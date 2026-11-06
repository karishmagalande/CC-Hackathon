"""Cached access to the processed tables. Builds them on first run if missing."""
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
TABLES = ["sessions", "actions", "events", "taps", "fixations", "poses", "vitals", "states",
          "device_dwell", "rating_history", "ratings", "action_difficulty", "roster", "surveys",
          "workflow_steps", "role_standard"]


def ensure_built():
    if all((PROC / f"{t}.csv").exists() for t in TABLES):
        return
    with st.spinner("First run: generating sample telemetry and building tables..."):
        if not (ROOT / "data" / "raw" / "roster.csv").exists():
            subprocess.run([sys.executable, str(ROOT / "generator" / "make_raw.py")], check=True)
        subprocess.run([sys.executable, str(ROOT / "pipeline" / "build.py")], check=True)


@st.cache_data(show_spinner=False)
def load(name):
    df = pd.read_csv(PROC / f"{name}.csv")
    for col in ("started_at",):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    return df


def all_tables():
    ensure_built()
    return {t: load(t) for t in TABLES}


def training_sessions(T):
    s = T["sessions"]
    s = s[s["mode"] == "training"].merge(T["roster"], on="learner_id", how="left")
    return s


def session_parts(T, sid):
    return {k: T[k][T[k].session_id == sid] for k in
            ["actions", "events", "taps", "fixations", "poses", "vitals", "states"]}
