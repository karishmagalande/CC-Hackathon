"""
Workflow paths: each session as a route across information lanes.

Follows the hackathon team's VR observation synthesis:
  1. each session becomes a path across lanes (Epic, patient assessment,
     vital sign monitor, COMET, communication)
  2. paths are overlaid per role to find the standard (typical) workflow
  3. each learner's path is compared with their role's standard
  4. COMET views are marked as CDS touchpoints

The typical path is the medoid: the real path with the smallest total edit
distance to every other path of that role, so it is always a path someone took.
"""
import numpy as np
import pandas as pd

from .catalog import LANE_ORDER, SCENARIOS, event_lane

# readable names for logged interactions that are also critical actions
ACTION_LABEL = {(a["rule"]["verb"], a["rule"]["object"], a["rule"]["target"]): a["label"]
                for sc in SCENARIOS.values() for a in sc["actions"]}
ACTION_LABEL[("touch", "patient", "forehead")] = "First look at patient"


def core(lanes):
    """Lane sequence without COMET (the CDS touchpoint), duplicates merged. Standards use this."""
    out = []
    for x in lanes:
        if x != "comet" and (not out or out[-1] != x):
            out.append(x)
    return out


def path_steps(events, session_id):
    """Ordered lane steps for one session. Consecutive steps in the same lane merge into one."""
    ev = events.sort_values("t")
    steps = []
    for e in ev.itertuples():
        lane = event_lane(e.verb, e.object)
        if lane is None:
            continue
        what = ACTION_LABEL.get((e.verb, e.object, e.target), str(e.target).replace("_", " "))
        if steps and steps[-1]["lane"] == lane:
            if what not in steps[-1]["what"]:
                steps[-1]["what"] += f"; {what}"
            continue
        steps.append({"session_id": session_id, "t": float(e.t), "lane": lane, "what": what})
    for i, s in enumerate(steps, start=1):
        s["step"] = i
    return steps


def edit_distance(a, b):
    """Insertions, deletions and swaps needed to turn lane sequence a into b."""
    d = np.zeros((len(a) + 1, len(b) + 1), dtype=int)
    d[:, 0] = range(len(a) + 1)
    d[0, :] = range(len(b) + 1)
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + (a[i - 1] != b[j - 1]))
    return int(d[-1, -1])


def match(path, standard):
    """0-100: how closely a lane sequence follows the standard."""
    if not standard or not path:
        return 0.0 if standard else None
    return round(100 * (1 - edit_distance(path, standard) / max(len(path), len(standard))), 1)


def typical_path(paths):
    """The path with the smallest total distance to all others (the medoid)."""
    paths = [p for p in paths if p]
    if not paths:
        return []
    return min(paths, key=lambda p: sum(edit_distance(p, q) for q in paths))


def missing_steps(path, standard):
    """Indices of standard steps the learner's path does not contain, in order (via LCS)."""
    n, m = len(standard), len(path)
    L = np.zeros((n + 1, m + 1), dtype=int)
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            L[i, j] = L[i + 1, j + 1] + 1 if standard[i] == path[j] else max(L[i + 1, j], L[i, j + 1])
    kept, i, j = set(), 0, 0
    while i < n and j < m:
        if standard[i] == path[j]:
            kept.add(i)
            i, j = i + 1, j + 1
        elif L[i + 1, j] >= L[i, j + 1]:
            i += 1
        else:
            j += 1
    return [k for k in range(n) if k not in kept]


def session_metrics(steps, events, onset, standard, actions):
    lanes = [s["lane"] for s in steps]
    first_assess = next((s["t"] for s in steps if s["lane"] == "assessment"), None)
    epic_ev = events[events.object == "epic"]
    epic_before = int((epic_ev.t < first_assess).sum()) if first_assess is not None else int(len(epic_ev))
    comm = next((s["t"] for s in steps if s["lane"] == "communication" and s["t"] > 0), None)
    comet = events[events.object == "comet"]
    comet_t = float(comet.t.min()) if len(comet) else None
    after = None
    if comet_t is not None and len(actions):
        nxt = actions.dropna(subset=["t_abs"])
        nxt = nxt[nxt.t_abs > comet_t]
        after = round(float(nxt.t_abs.min() - comet_t), 1) if len(nxt) else None
    share = {f"lane_share_{k}": round(lanes.count(k) / len(lanes), 3) if lanes else 0.0 for k in LANE_ORDER}
    return {
        "workflow_steps": len(steps),
        "lane_switches": max(len(steps) - 1, 0),
        "first_lane": lanes[0] if lanes else None,
        "first_info_lane": next((x for x in lanes if x != "communication"), None),
        "epic_before_assessment": epic_before,
        "time_to_bedside": first_assess,
        "time_to_first_communication": comm,
        "workflow_match": match(core(lanes), standard),
        "workflow_missing": len(missing_steps(core(lanes), standard)) if standard else None,
        "cds_viewed": comet_t is not None,
        "cds_view_after_change": None if comet_t is None else round(comet_t - onset, 1),
        "cds_to_next_action": after,
        **share,
    }


def build(sessions, events, actions, roster):
    """Returns (workflow_steps, role_standard, per-session metrics)."""
    role_of = dict(zip(roster.learner_id, roster.role))
    by_ev = {k: g for k, g in events.groupby("session_id")}
    by_act = {k: g for k, g in actions.groupby("session_id")}
    empty = events.iloc[0:0]
    all_steps, lanes_of = [], {}
    for s in sessions.itertuples():
        st = path_steps(by_ev.get(s.session_id, empty), s.session_id)
        all_steps += st
        lanes_of[s.session_id] = [x["lane"] for x in st]

    train = sessions[sessions["mode"] == "training"]
    standards, std_rows = {}, []
    for role in sorted(set(role_of.values())):
        sids = [x for x in train.session_id if role_of.get(train.set_index("session_id").loc[x, "learner_id"]) == role]
        std = typical_path([core(lanes_of[x]) for x in sids])
        standards[role] = std
        steps = pd.DataFrame([x for x in all_steps if x["session_id"] in set(sids)])
        for i, lane in enumerate(std, start=1):
            # most common description of that lane at about that position, for the label
            cand = steps[(steps.lane == lane) & (steps.step == i)] if len(steps) else steps
            if len(cand) == 0 and len(steps):
                cand = steps[(steps.lane == lane) & (steps.step.between(i - 1, i + 2))]
            what = cand.what.str.split(";").str[0].mode().iloc[0] if len(cand) else ""
            std_rows.append({"role": role, "step": i, "lane": lane, "what": what, "sessions": len(sids)})

    metrics = []
    for s in sessions.itertuples():
        role = role_of.get(s.learner_id, "RN")
        st = [x for x in all_steps if x["session_id"] == s.session_id]
        m = session_metrics(st, by_ev.get(s.session_id, empty), float(s.onset_t), standards.get(role, []),
                            by_act.get(s.session_id, actions.iloc[0:0]))
        metrics.append({"session_id": s.session_id, "workflow_role": role, **m})
    return pd.DataFrame(all_steps), pd.DataFrame(std_rows), pd.DataFrame(metrics)
