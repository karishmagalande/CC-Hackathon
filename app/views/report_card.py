import html as h

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lens import ratings, ui
from lens.catalog import COMPETENCIES, ROLE_COLORS, SCENARIOS
from lens.data import all_tables, training_sessions
from lens.ui import C, COMP_COL, MONO

T = all_tables()
S = training_sessions(T)
roster = T["roster"].set_index("learner_id")
names = roster.display_name.to_dict()

ui.top("Learner · Report Card", "Readiness Profile",
       "Everything one learner has done in DISCOVER, turned into competency ratings, a trend, "
       "and a reasoned next scenario.")

learners = sorted(S.learner_id.unique(), key=lambda x: names[x])
lid = st.selectbox("Learner", learners, index=learners.index("L001") if "L001" in learners else 0,
                   format_func=lambda x: f"{names[x]}  ·  {roster.loc[x, 'role']}  ·  {roster.loc[x, 'unit']}")
r = roster.loc[lid]
mine = S[S.learner_id == lid].sort_values("started_at")
cur = T["ratings"][T["ratings"].learner_id == lid].set_index("competency").rating
cohort_med = T["ratings"].groupby("competency").rating.median()
hist = T["rating_history"][T["rating_history"].learner_id == lid]
first_r = hist.sort_values("started_at").groupby("competency").head(1).set_index("competency").rating

strong = cur.idxmax()
weak = cur.idxmin()
first, last = mine.iloc[0], mine.iloc[-1]
ui.vitals_row([
    ("Sessions", f"{len(mine)}", "", f"{mine.scenario_id.nunique()} scenarios · since {first.started_at:%b %d}",
     C["spo2"]),
    ("Latest score", f"{last.score:.0f}", "/100", f"first was {first.score:.0f}",
     C["on_time"] if last.score >= 85 else C["late"] if last.score >= 65 else C["missed"]),
    ("Unstable time", f"{mine.instability_sec.iloc[-1]}", "s", f"first run {mine.instability_sec.iloc[0]}s",
     C["sbp"]),
    ("Strongest", COMPETENCIES[strong].split(" ")[0], "", f"rated {cur[strong]:.0f}", COMP_COL[strong]),
    ("Focus area", COMPETENCIES[weak].split(" ")[0], "", f"rated {cur[weak]:.0f}", COMP_COL[weak]),
    (f"{r.role} workflow", f"{last.workflow_match:.0f}", "%", f"match to the {r.role} standard · first "
     f"{first.workflow_match:.0f}%", ROLE_COLORS.get(r.role, C["accent"])),
])

# --------------------------------------------------------------- 01 ratings
ui.section("01", "Competency ratings", "every critical action is a match against its difficulty. "
           "1200 is where every learner starts")
a, b = st.columns([1, 1.35])
with a:
    cats = [COMPETENCIES[c] for c in COMPETENCIES]
    rad = go.Figure()
    rad.add_trace(go.Scatterpolar(r=[cohort_med[c] for c in COMPETENCIES] + [cohort_med["REC"]],
                                  theta=cats + [cats[0]], name="Cohort median",
                                  line=dict(color=C["ghost"], dash="dot", width=1.2), fill=None))
    rad.add_trace(go.Scatterpolar(r=[first_r.get(c, 1200) for c in COMPETENCIES] + [first_r.get("REC", 1200)],
                                  theta=cats + [cats[0]], name="After first session",
                                  line=dict(color=C["late"], width=1), opacity=0.6))
    rad.add_trace(go.Scatterpolar(r=[cur[c] for c in COMPETENCIES] + [cur["REC"]], theta=cats + [cats[0]],
                                  name="Now", line=dict(color=C["spo2"], width=2.2), fill="toself",
                                  fillcolor="rgba(79,195,247,0.12)"))
    rad.update_layout(polar=dict(bgcolor="rgba(0,0,0,0)",
                                 radialaxis=dict(range=[1100, 1450], gridcolor=C["line"], linecolor=C["line"],
                                                 showticklabels=False),
                                 angularaxis=dict(gridcolor=C["line"], linecolor=C["line"],
                                                  tickfont=dict(size=11, color=C["text"]))),
                      legend=dict(y=-0.08, x=0.5, xanchor="center"), margin=dict(l=90, r=90, t=30, b=30))
    ui.chart(rad, height=380, key="radar")
with b:
    ln = go.Figure()
    for c in COMPETENCIES:
        hh = hist[hist.competency == c].sort_values("started_at")
        ln.add_trace(go.Scatter(x=hh.started_at, y=hh.rating, mode="lines+markers", name=COMPETENCIES[c],
                                line=dict(color=COMP_COL[c], width=2 if c == weak else 1.3,
                                          shape="spline"), marker=dict(size=6)))
    ln.add_hline(y=1200, line=dict(color=C["faint"], dash="dot", width=1))
    ln.update_layout(legend=dict(y=1.14), margin=dict(l=10, r=10, t=40, b=10))
    ln.update_yaxes(title=dict(text="rating", font=dict(size=11, color=C["muted"])))
    ui.chart(ln, height=380, key="rlines")

# --------------------------------------------------------------- 02 history
ui.section("02", "Session history", "score and simulated patient outcome per run")
x1, x2 = st.columns([1.35, 1])
with x1:
    tab = mine.assign(
        Date=mine.started_at.dt.strftime("%b %d"),
        Scenario=mine.scenario_id.map(lambda x: SCENARIOS[x]["short"]),
        Attempt=mine.attempt, Score=mine.score.round(0),
        Rescue=mine.time_to_rescue.map(lambda v: "missed" if pd.isna(v) else f"{v:.0f}s"),
        Unstable=mine.instability_sec.map(lambda v: f"{v}s"),
        Monitor=(mine.gaze_monitor * 100).round(0).astype(int).astype(str) + "%",
        Workflow=mine.workflow_match.map(lambda v: f"{v:.0f}%"),
        COMET=mine.cds_viewed.astype(str).str.lower().map({"true": "viewed", "false": ""}),
    )[["Date", "Scenario", "Attempt", "Score", "Rescue", "Unstable", "Monitor", "Workflow", "COMET", "session_id"]]
    st.dataframe(tab.rename(columns={"session_id": "Session"}), hide_index=True, width="stretch",
                 column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100,
                                                                         format="%d")})
    st.page_link("views/replay.py", label="Open a session in Session Replay", icon=":material/arrow_forward:")
    st.page_link("views/workflows.py", label=f"Compare with the {r.role} standard workflow",
                 icon=":material/route:")
with x2:
    tr = go.Figure()
    for sc_id, g in mine.groupby("scenario_id"):
        tr.add_trace(go.Scatter(x=g.attempt, y=g.score, mode="lines+markers+text", name=SCENARIOS[sc_id]["short"],
                                text=[f"{v:.0f}" for v in g.score], textposition="top center",
                                textfont=dict(family=MONO, size=10, color=C["muted"]),
                                marker=dict(size=9)))
    tr.update_xaxes(dtick=1, title=dict(text="attempt", font=dict(size=11, color=C["muted"])))
    tr.update_yaxes(range=[0, 110])
    tr.update_layout(legend=dict(y=1.16), margin=dict(l=10, r=10, t=40, b=10))
    ui.chart(tr, height=300, key="trend")

# --------------------------------------------------------------- 03 next
ui.section("03", "Next scenario", "picked where you are likely, but not certain, to succeed")
recs, weakest = ratings.recommend(lid, T["ratings"],
                                  T["action_difficulty"], list(mine.scenario_id))
n1, n2 = st.columns([1.35, 1])
with n1:
    for i, rc in enumerate(recs):
        st.markdown(
            f'<div class="rec" style="border-left-color:{C["accent"] if i == 0 else C["line"]}">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<span class="nm">{"Recommended · " if i == 0 else ""}{h.escape(rc["name"])}</span>'
            f'{ui.tag("targets " + COMPETENCIES[rc["targets"]], COMP_COL[rc["targets"]])}</div>'
            f'<div class="why">{h.escape(rc["why"])}</div></div>', unsafe_allow_html=True)
with n2:
    sv = T["surveys"][T["surveys"].learner_id == lid].set_index("competency")
    dm = go.Figure()
    for c in COMPETENCIES:
        if c not in sv.index:
            continue
        p, q = sv.loc[c, "pre_confidence"], sv.loc[c, "post_confidence"]
        dm.add_trace(go.Scatter(x=[p, q], y=[COMPETENCIES[c]] * 2, mode="lines+markers", showlegend=False,
                                line=dict(color=C["line"], width=4),
                                marker=dict(size=[9, 12], color=[C["faint"], COMP_COL[c]])))
    dm.update_xaxes(range=[0.5, 5.5], dtick=1, title=dict(text="self-reported confidence, pre to post (1-5)",
                                                          font=dict(size=11, color=C["muted"])))
    dm.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    ui.chart(dm, height=250, key="conf")

# --------------------------------------------------------------- export
def report_html():
    rows = "".join(
        f"<tr><td>{x.started_at:%b %d}</td><td>{SCENARIOS[x.scenario_id]['name']}</td><td>{x.attempt}</td>"
        f"<td><b>{x.score:.0f}</b></td><td>{'missed' if pd.isna(x.time_to_rescue) else f'{x.time_to_rescue:.0f}s'}"
        f"</td><td>{x.instability_sec}s</td></tr>" for x in mine.itertuples())
    comps = "".join(
        f"<tr><td>{COMPETENCIES[c]}</td><td><b>{cur[c]:.0f}</b></td><td>{cohort_med[c]:.0f}</td>"
        f"<td>{cur[c] - first_r.get(c, 1200):+.0f}</td></tr>" for c in COMPETENCIES)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Report card · {names[lid]}</title>
<style>body{{font-family:Georgia,serif;color:#1b2230;max-width:760px;margin:40px auto;padding:0 20px}}
h1{{font-weight:400;margin:0}} .k{{font:11px/1.4 monospace;letter-spacing:.14em;color:#2f6f8f;text-transform:uppercase}}
table{{width:100%;border-collapse:collapse;margin:10px 0 24px;font:13px system-ui}} td,th{{border-bottom:1px solid #dde3ea;
padding:6px 4px;text-align:left}} th{{font-weight:600;color:#5a6577}} .note{{color:#6b7686;font:12px system-ui}}</style>
</head><body><div class="k">DISCOVER · learner report card</div><h1>{names[lid]}</h1>
<p class="note">{r.role} · {r.unit} · {r.cohort} · generated from synthetic sample data</p>
<h3>Competency ratings</h3><table><tr><th>Competency</th><th>Rating</th><th>Cohort median</th><th>Change</th></tr>
{comps}</table><h3>Sessions</h3><table><tr><th>Date</th><th>Scenario</th><th>Attempt</th><th>Score</th>
<th>Rescue</th><th>Unstable</th></tr>{rows}</table><h3>Recommended next</h3><p><b>{recs[0]['name']}</b>. {recs[0]['why']}</p>
<p class="note">Use your browser's Print, then Save as PDF.</p></body></html>"""


st.download_button("Download printable report card", report_html(), file_name=f"report_card_{lid}.html",
                   mime="text/html", icon=":material/download:")
