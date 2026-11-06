"""
Session level metrics computed from the tidy telemetry tables.

Definitions (also in docs/METRICS.md):
  action status    on_time if done within target_sec of onset, late if done after,
                   missed if never done
  score            weighted points: on_time = full, late = half, missed = 0
  cue_to_action    seconds from deterioration onset to the first critical action
  time_to_rescue   seconds from onset to the scenario's rescue action
  instability_sec  seconds the simulated patient spent outside safe vital ranges
  gaze shares      share of fixation time on each gaze group after onset
  missed cue       an unstable stretch of 6 s or more with no look at patient or monitor
  pre_touch_dwell  seconds spent looking at a device in the 10 s before its first effective use
  ghost delta      learner time minus expert reference time, per completed action
"""
import numpy as np
import pandas as pd

from .catalog import SCENARIOS, object_group

MISSED_CUE_MIN = 6.0


def unstable_mask(vitals, scenario_id):
    d = SCENARIOS[scenario_id]["danger"]
    m = pd.Series(False, index=vitals.index)
    if "spo2_lt" in d:
        m |= vitals["spo2"] < d["spo2_lt"]
    if "hr_lt" in d:
        m |= vitals["hr"] < d["hr_lt"]
    if "hr_gt" in d:
        m |= vitals["hr"] > d["hr_gt"]
    if "sbp_lt" in d:
        m |= vitals["sbp"] < d["sbp_lt"]
    return m


def match_actions(events, scenario_id, onset):
    """Apply the scenario's interaction rules to the raw event stream."""
    out = {}
    for a in SCENARIOS[scenario_id]["actions"]:
        r = a["rule"]
        hit = events[(events.verb == r["verb"]) & (events.object == r["object"]) &
                      (events.target == r["target"]) & (events.t >= onset - 2)]
        out[a["id"]] = float(hit.t.min()) if len(hit) else None
    return out


def action_table(session, events, reference_rel=None):
    sc_id = session["scenario_id"]
    onset = session["onset_t"]
    times = match_actions(events, sc_id, onset)
    rows = []
    for order, a in enumerate(SCENARIOS[sc_id]["actions"], start=1):
        t = times[a["id"]]
        t_rel = None if t is None else round(t - onset, 1)
        if t_rel is None:
            status, pts = "missed", 0.0
        elif t_rel <= a["target_sec"]:
            status, pts = "on_time", float(a["weight"])
        else:
            status, pts = "late", a["weight"] / 2
        exp = None if reference_rel is None else reference_rel.get(a["id"])
        rows.append({
            "session_id": session["session_id"], "scenario_id": sc_id,
            "action_id": a["id"], "label": a["label"], "competency": a["comp"],
            "order": order, "weight": a["weight"], "target_sec": a["target_sec"],
            "t_abs": t, "t_rel": t_rel, "expert_rel": exp,
            "ghost_delta": None if (t_rel is None or exp is None) else round(t_rel - exp, 1),
            "status": status, "points": pts,
        })
    return pd.DataFrame(rows)


def gaze_shares(fix, onset):
    f = fix[fix.t1 > onset].copy()
    f["t0"] = f.t0.clip(lower=onset)
    f["dur"] = f.t1 - f.t0
    f["group"] = f.object.map(object_group)
    tot = f.dur.sum() or 1.0
    return {g: round(float(f.loc[f.group == g, "dur"].sum() / tot), 3)
            for g in ["patient", "monitor", "equipment", "environment"]}


def missed_cues(fix, vitals, scenario_id, onset):
    """Stretches where the patient is unstable and nobody is looking at them."""
    v = vitals[vitals.t >= onset].reset_index(drop=True)
    if v.empty:
        return []
    unstable = unstable_mask(v, scenario_id).values
    watching = np.zeros(len(v), dtype=bool)
    f = fix[fix.object.isin(["patient", "monitor"])]
    for t0, t1 in zip(f.t0, f.t1):
        lo, hi = int(np.floor(t0 - onset)), int(np.ceil(t1 - onset))
        watching[max(lo, 0):max(hi, 0)] = True
    bad = unstable & ~watching
    spans, start = [], None
    for i, b in enumerate(bad):
        if b and start is None:
            start = i
        if (not b or i == len(bad) - 1) and start is not None:
            end = i if not b else i + 1
            if end - start >= MISSED_CUE_MIN:
                spans.append((float(v.t[start]), float(v.t[min(end, len(v) - 1)])))
            start = None
    return spans


def pre_touch_dwell(fix, events, obj):
    """Seconds looking at a device in the 10 s before its first effective use."""
    e = events[(events.object == obj) & (events.verb.isin(["set", "attach", "administer", "use"]))]
    if e.empty:
        return None
    t = float(e.t.min())
    f = fix[(fix.object == obj) & (fix.t1 > t - 10) & (fix.t0 < t)]
    return round(float((f.t1.clip(upper=t) - f.t0.clip(lower=t - 10)).sum()), 2)


def session_summary(session, actions, fix, vitals, taps):
    sc = SCENARIOS[session["scenario_id"]]
    onset = session["onset_t"]
    total_w = actions.weight.sum()
    score = round(100 * actions.points.sum() / total_w, 1)
    done = actions.dropna(subset=["t_rel"])
    rescue = actions[actions.action_id == sc["rescue"]]
    after = vitals[vitals.t >= onset]
    shares = gaze_shares(fix, onset)
    cues = missed_cues(fix, vitals, session["scenario_id"], onset)
    return {
        "session_id": session["session_id"],
        "score": score,
        "on_time": int((actions.status == "on_time").sum()),
        "late": int((actions.status == "late").sum()),
        "missed": int((actions.status == "missed").sum()),
        "cue_to_action": None if done.empty else float(done.t_rel.min()),
        "time_to_rescue": None if rescue.t_rel.isna().all() else float(rescue.t_rel.iloc[0]),
        "instability_sec": int(unstable_mask(after, session["scenario_id"]).sum()),
        "min_spo2": int(after.spo2.min()) if len(after) else None,
        "gaze_patient": shares["patient"], "gaze_monitor": shares["monitor"],
        "gaze_equipment": shares["equipment"], "gaze_environment": shares["environment"],
        "missed_cues": len(cues),
        "missed_cue_sec": round(sum(b - a for a, b in cues), 1),
        "no_effect_taps": int(len(taps)),
        "ghost_delta_total": round(float(done.ghost_delta.dropna().sum()), 1),
    }
