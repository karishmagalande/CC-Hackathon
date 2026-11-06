import json
import subprocess
import sys

import pandas as pd
import streamlit as st

from lens import ui
from lens.catalog import SCENARIOS
from lens.data import PROC, ROOT, TABLES, all_tables
from lens.ui import C

T = all_tables()

ui.top("System · Data & Pipeline", "From headset log to dashboard",
       "What the prototype reads, how raw interactions become clinical actions, and every table behind the views.")

ui.section("01", "A raw session log", "one JSON record per line, the way a headset stream arrives")
logs = sorted((ROOT / "data" / "raw" / "sessions").glob("*.jsonl"))
pick = st.selectbox("Log file", [p.name for p in logs], index=min(5, len(logs) - 1))
lines = open(ROOT / "data" / "raw" / "sessions" / pick).read().splitlines()
kinds = pd.Series([json.loads(l)["k"] for l in lines]).value_counts()
c1, c2 = st.columns([1.6, 1])
with c1:
    sample = [l for l in lines if '"k":"evt"' in l or '"k":"meta"' in l or '"k":"state"' in l][:8]
    sample += [l for l in lines if '"k":"fix"' in l][:3] + [l for l in lines if '"k":"vit"' in l][:2]
    sample += [l for l in lines if '"k":"tap"' in l][:2]
    st.code("\n".join(sample), language="json")
with c2:
    st.markdown('<div class="panel"><div class="lens-kicker">Records in this log</div>' +
                "".join(f'<div style="display:flex;justify-content:space-between;margin-top:6px;font-size:14px">'
                        f'<span>{k}</span><span style="font-family:var(--mono);color:{C["muted"]}">{v:,}</span></div>'
                        for k, v in kinds.items()) + "</div>", unsafe_allow_html=True)

ui.section("02", "Action rules", "a critical action is the first raw interaction that matches its rule. "
           "Educators edit these in lens/catalog.py")
sc = st.selectbox("Scenario", list(SCENARIOS), format_func=lambda x: SCENARIOS[x]["name"])
rules = pd.DataFrame([{"action": a["label"], "competency": a["comp"], "verb": a["rule"]["verb"],
                       "object": a["rule"]["object"], "target": a["rule"]["target"],
                       "target_sec": a["target_sec"], "weight": a["weight"],
                       "rescue": "yes" if a["id"] == SCENARIOS[sc]["rescue"] else ""}
                      for a in SCENARIOS[sc]["actions"]])
st.dataframe(rules, hide_index=True, width="stretch")
st.markdown('<div class="small-note">Target times are placeholders for the prototype. '
            'Replace them with the DISCOVER team\'s scenario definitions.</div>', unsafe_allow_html=True)

st.markdown("**Workflow lanes.** Each logged interaction is also placed in one information lane "
            "(lens/catalog.py, `event_lane`). Consecutive steps in the same lane merge into one step.")
st.dataframe(pd.DataFrame([
    {"lane": "Epic", "logged as": "use / read / check on object epic", "example": "check orders, meds, labs"},
    {"lane": "Patient assessment", "logged as": "anything on patient or penlight, any inspect", "example": "touch chest, check pulses"},
    {"lane": "Vital sign monitor", "logged as": "check on object monitor", "example": "read vitals, watch trend"},
    {"lane": "COMET / in-room view", "logged as": "any interaction with object comet", "example": "view risk score (CDS touchpoint)"},
    {"lane": "Communication", "logged as": "communicate / use on team or phone", "example": "hand-off, call for help"},
]), hide_index=True, width="stretch")

ui.section("03", "Processed tables", "")
counts = pd.DataFrame([{"table": t, "rows": len(T[t]), "columns": len(T[t].columns)} for t in TABLES])
t1, t2 = st.columns([1, 2.2])
with t1:
    st.dataframe(counts, hide_index=True, width="stretch", height=520)
with t2:
    tname = st.selectbox("Preview table", TABLES)
    st.dataframe(T[tname].head(300), hide_index=True, width="stretch", height=380)
    st.download_button(f"Download {tname}.csv", (PROC / f"{tname}.csv").read_bytes(), file_name=f"{tname}.csv",
                       mime="text/csv", icon=":material/download:")

ui.section("04", "Regenerate", "new random cohort with a different seed")
r1, r2 = st.columns([1, 3])
seed = r1.number_input("Seed", 1, 9999, 7)
if r2.button("Regenerate sample data", icon=":material/refresh:"):
    with st.spinner("Generating logs and rebuilding tables..."):
        subprocess.run([sys.executable, str(ROOT / "generator" / "make_raw.py"), "--seed", str(int(seed))], check=True)
        subprocess.run([sys.executable, str(ROOT / "pipeline" / "build.py")], check=True)
    st.cache_data.clear()
    st.success("Done. Every page now reads the new data.")
