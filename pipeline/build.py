"""
Turn raw headset logs into tidy tables and computed metrics.

  data/raw/sessions/*.jsonl  ->  data/processed/*.csv

Swap the raw folder for real DISCOVER exports and only parse_log() needs to
change if the field names differ (see docs/DATA_DICTIONARY.md).

Run:  python pipeline/build.py
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lens import metrics, ratings, workflow  # noqa: E402

RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"


def parse_log(path):
    meta, ev, taps, fix, pose, vit, state = None, [], [], [], [], [], []
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            k = r["k"]
            if k == "meta":
                meta = r
            elif k == "evt":
                ev.append({"t": r["t"], "verb": r["v"], "object": r["o"], "target": r["x"]})
            elif k == "tap":
                taps.append({"t": r["t"], "object": r["o"], "control": r["x"]})
            elif k == "fix":
                fix.append({"t0": r["t0"], "t1": r["t1"], "object": r["o"]})
            elif k == "pose":
                pose.append({"t": r["t"], "x": r["x"], "y": r["y"]})
            elif k == "vit":
                vit.append({"t": r["t"], "hr": r["hr"], "spo2": r["spo2"], "rr": r["rr"], "sbp": r["sbp"]})
            elif k == "state":
                state.append({"t": r["t"], "state": r["s"]})
            elif k == "end":
                meta["duration"] = r["t"]
    sid = meta["session_id"]
    frames = {}
    for name, rows in [("events", ev), ("taps", taps), ("fixations", fix),
                       ("poses", pose), ("vitals", vit), ("states", state)]:
        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame(columns={"events": ["t", "verb", "object", "target"],
                                       "taps": ["t", "object", "control"],
                                       "fixations": ["t0", "t1", "object"],
                                       "poses": ["t", "x", "y"],
                                       "vitals": ["t", "hr", "spo2", "rr", "sbp"],
                                       "states": ["t", "state"]}[name])
        df.insert(0, "session_id", sid)
        frames[name] = df
    st = frames["states"]
    onset = st.loc[st.state == "deteriorating", "t"]
    meta["onset_t"] = float(onset.iloc[0]) if len(onset) else 0.0
    return meta, frames


def main():
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    logs = sorted((RAW / "sessions").glob("*.jsonl"))
    if not logs:
        raise SystemExit("No raw logs found. Run: python generator/make_raw.py")

    metas, parts = [], {}
    for p in logs:
        meta, frames = parse_log(p)
        metas.append(meta)
        for k, df in frames.items():
            parts.setdefault(k, []).append(df)
    sessions = pd.DataFrame(metas)
    sessions["started_at"] = pd.to_datetime(sessions["started_at"])
    tables = {k: pd.concat(v, ignore_index=True) for k, v in parts.items()}
    by = {k: {sid: g for sid, g in df.groupby("session_id")} for k, df in tables.items()}
    empty = {k: df.iloc[0:0] for k, df in tables.items()}

    def part(name, sid):
        return by[name].get(sid, empty[name])

    # expert reference times per scenario (the ghost)
    reference = {}
    for _, s in sessions[sessions["mode"] == "reference"].iterrows():
        a = metrics.action_table(s, part("events", s.session_id))
        reference[s.scenario_id] = dict(zip(a.action_id, a.t_rel))

    action_rows, summaries = [], []
    for _, s in sessions.iterrows():
        a = metrics.action_table(s, part("events", s.session_id), reference.get(s.scenario_id))
        action_rows.append(a)
        summaries.append(metrics.session_summary(
            s, a, part("fixations", s.session_id), part("vitals", s.session_id), part("taps", s.session_id)))
    actions = pd.concat(action_rows, ignore_index=True)
    summary = pd.DataFrame(summaries)

    # pre-touch dwell per device per session, for the partner view
    dwell = []
    for sid in sessions.session_id:
        f, e = part("fixations", sid), part("events", sid)
        for obj in ["o2_flow", "vent", "iv_pump", "suction", "phone", "med_cart", "bvm"]:
            d = metrics.pre_touch_dwell(f, e, obj)
            if d is not None:
                dwell.append({"session_id": sid, "object": obj, "pre_touch_dwell": d})
    dwell = pd.DataFrame(dwell)

    hist, current, difficulty = ratings.run_ratings(sessions, actions)

    roster = pd.read_csv(RAW / "roster.csv")
    surveys = pd.read_csv(RAW / "surveys.csv")
    sessions = sessions.merge(summary, on="session_id")

    # workflow paths across information lanes, standard path per role
    wf_steps, role_standard, wf_metrics = workflow.build(sessions, tables["events"], actions, roster)
    sessions = sessions.merge(wf_metrics, on="session_id", how="left")

    out = {
        "sessions": sessions, "actions": actions, "events": tables["events"],
        "taps": tables["taps"], "fixations": tables["fixations"], "poses": tables["poses"],
        "vitals": tables["vitals"], "states": tables["states"], "device_dwell": dwell,
        "rating_history": hist, "ratings": current, "action_difficulty": difficulty,
        "roster": roster, "surveys": surveys,
        "workflow_steps": wf_steps, "role_standard": role_standard,
    }
    for name, df in out.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
    print(f"Built {len(out)} tables from {len(logs)} logs in {time.time() - t0:.1f}s -> {OUT}")


if __name__ == "__main__":
    main()
