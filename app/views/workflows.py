import html

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lens import swimlane, ui, workflow
from lens.catalog import LANE_ORDER, LANES, ROLE_COLORS, ROLE_SUMMARY, ROLE_WORKFLOWS
from lens.data import all_tables, training_sessions
from lens.ui import C, MONO

T = all_tables()
S = training_sessions(T)
W = T["workflow_steps"]
STD = T["role_standard"]
ROLES = [r for r in ["Provider", "RN", "RT"] if r in set(S.role)]

ui.top("Program · Role Workflows", "Three typical workflows",
       "Every DISCOVER session turned into a path across information sources, overlaid per role to find the "
       "standard workflow, then used to show where learners leave it and where a CDS tool changes it.")

lanes_of = W.sort_values(["session_id", "step"]).groupby("session_id").lane.apply(list).to_dict()
std_of = {r: STD[STD.role == r].sort_values("step").lane.tolist() for r in ROLES}
S = S.assign(path=S.session_id.map(lambda x: lanes_of.get(x, [])))
cds = S.cds_viewed.astype(str).str.lower() == "true"
with_c, without_c = S[cds], S[~cds]

ui.vitals_row([
    ("Sessions mapped", f"{len(S)}", "", f"{S.learner_id.nunique()} learners · {len(W):,} workflow steps", C["spo2"]),
    *[(f"{r} workflow match", f"{S[S.role == r].workflow_match.median():.0f}", "%",
       f"{(S.role == r).sum()} sessions · standard {len(std_of[r])} steps", ROLE_COLORS[r]) for r in ROLES],
    ("COMET effect", f"{without_c.time_to_rescue.median() - with_c.time_to_rescue.median():.0f}", "s faster",
     f"median time to rescue, {len(with_c)} with vs {len(without_c)} without", C["violet"]),
])

# ---------------------------------------------------------------- 01 three typical workflows
ui.section("01", "Three typical workflows", "faint lines are individual sessions; the thick numbered line is the "
           "standard path, the session closest to all others of that role")
cols = st.columns(len(ROLES))
per = S.groupby("role")
epic_b = per.epic_before_assessment.mean()
bedside = per.time_to_bedside.median()
share = per[[f"lane_share_{k}" for k in LANE_ORDER]].mean()
for col, r in zip(cols, ROLES):
    with col:
        g = S[S.role == r]
        ui.chart(swimlane.overlay_map(list(g.path), std_of[r], ROLE_COLORS[r]), key=f"ov_{r}")
        st.markdown(f'<div style="background:{ROLE_COLORS[r]};color:#0A0F1A;text-align:center;font-weight:600;'
                    f'padding:7px;border-radius:6px;margin:2px 0 10px">{r}</div>', unsafe_allow_html=True)
        if r == "Provider":
            data_line = (f"Checks Epic {epic_b[r]:.1f} times before reaching the patient (RN {epic_b.get('RN', 0):.1f}, "
                         f"RT {epic_b.get('RT', 0):.1f}) and reaches the bedside at {bedside[r]:.0f}s.")
        elif r == "RN":
            data_line = (f"The vital sign monitor is {share.loc[r, 'lane_share_vitals'] * 100:.0f}% of steps, the "
                         f"highest of the three roles.")
        else:
            data_line = (f"{share.loc[r, 'lane_share_assessment'] * 100:.0f}% of steps are patient or equipment "
                         f"assessment and {share.loc[r, 'lane_share_communication'] * 100:.0f}% are communication; "
                         f"no Epic before the bedside.")
        st.markdown(f'<div style="font-size:14px;line-height:1.5">• {html.escape(ROLE_SUMMARY[r])}</div>'
                    f'<div style="font-size:14px;line-height:1.5;margin-top:6px;color:{C["accent"]}">• '
                    f'{html.escape(data_line)}</div>', unsafe_allow_html=True)
        steps = STD[STD.role == r].sort_values("step")
        st.markdown('<div class="panel" style="margin-top:10px">' + "".join(
            f'<div style="display:flex;gap:8px;padding:3px 0;font-size:12.5px"><span style="font-family:var(--mono);'
            f'color:{C["muted"]};min-width:18px">{x.step}</span><span style="color:{LANES[x.lane]["color"]};'
            f'min-width:118px">{LANES[x.lane]["label"]}</span><span style="color:{C["muted"]}">'
            f'{html.escape(str(x.what))[:34]}</span></div>' for x in steps.itertuples()) + "</div>",
            unsafe_allow_html=True)

# ---------------------------------------------------------------- 02 opportunity areas
ui.section("02", "Where learners leave the standard", "share of sessions that skip each step of their role's "
           "standard path. These are the opportunity areas for a CDS prompt")
cols = st.columns(len(ROLES))
for col, r in zip(cols, ROLES):
    g = S[S.role == r]
    std = std_of[r]
    miss = np.zeros(len(std))
    for p in g.path:
        for k in workflow.missing_steps(workflow.core(p), std):
            miss[k] += 1
    miss = miss / max(len(g), 1)
    lab = STD[STD.role == r].sort_values("step")
    ylab = [f"{x.step}  {LANES[x.lane]['label']}" for x in lab.itertuples()]
    fig = go.Figure(go.Bar(y=ylab, x=miss * 100, orientation="h",
                           marker_color=[LANES[k]["color"] for k in std],
                           text=[f"{v * 100:.0f}%" for v in miss], textposition="outside",
                           textfont=dict(family=MONO, size=10.5, color=C["muted"]),
                           customdata=lab.what, hovertemplate="%{y}<br>%{customdata}<br>%{x:.0f}% skip<extra></extra>"))
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=11, color=C["text"]))
    fig.update_xaxes(range=[0, max(miss.max() * 140, 10)], showgrid=False, showticklabels=False)
    fig.update_layout(title=dict(text=r, font=dict(size=13, color=ROLE_COLORS[r])), margin=dict(l=10, r=20, t=36, b=10))
    with col:
        ui.chart(fig, height=330, key=f"miss_{r}")
        worst = int(np.argmax(miss))
        st.markdown(f'<div class="small-note">Most skipped: step {worst + 1}, '
                    f'{html.escape(LANES[std[worst]]["label"].lower())} ({html.escape(str(lab.what.iloc[worst]))}), '
                    f'{miss[worst] * 100:.0f}% of sessions</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 03 CDS
ui.section("03", "What COMET changes", "sessions where the learner looked at the COMET risk score after the patient "
           "began to change, against sessions where they did not")
c1, c2 = st.columns([1.3, 1])
with c1:
    metrics_ = [("Time to rescue (s)", "time_to_rescue", "median"), ("Score", "score", "mean"),
                ("Patient unstable (s)", "instability_sec", "median"), ("Workflow match (%)", "workflow_match", "median")]
    fig = go.Figure()
    for name, grp, colr in [("Without COMET", without_c, C["faint"]), ("With COMET", with_c, C["violet"])]:
        vals = [getattr(grp[m], agg)() for _, m, agg in metrics_]
        fig.add_trace(go.Bar(x=[m[0] for m in metrics_], y=vals, name=name, marker_color=colr,
                             text=[f"{v:.0f}" for v in vals], textposition="outside",
                             textfont=dict(family=MONO, size=11, color=C["text"])))
    fig.update_layout(barmode="group", legend=dict(y=1.12), margin=dict(l=10, r=10, t=40, b=10))
    fig.update_yaxes(showticklabels=False, showgrid=False)
    ui.chart(fig, height=330, key="cds_bars")
with c2:
    after = W.sort_values(["session_id", "step"]).copy()
    after["next_lane"] = after.groupby("session_id").lane.shift(-1)
    nxt = after[after.lane == "comet"].next_lane.value_counts(normalize=True)
    when = with_c.cds_view_after_change.median()
    gap = with_c.cds_to_next_action.median()
    rows = "".join(f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid '
                   f'{C["line"]};font-size:13.5px"><span style="color:{LANES[k]["color"]}">{LANES[k]["label"]}</span>'
                   f'<span style="font-family:var(--mono)">{v * 100:.0f}%</span></div>' for k, v in nxt.items())
    st.markdown(
        f'<div class="panel"><div class="lens-kicker">Placement</div>'
        f'<div style="font-size:14px;margin:6px 0 10px;line-height:1.5">COMET was looked at a median <b>{when:.0f}s</b> '
        f'after the patient began to change, and the next critical action followed <b>{gap:.0f}s</b> later. '
        f'What learners did next:</div>{rows}</div>', unsafe_allow_html=True)
    st.markdown('<div class="small-note" style="margin-top:8px">Hypothesised CDS workflow change, measured on '
                'simulated sessions. Confirm with the DISCOVER team before drawing conclusions.</div>',
                unsafe_allow_html=True)

# ---------------------------------------------------------------- 04 lane mix + hypothesis check
ui.section("04", "Where each role gets its information", "share of workflow steps per information source, and the "
           "observed standard path against the path hypothesised from VR observation")
l1, l2 = st.columns([1.2, 1])
with l1:
    fig = go.Figure()
    for k in LANE_ORDER:
        fig.add_trace(go.Bar(y=ROLES, x=[share.loc[r, f"lane_share_{k}"] * 100 for r in ROLES], orientation="h",
                             name=LANES[k]["label"], marker_color=LANES[k]["color"],
                             text=[f"{share.loc[r, f'lane_share_{k}'] * 100:.0f}%" for r in ROLES],
                             textposition="inside", textfont=dict(size=10.5, color="#0A0F1A")))
    fig.update_layout(barmode="stack", legend=dict(orientation="h", y=1.32, x=0), margin=dict(l=10, r=10, t=70, b=10))
    fig.update_xaxes(range=[0, 100], showgrid=False, title=dict(text="% of steps", font=dict(size=11, color=C["muted"])))
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=12, color=C["text"]))
    ui.chart(fig, height=300, key="mix")
with l2:
    def chips(seq):
        return "".join(f'<span style="display:inline-block;width:14px;height:14px;border-radius:3px;margin-right:3px;'
                       f'background:{LANES[k]["color"]}" title="{LANES[k]["label"]}"></span>' for k in seq)
    rows = "".join(
        f'<div style="padding:8px 0;border-bottom:1px solid {C["line"]}"><div style="display:flex;justify-content:'
        f'space-between"><b style="color:{ROLE_COLORS[r]}">{r}</b><span style="font-family:var(--mono);'
        f'color:{C["accent"]}">{workflow.match(std_of[r], ROLE_WORKFLOWS[r]):.0f}% alike</span></div>'
        f'<div class="small-note" style="margin-top:4px">observed  {chips(std_of[r])}</div>'
        f'<div class="small-note">hypothesis {chips(ROLE_WORKFLOWS[r])}</div></div>' for r in ROLES)
    legend = " ".join(f'<span style="color:{LANES[k]["color"]}">■ {LANES[k]["label"]}</span>' for k in LANE_ORDER)
    st.markdown(f'<div class="panel"><div class="lens-kicker">Observed vs hypothesised standard</div>{rows}'
                f'<div style="font-size:11px;margin-top:8px">{legend}</div></div>', unsafe_allow_html=True)
