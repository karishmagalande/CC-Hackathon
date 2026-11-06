"""DISCOVER Lens entry point.  Run:  streamlit run app/main.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
st.set_page_config(page_title="DISCOVER Lens", page_icon="◎", layout="wide",
                   initial_sidebar_state="expanded")

from lens import ui  # noqa: E402
from lens.data import all_tables  # noqa: E402

ui.setup("DISCOVER Lens")
all_tables()  # builds data on first run

V = ROOT / "app" / "views"
pages = {
    "": [st.Page(V / "overview.py", title="Overview", icon=":material/radar:", default=True)],
    "Learner": [
        st.Page(V / "replay.py", title="Session Replay", icon=":material/timeline:", url_path="replay"),
        st.Page(V / "report_card.py", title="Report Card", icon=":material/assignment_ind:", url_path="report"),
    ],
    "Program": [
        st.Page(V / "cohort.py", title="Cohort", icon=":material/groups:", url_path="cohort"),
        st.Page(V / "workflows.py", title="Role Workflows", icon=":material/route:", url_path="workflows"),
        st.Page(V / "value.py", title="Value Ledger", icon=":material/account_balance:", url_path="value"),
    ],
    "Partner": [
        st.Page(V / "friction.py", title="Friction Lens", icon=":material/touch_app:", url_path="friction"),
    ],
    "System": [
        st.Page(V / "data_room.py", title="Data & Pipeline", icon=":material/database:", url_path="data"),
    ],
}
nav = st.navigation(pages)
with st.sidebar:
    st.markdown(
        '<div style="font-family:var(--mono);font-size:11px;letter-spacing:.16em;color:#4FC3F7">'
        'DISCOVER LENS</div><div style="color:#8391A8;font-size:12px;margin:2px 0 6px">'
        'The data layer beside the headset</div>', unsafe_allow_html=True)
nav.run()
