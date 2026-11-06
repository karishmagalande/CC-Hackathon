import plotly.graph_objects as go
import streamlit as st

from lens import ui
from lens.data import all_tables, training_sessions
from lens.ui import C, MONO

T = all_tables()
S = training_sessions(T)

st.markdown(f"""
<div style="padding:26px 0 8px">
  <div class="lens-kicker">Cincinnati Children's · DISCOVER · Digital Health Hackathon 2026</div>
  <div style="font-size:44px;line-height:1.08;font-weight:400;margin:10px 0 12px;max-width:900px">
    The people who decide never put on the headset.<br>
    <span style="color:{C['spo2']}">So we bring the headset to them.</span></div>
  <div style="color:{C['muted']};font-size:16px;max-width:760px;line-height:1.55">
    DISCOVER Lens reads the telemetry a DISCOVER session already produces (every touch, every glance,
    every change in the simulated patient) and turns it into views for the three people who need it:
    the learner, the educator, and the partner.</div>
</div>""", unsafe_allow_html=True)

first, rep = S[S.attempt == 1], S[S.attempt >= 2]
ui.vitals_row([
    ("Sessions", f"{len(S)}", "", f"{S.learner_id.nunique()} learners · 5 scenarios", C["spo2"]),
    ("Score, first → repeat", f"{first.score.mean():.0f} → {rep.score.mean():.0f}", "", "mean", C["on_time"]),
    ("Patient unstable", f"{first.instability_sec.mean():.0f} → {rep.instability_sec.mean():.0f}", "s",
     "simulated, mean", C["sbp"]),
    ("Gaze samples", f"{len(T['fixations']):,}", "", "fixations logged", C["violet"]),
    ("Wasted touches", f"{len(T['taps']):,}", "", "on equipment controls", C["late"]),
])

cards = [
    ("views/replay.py", "Learner", "Ghost Run", "Replay one session against an expert run. See the moment "
     "the patient changed, where the learner was looking, and every action on one clock."),
    ("views/report_card.py", "Learner", "Readiness Profile", "Competency ratings that update after every "
     "action, a trend, and a next scenario chosen with a stated reason."),
    ("views/cohort.py", "Educator", "Cohort", "Learning curves, which critical actions fail most often, "
     "and whether repeat practice makes performance consistent."),
    ("views/workflows.py", "Educator · CDS team", "Role Workflows", "Every session as a path across Epic, "
     "patient, monitor, COMET and team. The standard path per role, where learners leave it, and what COMET changes."),
    ("views/value.py", "Administrator", "Value Ledger", "Staff hours and cost compared with mannequin "
     "simulation, with editable assumptions, plus the outcome chain."),
    ("views/friction.py", "Industry partner", "Friction Lens", "Which devices and controls cost clinicians "
     "time in a crisis, from eye-gaze and touch data. Exportable."),
    ("views/data_room.py", "Engineering", "Data & Pipeline", "Raw headset logs, the rules that turn them "
     "into clinical actions, and every table the views read."),
]
cols = st.columns(3)
for i, (page, who, title, body) in enumerate(cards):
    with cols[i % 3]:
        st.markdown(f'<div class="panel" style="min-height:150px;margin-top:10px"><div class="lens-kicker">{who}'
                    f'</div><div style="font-size:19px;margin:6px 0 6px">{title}</div><div style="color:'
                    f'{C["muted"]};font-size:13.5px;line-height:1.5">{body}</div></div>', unsafe_allow_html=True)
        st.page_link(page, label=f"Open {title}", icon=":material/arrow_forward:")

ui.section("", "How it fits", "")
steps = [("Headset", "DISCOVER session on Quest"), ("Telemetry log", "events · gaze · pose · vitals"),
         ("Rules", "interactions to clinical actions"), ("Metrics + ratings", "score · delta · Elo"),
         ("Views", "learner · educator · partner")]
flow = "".join(
    f'<div style="flex:1;text-align:center"><div style="font-family:var(--mono);font-size:11px;color:{C["accent"]}">'
    f'0{i + 1}</div><div style="font-size:15px;margin-top:4px">{a}</div><div style="color:{C["muted"]};'
    f'font-size:12px">{b}</div></div>' + ('<div style="color:#4A5670;align-self:center">→</div>'
                                         if i < len(steps) - 1 else "")
    for i, (a, b) in enumerate(steps))
st.markdown(f'<div class="panel" style="display:flex;gap:8px">{flow}</div>', unsafe_allow_html=True)
st.markdown('<div class="small-note" style="margin-top:10px">No VR engine changes needed. Point the pipeline at '
            'real DISCOVER exports and every view updates.</div>', unsafe_allow_html=True)
