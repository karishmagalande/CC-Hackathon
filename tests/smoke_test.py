"""Checks that the generated data tells the stories the views depend on.  Run: python tests/smoke_test.py"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    return ok


s = pd.read_csv(P / "sessions.csv")
prof = pd.read_csv(ROOT / "data" / "raw" / "_profiles.csv")
t = s[s["mode"] == "training"].merge(prof, on="learner_id")
by_att = t.groupby(t.attempt.clip(upper=3)).score.mean()
maya = t[(t.learner_id == "L001") & (t.scenario_id == "SC01")].sort_values("attempt").score.tolist()
ref = s[s["mode"] == "reference"]
roster = pd.read_csv(P / "roster.csv")[["learner_id", "role"]]
w = t.merge(roster, on="learner_id")
std = pd.read_csv(P / "role_standard.csv")
cds = w.cds_viewed.astype(str).str.lower() == "true"

results = [
    check("five expert reference runs score 100", len(ref) == 5 and (ref.score == 100).all()),
    check("mean score rises with repeat attempts", by_att.is_monotonic_increasing),
    check("demo learner improves on SC01 across 3 attempts", len(maya) == 3 and maya[0] < maya[1] < maya[2]),
    check("monitor-fixated learners look at the monitor most",
          t.groupby("profile").gaze_monitor.mean().idxmax() == "monitor_fixated"),
    check("equipment-hesitant learners waste the most touches",
          t.groupby("profile").no_effect_taps.mean().idxmax() == "equipment_hesitant"),
    check("Providers check Epic most before reaching the patient",
          w.groupby("role").epic_before_assessment.mean().idxmax() == "Provider"),
    check("RNs spend the largest share of steps on the vital sign monitor",
          w.groupby("role").lane_share_vitals.mean().idxmax() == "RN"),
    check("sessions that viewed COMET reach the rescue faster",
          w[cds].time_to_rescue.median() < w[~cds].time_to_rescue.median()),
    check("each role has a standard path of 6 to 13 steps",
          set(std.role) == {"Provider", "RN", "RT"} and std.groupby("role").step.max().between(6, 13).all()),
    check("every table is non-empty", all(len(pd.read_csv(f)) > 0 for f in P.glob("*.csv"))),
]
sys.exit(0 if all(results) else 1)
