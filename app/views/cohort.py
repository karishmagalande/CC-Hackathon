import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lens import ui
from lens.catalog import COMPETENCIES, SCENARIOS, ROLE_COLORS
from lens.data import all_tables, training_sessions
from lens.ui import C, COMP_COL, MONO

T = all_tables()
S = training_sessions(T)

ui.top("Program · Cohort", "Does practice change performance?",
       "Cohort level view for education directors and nurse leaders: learning curves, which actions "
       "fail most often, and whether repeat practice makes performance more consistent.")

f1, f2, f3 = st.columns(3)
cohorts = f1.multiselect("Cohort", sorted(S.cohort.unique()), default=sorted(S.cohort.unique()))
roles = f2.multiselect("Role", sorted(S.role.unique()), default=sorted(S.role.unique()))
scen = f3.selectbox("Scenario", ["All scenarios"] + list(SCENARIOS),
                    format_func=lambda x: x if x == "All scenarios" else SCENARIOS[x]["name"])
D = S[S.cohort.isin(cohorts) & S.role.isin(roles)]
if scen != "All scenarios":
    D = D[D.scenario_id == scen]
if D.empty:
    st.warning("No sessions match these filters.")
    st.stop()
D = D.assign(att=D.attempt.clip(upper=3).map({1: "1st", 2: "2nd", 3: "3rd+"}))
A = T["actions"].merge(D[["session_id", "att", "role"]], on="session_id")

a1 = D[D.attempt == 1]
a3 = D[D.attempt >= 3] if (D.attempt >= 3).any() else D[D.attempt == 2]
rate = lambda df: (df.time_to_rescue.notna() & (df.time_to_rescue <= df.scenario_id.map(
    lambda s: next(a["target_sec"] for a in SCENARIOS[s]["actions"] if a["id"] == SCENARIOS[s]["rescue"])))).mean()
ui.vitals_row([
    ("Learners", f"{D.learner_id.nunique()}", "", f"{len(D)} sessions", C["spo2"]),
    ("Median score", f"{a1.score.median():.0f} → {a3.score.median():.0f}", "", "first attempt to repeat",
     C["on_time"]),
    ("Rescue on time", f"{rate(a1) * 100:.0f} → {rate(a3) * 100:.0f}", "%", "share of runs", C["spo2"]),
    ("Unstable time", f"{a1.instability_sec.median():.0f} → {a3.instability_sec.median():.0f}", "s",
     "median, simulated patient", C["sbp"]),
    ("Score spread", f"{a1.score.std():.0f} → {a3.score.std():.0f}", "", "std dev, lower is more consistent",
     C["violet"]),
])

# ---------------------------------------------------------------- 01 curves
ui.section("01", "Learning curve", "each dot is one session")
c1, c2 = st.columns(2)
order = ["1st", "2nd", "3rd+"]


def strip(metric, title, colour, ytitle):
    fig = go.Figure()
    rng = np.random.default_rng(3)
    for i, att in enumerate(order):
        g = D[D.att == att]
        if g.empty:
            continue
        fig.add_trace(go.Box(x=[att] * len(g), y=g[metric], marker_color=colour, boxpoints=False,
                             line=dict(width=1), fillcolor="rgba(0,0,0,0)", showlegend=False))
        fig.add_trace(go.Scatter(x=[i + rng.uniform(-0.18, 0.18) for _ in range(len(g))], y=g[metric],
                                 mode="markers", marker=dict(size=6, color=colour, opacity=0.55),
                                 xaxis="x2", showlegend=False, customdata=g[["display_name", "role"]].values,
                                 hovertemplate="%{customdata[0]} · %{customdata[1]}<br>%{y:.0f}<extra></extra>"))
    med = D.groupby("att")[metric].median().reindex(order).dropna()
    fig.add_trace(go.Scatter(x=list(med.index), y=med.values, mode="lines+markers+text", showlegend=False,
                             text=[f"{v:.0f}" for v in med.values], textposition="middle right",
                             textfont=dict(family=MONO, size=12, color=C["text"]),
                             line=dict(color=C["text"], width=2), marker=dict(size=9, color=C["text"])))
    fig.update_layout(xaxis2=dict(overlaying="x", range=[-0.5, 2.5], visible=False),
                      title=dict(text=title, font=dict(size=13)), margin=dict(l=10, r=10, t=40, b=10))
    fig.update_xaxes(categoryorder="array", categoryarray=order, range=[-0.5, 2.5],
                     title=dict(text="attempt at the same scenario", font=dict(size=11, color=C["muted"])))
    fig.update_yaxes(title=dict(text=ytitle, font=dict(size=11, color=C["muted"])))
    return fig


with c1:
    ui.chart(strip("score", "Score", C["on_time"], "score"), height=360, key="c_score")
with c2:
    ui.chart(strip("instability_sec", "Time the simulated patient spent unstable", C["sbp"], "seconds"),
             height=360, key="c_unst")

# ---------------------------------------------------------------- 02 reliability
ui.section("02", "Action reliability", "share of runs where each critical action was done on time")
piv = (A.assign(ok=(A.status == "on_time").astype(float))
       .groupby(["scenario_id", "label", "competency", "att"]).ok.mean().unstack("att").reindex(columns=order))
piv = piv.reset_index()
piv["row"] = piv.scenario_id.map(lambda s: SCENARIOS[s]["short"]) + "  ·  " + piv.label
piv = piv.sort_values(["scenario_id"])
hm = go.Figure(go.Heatmap(
    z=piv[order].values * 100, x=order, y=piv.row, zmin=0, zmax=100,
    colorscale=[[0, "#3a1820"], [0.5, "#5a4a1c"], [0.8, "#1d4a3c"], [1, C["on_time"]]],
    texttemplate="%{z:.0f}", textfont=dict(family=MONO, size=11), xgap=3, ygap=2,
    colorbar=dict(title=dict(text="% on time", font=dict(size=10)), thickness=10, tickfont=dict(size=10)),
    hovertemplate="%{y}<br>%{x} attempt: %{z:.0f}% on time<extra></extra>"))
hm.update_yaxes(autorange="reversed", tickfont=dict(size=11, color=C["text"]))
hm.update_xaxes(side="top")
r1, r2 = st.columns([1.6, 1])
with r1:
    ui.chart(hm, height=max(340, 24 * len(piv) + 60), key="heat")
with r2:
    worst = (A[A.att == "1st"].groupby(["scenario_id", "label"]).status
             .apply(lambda x: (x == "missed").mean()).sort_values(ascending=False).head(5))
    st.markdown('<div class="panel"><div class="lens-kicker">Most often missed on a first attempt</div>' +
                "".join(f'<div style="display:flex;justify-content:space-between;margin-top:9px;font-size:14px">'
                        f'<span>{lab} <span style="color:{C["muted"]}">· {SCENARIOS[sc]["short"]}</span></span>'
                        f'<span style="font-family:var(--mono);color:{C["missed"]}">{v * 100:.0f}%</span></div>'
                        for (sc, lab), v in worst.items()) + "</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    by_role = D[D.attempt == 1].groupby("role").time_to_rescue.median().sort_values()
    rb = go.Figure(go.Bar(x=by_role.values, y=by_role.index, orientation="h", marker_color=C["spo2"],
                          text=[f"{v:.0f}s" for v in by_role.values], textposition="outside",
                          textfont=dict(family=MONO, size=10, color=C["muted"])))
    rb.update_layout(title=dict(text="Median time to rescue, first attempt, by role", font=dict(size=13)),
                     margin=dict(l=10, r=30, t=40, b=10))
    rb.update_xaxes(showticklabels=False, showgrid=False, range=[0, by_role.max() * 1.3])
    ui.chart(rb, height=260, key="role")
    wm = D.groupby(["role", "attempt"]).workflow_match.median().reset_index()
    wf = go.Figure()
    for role_, g in wm.groupby("role"):
        wf.add_trace(go.Scatter(x=g.attempt, y=g.workflow_match, mode="lines+markers", name=role_,
                                line=dict(color=ROLE_COLORS.get(role_, C["accent"]), width=2)))
    wf.update_layout(title=dict(text="Workflow match to role standard, by attempt", font=dict(size=13)),
                     legend=dict(orientation="h", y=-0.2), margin=dict(l=10, r=10, t=40, b=10))
    wf.update_xaxes(dtick=1)
    wf.update_yaxes(ticksuffix="%")
    ui.chart(wf, height=260, key="wfrole")
    st.page_link("views/workflows.py", label="Open Role Workflows", icon=":material/route:")

# ---------------------------------------------------------------- 03 who needs support
ui.section("03", "Who could use support", "learners whose lowest competency rating sits furthest below the cohort")
R = T["ratings"].merge(T["roster"], on="learner_id")
R = R[R.learner_id.isin(D.learner_id)]
med = R.groupby("competency").rating.median()
R["gap"] = R.rating - R.competency.map(med)
low = R.sort_values("gap").groupby("learner_id").head(1).head(8)
cells = "".join(
    f'<div class="rec" style="border-left-color:{COMP_COL[x.competency]}"><div style="display:flex;'
    f'justify-content:space-between"><span class="nm">{x.display_name}</span><span style="font-family:var(--mono);'
    f'color:{C["muted"]};font-size:12px">{x.role}</span></div><div class="why">{COMPETENCIES[x.competency]} '
    f'rated {x.rating:.0f}, {abs(x.gap):.0f} below the cohort median</div></div>' for x in low.itertuples())
st.markdown(f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px">'
            f'{cells}</div>', unsafe_allow_html=True)
