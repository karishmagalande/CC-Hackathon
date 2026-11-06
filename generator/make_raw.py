"""
Generate synthetic DISCOVER headset telemetry.

Output (data/raw/):
  roster.csv              learners
  surveys.csv             pre/post confidence survey per learner
  sessions/<id>.jsonl     one telemetry log per simulation run
  _profiles.csv           hidden behaviour profile per learner (for validation only)

Each JSONL log mixes record kinds the way a headset stream would:
  {"k":"meta", ...}                         session header
  {"k":"evt","t":47.21,"v":"attach","o":"bvm","x":"patient_face"}
  {"k":"tap","t":51.0,"o":"vent","x":"mode_dial","fx":0}   touch with no effect
  {"k":"fix","t0":12.0,"t1":13.4,"o":"monitor"}            gaze fixation
  {"k":"pose","t":12,"x":2.81,"y":2.02}                    head position, 1 Hz
  {"k":"vit","t":12,"hr":152,"spo2":94,"rr":46,"sbp":88}   patient engine vitals, 1 Hz
  {"k":"state","t":31.4,"s":"deteriorating"}               patient engine state change
  {"k":"end","t":300,"reason":"facilitator_stop"}

Run:  python generator/make_raw.py --seed 7
"""
import argparse
import csv
import json
import math
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lens.catalog import (CONTROL_SURFACES, ROLES, ROOM_OBJECTS, SCENARIOS,  # noqa: E402
                          UNITS, object_xy)

RAW = ROOT / "data" / "raw"

# ---------------------------------------------------------------------------
# Behaviour profiles. These drive the stories the dashboard should surface.
#   speed      multiplier on expert action times at attempt 1
#   learn      fraction of the gap to expert closed per repeat attempt
#   miss       base probability of skipping a non-trivial action
#   slow_comp  competency codes that run extra slow, with their multiplier
#   gaze_calm / gaze_crisis  weights over patient, monitor, equipment, environment
#   predwell   seconds spent looking at equipment before first touch
#   mistap     mean touches without effect per equipment action
# ---------------------------------------------------------------------------
PROFILES = {
    "expert":          dict(speed=1.00, learn=0.00, miss=0.00, slow_comp={}, gaze_calm=(4, 3, 1, 1),
                            gaze_crisis=(6, 3, 1, 0.3), predwell=0.5, mistap=0.1),
    "steady":          dict(speed=1.85, learn=0.22, miss=0.07, slow_comp={}, gaze_calm=(4, 3, 1.5, 2),
                            gaze_crisis=(5, 3, 1.5, 0.8), predwell=1.0, mistap=0.4),
    "monitor_fixated": dict(speed=2.30, learn=0.18, miss=0.10, slow_comp={"AIR": 1.35}, gaze_calm=(2, 6, 1, 1.5),
                            gaze_crisis=(1.5, 8, 1, 0.6), predwell=1.0, mistap=0.4),
    "solo_operator":   dict(speed=1.75, learn=0.20, miss=0.08, slow_comp={"COM": 2.6}, gaze_calm=(5, 2, 1.5, 1),
                            gaze_crisis=(6, 2, 1.5, 0.4), predwell=0.9, mistap=0.3),
    "fast_improver":   dict(speed=2.90, learn=0.42, miss=0.20, slow_comp={"AIR": 1.2}, gaze_calm=(3, 3, 2, 3),
                            gaze_crisis=(3, 4, 2, 2.0), predwell=1.6, mistap=1.0),
    "equipment_hesitant": dict(speed=1.75, learn=0.22, miss=0.07, slow_comp={"EQP": 2.3}, gaze_calm=(4, 3, 2.5, 1),
                            gaze_crisis=(4, 3, 3.5, 0.6), predwell=3.5, mistap=2.8),
}
PROFILE_MIX = ["steady"] * 9 + ["monitor_fixated"] * 6 + ["solo_operator"] * 6 + \
              ["fast_improver"] * 7 + ["equipment_hesitant"] * 6 + ["expert"] * 2

FIRST = ["Maya", "Jordan", "Priya", "Ethan", "Lena", "Marcus", "Sofia", "Daniel", "Aisha", "Noah",
         "Grace", "Omar", "Hannah", "Lucas", "Zoe", "Caleb", "Nadia", "Owen", "Ruby", "Isaac",
         "Leah", "Mateo", "Chloe", "Samuel", "Ava", "Elijah", "Mia", "Henry", "Ivy", "Theo",
         "Clara", "Julian", "Elena", "Miles", "Harper", "Rowan"]
LAST_INITIAL = list("OKRMTBLSHWCDPAGNFJVEYZQIUX")

WALK_SPEED = 1.1  # m/s
# How hard each device's interface is to use under pressure (1.0 = neutral).
# Scales the look-before-use and the touches with no effect.
DEVICE_FRICTION = {"vent": 2.2, "iv_pump": 1.7, "o2_flow": 1.1, "med_cart": 1.3,
                   "suction": 0.9, "phone": 0.5, "bvm": 0.8}
NO_WALK = {"clock", "team"}  # can be done from where you stand
AT_PATIENT = {"penlight"}    # performed at the crib


def walk_target(obj):
    if obj in NO_WALK:
        return None
    if obj in AT_PATIENT:
        return object_xy("patient")
    x, y = object_xy(obj)
    # stand in front of wall objects, not inside them
    return (min(max(x, 0.5), 5.5), min(max(y, 0.5), 4.3))


def simulate_vitals(rng, sc, onset, rescue_t, duration):
    v = sc["vitals"]
    base, nadir = v["baseline"], v["nadir"]
    rows = []
    at_rescue = None
    for t in range(0, duration + 1):
        row = {"t": t}
        for key in ("hr", "spo2", "rr", "sbp"):
            b, n = base[key], nadir[key]
            if t < onset:
                val = b
            elif rescue_t is None or t < rescue_t:
                val = b + (n - b) * (1 - math.exp(-(t - onset) / v["tau_decline"]))
            else:
                if at_rescue is None:
                    at_rescue = {}
                if key not in at_rescue:
                    tr = rescue_t
                    at_rescue[key] = b + (n - b) * (1 - math.exp(-(tr - onset) / v["tau_decline"]))
                start = at_rescue[key]
                val = start + (b - start) * (1 - math.exp(-(t - rescue_t) / v["tau_recover"]))
            noise = {"hr": 2.5, "spo2": 0.6, "rr": 1.5, "sbp": 1.5}[key]
            val = val + rng.normal(0, noise)
            if key == "spo2":
                val = min(100, val)
            row[key] = int(round(val))
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Role workflows: information-gathering steps each role takes, following the
# hackathon team's VR observation synthesis (Provider, RN, RT).
# Each step: (lane object, verb, what was gathered, when).
#   when = ("pre", a, b)    seconds a..b after the session starts
#   when = ("on", a, b)     seconds a..b after the patient starts to change
#   when = ("end", a, b)    seconds a..b before the session ends
# ---------------------------------------------------------------------------
ROLE_STEPS = {
    "Provider": [
        ("team", "communicate", "patient hand-off", ("pre", 1, 3)),
        ("epic", "view", "check orders, meds, labs", ("pre", 4, 9)),
        ("epic", "view", "review trends and notes", ("pre", 10, 16)),
        ("patient", "touch", "physical exam", ("pre", 18, 24)),
        ("monitor", "check", "review vitals trend", ("on", 8, 16)),
        ("team", "communicate", "discuss concerns with team", ("on", 18, 32)),
        ("patient", "touch", "reassess response", ("on", 70, 110)),
        ("epic", "view", "new orders and labs", ("on", 115, 150)),
        ("team", "communicate", "share care plan", ("end", 15, 35)),
    ],
    "RN": [
        ("team", "communicate", "patient hand-off (nursing packet)", ("pre", 1, 3)),
        ("epic", "view", "check orders, meds, labs", ("pre", 3, 7)),
        ("patient", "touch", "physical exam: pulse, breath, cap refill, temp", ("pre", 9, 14)),
        ("monitor", "check", "read vitals", ("on", 3, 8)),
        ("team", "communicate", "discuss concerns with provider", ("on", 16, 30)),
        ("monitor", "check", "watch vitals trend", ("on", 36, 50)),
        ("epic", "view", "chart vitals and head-to-toe", ("on", 55, 85)),
        ("monitor", "check", "recheck vitals after intervention", ("on", 135, 170)),
        ("patient", "touch", "get blood for iSTAT", ("on", 90, 130)),
        ("team", "communicate", "listen to care plan from provider", ("end", 45, 70)),
        ("epic", "view", "update charts", ("end", 10, 25)),
    ],
    "RT": [
        ("team", "communicate", "respiratory hand-off", ("pre", 1, 3)),
        ("vent", "inspect", "check respiratory equipment", ("pre", 5, 10)),
        ("monitor", "check", "SpO2 and respiratory rate", ("on", 3, 8)),
        ("team", "communicate", "update team on airway", ("on", 14, 26)),
        ("epic", "view", "check respiratory orders", ("on", 45, 75)),
        ("team", "communicate", "discuss settings with provider", ("on", 80, 110)),
        ("patient", "touch", "reassess breath sounds", ("on", 115, 150)),
        ("team", "communicate", "hand back to bedside team", ("end", 15, 35)),
    ],
}
# how likely a profile is to skip a step of its role's workflow
SKIP = {"expert": 0.0, "steady": 0.10, "monitor_fixated": 0.18, "solo_operator": 0.15,
        "fast_improver": 0.28, "equipment_hesitant": 0.15}
CDS_SPEEDUP = 0.82   # learners who look at COMET act about 18% sooner afterwards


def workflow_events(rng, role, prof_name, attempt, onset, duration, cds_on):
    """Information-gathering events for one session, following the role's workflow."""
    out = []
    skip = SKIP.get(prof_name, 0.15) * (0.75 ** (attempt - 1))
    for obj, verb, what, (anchor, a, b) in ROLE_STEPS.get(role, ROLE_STEPS["RN"]):
        is_comm = obj == "team"
        p_skip = skip * (3.5 if (is_comm and prof_name == "solo_operator") else 1.0)
        if rng.random() < p_skip:
            continue
        base = 0.0 if anchor == "pre" else onset if anchor == "on" else duration
        t = base + (-1 if anchor == "end" else 1) * float(rng.uniform(a, b))
        if anchor == "pre":
            t = min(t, onset - 1)
        out.append({"k": "evt", "t": round(max(0.5, min(t, duration - 3)), 2), "v": verb, "o": obj, "x": what})
    if prof_name == "monitor_fixated":   # extra glances back to the monitor
        for _ in range(rng.integers(2, 4)):
            out.append({"k": "evt", "t": round(onset + float(rng.uniform(5, 120)), 2), "v": "check",
                        "o": "monitor", "x": "re-read vitals"})
    if cds_on:
        out.append({"k": "evt", "t": round(onset + float(rng.uniform(2, 9)), 2), "v": "view", "o": "comet",
                    "x": "COMET risk score: severity of condition"})
    return out


def plan_actions(rng, sc, prof, attempt, is_reference):
    """Decide when (or if) each critical action happens, relative to onset."""
    if is_reference:
        speed = 0.92
    else:
        gap = prof["speed"] - 1.0
        speed = 1.0 + gap * (1 - prof["learn"]) ** (attempt - 1)
        if rng.random() < 0.14 * 0.5 ** (attempt - 1):
            speed *= rng.uniform(1.3, 1.8)  # an off day: distracted, new team, unfamiliar room
    plan = []
    for i, a in enumerate(sc["actions"]):
        mult = speed * prof["slow_comp"].get(a["comp"], 1.0) ** (0.75 ** (attempt - 1))
        miss_p = 0.0 if is_reference else 0.02 + prof["miss"] * (0.7 ** (attempt - 1))
        if a["comp"] in prof["slow_comp"]:
            miss_p *= 2.2
        if i == 0:
            miss_p *= 0.2
        missed = rng.random() < miss_p
        jitter = 1.0 if is_reference else rng.lognormal(0, 0.24)
        t_rel = a["expert_sec"] * mult * jitter
        plan.append({"action": a, "t_rel": t_rel, "missed": missed})
    # one person does these one after another: keep at least 2.5 s apart
    done = sorted([p for p in plan if not p["missed"]], key=lambda p: p["t_rel"])
    last = -10
    for p in done:
        if p["t_rel"] < last + 2.5:
            p["t_rel"] = last + 2.5 + rng.uniform(0, 1.5)
        last = p["t_rel"]
    return plan


def gaze_stream(rng, prof, duration, onset, anchors):
    """Fixation segments: anchored looks at action objects plus free looking."""
    groups = {
        "patient": ["patient"],
        "monitor": ["monitor"],
        "equipment": ["bvm", "o2_flow", "suction", "iv_pump", "vent", "med_cart", "phone"],
        "environment": ["door", "sink", "clock", "elsewhere"],
    }
    gnames = list(groups)
    anchored = []
    for t, obj in anchors:
        look_obj = "patient" if obj in AT_PATIENT else obj
        group = ROOM_OBJECTS[look_obj]["group"]
        pre = prof["predwell"] * DEVICE_FRICTION.get(look_obj, 1.0) if group == "equipment" else 0.8
        pre = pre * rng.uniform(0.7, 1.3)
        anchored.append((max(0, t - pre), t + rng.uniform(0.6, 1.6), look_obj))
    anchored.sort()

    fixes = []
    t = 0.0
    ai = 0
    while t < duration:
        if ai < len(anchored) and t >= anchored[ai][0] - 0.05:
            t0, t1, obj = anchored[ai]
            t0 = max(t0, t)
            if t1 > t0:
                fixes.append((round(t0, 2), round(t1, 2), obj))
                t = t1
            ai += 1
            continue
        w = np.array(prof["gaze_crisis"] if t >= onset else prof["gaze_calm"], dtype=float)
        g = gnames[rng.choice(len(gnames), p=w / w.sum())]
        obj = groups[g][rng.integers(len(groups[g]))]
        dur = float(np.clip(rng.lognormal(math.log(1.1), 0.5), 0.25, 4.0))
        t1 = t + dur
        if ai < len(anchored):
            t1 = min(t1, anchored[ai][0])
        if t1 - t >= 0.15:
            fixes.append((round(t, 2), round(min(t1, duration), 2), obj))
        t = max(t1, t + 0.15)
    return fixes


def pose_stream(rng, duration, actions_timed):
    """Head position at 1 Hz from a simple walk plan."""
    crib = object_xy("patient")
    crib_stand = (crib[0] - 0.55, crib[1] - 0.45)
    way = [(0.0, (0.7, 0.4)), (5.0, crib_stand)]
    pos = crib_stand
    for t, obj in actions_timed:
        tgt = walk_target(obj)
        if tgt is None:
            continue
        if obj in ("patient", "penlight"):
            tgt = crib_stand
        dist = math.dist(pos, tgt)
        travel = dist / WALK_SPEED
        leave = max(way[-1][0] + 0.5, t - travel - 0.4)
        way.append((leave, pos))
        way.append((leave + travel, tgt))
        way.append((t + 1.5, tgt))
        pos = tgt
        if tgt != crib_stand:
            back = math.dist(tgt, crib_stand) / WALK_SPEED
            way.append((t + 1.5 + back, crib_stand))
            pos = crib_stand
    way.sort(key=lambda w: w[0])
    out = []
    j = 0
    for s in range(0, duration + 1):
        while j < len(way) - 2 and way[j + 1][0] <= s:
            j += 1
        (ta, pa), (tb, pb) = way[j], way[min(j + 1, len(way) - 1)]
        f = 0 if tb <= ta else min(1, max(0, (s - ta) / (tb - ta)))
        x = pa[0] + (pb[0] - pa[0]) * f + rng.normal(0, 0.03)
        y = pa[1] + (pb[1] - pa[1]) * f + rng.normal(0, 0.03)
        out.append({"k": "pose", "t": s, "x": round(x, 2), "y": round(y, 2)})
    return out


def simulate_session(rng, sid, learner, scenario_id, attempt, started_at, prof, is_reference=False,
                     role="RN", prof_name="steady", cds_on=False):
    sc = SCENARIOS[scenario_id]
    duration = sc["duration"]
    onset = float(rng.uniform(*sc["onset_range"]))
    plan = plan_actions(rng, sc, prof, attempt, is_reference)
    if cds_on and not is_reference:
        for p in plan:
            if p["t_rel"] > 8:
                p["t_rel"] = 8 + (p["t_rel"] - 8) * CDS_SPEEDUP

    records = [{
        "k": "meta", "session_id": sid, "learner_id": learner, "scenario_id": scenario_id,
        "attempt": attempt, "started_at": started_at.isoformat(timespec="seconds"),
        "headset": f"Q3-{rng.integers(100, 999)}", "build": "discover-2.4.1",
        "mode": "reference" if is_reference else "training", "cds_on": bool(cds_on),
    }]

    events, taps, anchors, rescue_t = [], [], [], None
    # pre-onset settling: learner walks in, glances, touches the patient once
    # Providers gather information in Epic before going to the bedside (VR observation synthesis)
    first_look = (14, 18) if role == "Provider" else (6, 12)
    events.append({"k": "evt", "t": round(min(float(rng.uniform(*first_look)), onset - 2), 2),
                   "v": "touch", "o": "patient", "x": "forehead"})
    for p in plan:
        if p["missed"]:
            continue
        a = p["action"]
        t = onset + p["t_rel"]
        if t > duration - 4:
            continue
        r = a["rule"]
        # some setup interactions before the effective one (pick up, carry)
        if r["object"] in ("bvm", "penlight") or r["verb"] == "administer":
            events.append({"k": "evt", "t": round(t - rng.uniform(1.5, 4), 2),
                           "v": "grab", "o": r["object"], "x": "hand"})
        # touches with no effect on control surfaces
        if r["object"] in CONTROL_SURFACES:
            n = rng.poisson(prof["mistap"] * DEVICE_FRICTION.get(r["object"], 1.0) * (0.8 ** (attempt - 1)))
            for _ in range(n):
                taps.append({"k": "tap", "t": round(t - rng.uniform(0.3, 6), 2), "o": r["object"],
                             "x": str(rng.choice(CONTROL_SURFACES[r["object"]])), "fx": 0})
        events.append({"k": "evt", "t": round(t, 2), "v": r["verb"], "o": r["object"], "x": r["target"]})
        anchors.append((t, r["object"]))
        if a["id"] == sc["rescue"]:
            rescue_t = int(round(t))

    # information-gathering steps of the learner's role (Epic, monitor, COMET, team)
    wf = workflow_events(rng, role, "expert" if is_reference else prof_name, attempt, onset, duration, cds_on)
    events += wf
    anchors += [(e["t"], e["o"]) for e in wf if e["o"] in ROOM_OBJECTS]

    # distractor interactions that are not critical actions
    for _ in range(rng.integers(1, 4)):
        obj = str(rng.choice(["sink", "monitor", "door", "suction", "med_cart"]))
        events.append({"k": "evt", "t": round(float(rng.uniform(5, duration - 10)), 2),
                       "v": "touch", "o": obj, "x": "surface"})

    vit = simulate_vitals(rng, sc, onset, rescue_t, duration)
    fixes = gaze_stream(rng, prof, duration, onset, sorted(anchors))
    poses = pose_stream(rng, duration, sorted(anchors))

    stream = events + taps
    stream.append({"k": "state", "t": round(onset, 2), "s": "deteriorating"})
    if rescue_t is not None:
        stream.append({"k": "state", "t": float(rescue_t), "s": "responding"})
    stream += [{"k": "fix", "t0": a, "t1": b, "o": o} for a, b, o in fixes]
    stream += poses
    stream += [{"k": "vit", **row} for row in vit]
    stream.sort(key=lambda r: r.get("t", r.get("t0", 0)))
    records += stream
    records.append({"k": "end", "t": duration, "reason": "facilitator_stop"})
    return records


def quick_score(records, scenario_id):
    """Score a generated log the same way the pipeline does (used to pin the demo story)."""
    sc = SCENARIOS[scenario_id]
    onset = next(r["t"] for r in records if r["k"] == "state" and r["s"] == "deteriorating")
    ev = [r for r in records if r["k"] == "evt"]
    pts = 0.0
    for a in sc["actions"]:
        r = a["rule"]
        hits = [e["t"] for e in ev if e["v"] == r["verb"] and e["o"] == r["object"]
                and e["x"] == r["target"] and e["t"] >= onset - 2]
        if hits:
            pts += a["weight"] if min(hits) - onset <= a["target_sec"] else a["weight"] / 2
    return 100 * pts / sum(a["weight"] for a in sc["actions"])


# Demo learner score bands, so the pitch story is the same on every machine.
DEMO_BANDS = {("SC01", 1): (35, 55), ("SC01", 2): (68, 82), ("SC01", 3): (90, 100),
              ("SC04", 1): (60, 78), ("SC02", 1): (45, 65)}


def write_jsonl(path, records):
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


def main(seed=7):
    rng = np.random.default_rng(seed)
    if RAW.exists():
        shutil.rmtree(RAW)
    (RAW / "sessions").mkdir(parents=True)

    n = len(FIRST)
    profiles = list(PROFILE_MIX[:n])
    rng.shuffle(profiles)
    # Demo learner: Maya O. is a fast improver. Fixed so the pitch story is stable.
    profiles[0] = "fast_improver"
    profiles[1] = "monitor_fixated"
    profiles[2] = "equipment_hesitant"
    profiles[3] = "solo_operator"

    roster, hidden = [], []
    for i in range(n):
        lid = f"L{i + 1:03d}"
        role = "RN" if i == 0 else ROLES[rng.integers(len(ROLES))]
        cohort = "Summer 2026" if i % 3 == 2 else "Fall 2026"
        exp = {"RN": rng.integers(0, 6), "Provider": rng.integers(0, 9), "RT": rng.integers(1, 10)}.get(role, 1)
        roster.append({"learner_id": lid, "display_name": f"{FIRST[i]} {LAST_INITIAL[i % 26]}.",
                       "role": role, "unit": UNITS[rng.integers(len(UNITS))],
                       "cohort": cohort, "experience_years": int(exp)})
        hidden.append({"learner_id": lid, "profile": profiles[i]})

    with open(RAW / "roster.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(roster[0]))
        w.writeheader()
        w.writerows(roster)
    with open(RAW / "_profiles.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["learner_id", "profile"])
        w.writeheader()
        w.writerows(hidden)

    sc_ids = list(SCENARIOS)
    count = 0
    # reference runs used as the expert ghost
    for sc_id in sc_ids:
        count += 1
        sid = f"REF-{sc_id}"
        recs = simulate_session(rng, sid, "EXPERT", sc_id, 1, datetime(2026, 5, 20, 9, 0),
                                PROFILES["expert"], is_reference=True, role="RN", prof_name="expert", cds_on=True)
        write_jsonl(RAW / "sessions" / f"{sid}.jsonl", recs)

    sess_no = 0
    surveys = []
    for r, h in zip(roster, hidden):
        prof = PROFILES[h["profile"]]
        start = datetime(2026, 6, 2) if r["cohort"] == "Summer 2026" else datetime(2026, 9, 1)
        if r["learner_id"] == "L001":
            schedule = ["SC01", "SC01", "SC01", "SC04", "SC02"]
        else:
            k = int(rng.integers(3, 7))
            main_sc = sc_ids[rng.integers(len(sc_ids))]
            others = [s for s in sc_ids if s != main_sc]
            schedule = [main_sc, main_sc] + list(rng.choice(others, size=k - 2))
            if rng.random() < 0.5:
                schedule.append(main_sc)
        attempts = {}
        day = start + timedelta(days=int(rng.integers(0, 10)))
        for sc_id in schedule:
            attempts[sc_id] = attempts.get(sc_id, 0) + 1
            sess_no += 1
            sid = f"S{sess_no:04d}"
            when = day.replace(hour=int(rng.integers(8, 17)), minute=int(rng.integers(0, 60)))
            cds_on = bool(rng.random() < 0.5)
            kw = dict(role=r["role"], prof_name=h["profile"], cds_on=cds_on)
            if r["learner_id"] == "L001":
                lo, hi = DEMO_BANDS[(sc_id, attempts[sc_id])]
                for trial in range(500):
                    sub = np.random.default_rng(seed * 1000 + sess_no * 37 + trial)
                    kw["cds_on"] = attempts[sc_id] == 3   # Maya sees COMET on her third attempt
                    recs = simulate_session(sub, sid, r["learner_id"], sc_id, attempts[sc_id], when, prof, **kw)
                    if lo <= quick_score(recs, sc_id) <= hi:
                        break
            else:
                recs = simulate_session(rng, sid, r["learner_id"], sc_id, attempts[sc_id], when, prof, **kw)
            write_jsonl(RAW / "sessions" / f"{sid}.jsonl", recs)
            day += timedelta(days=int(rng.integers(4, 15)))
            count += 1
        total = len(schedule)
        for comp in ("REC", "COM", "AIR", "CIR", "EQP"):
            pre = int(np.clip(rng.normal(2.6 if h["profile"] != "expert" else 4.2, 0.7), 1, 5))
            gain = min(2, total * 0.25 + rng.normal(0.3, 0.4))
            post = int(np.clip(round(pre + gain), 1, 5))
            surveys.append({"learner_id": r["learner_id"], "competency": comp,
                            "pre_confidence": pre, "post_confidence": post})

    with open(RAW / "surveys.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(surveys[0]))
        w.writeheader()
        w.writerows(surveys)

    print(f"Wrote {count} session logs for {n} learners to {RAW}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    main(ap.parse_args().seed)
