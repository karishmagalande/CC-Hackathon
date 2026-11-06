import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from lens import debrief, metrics, swimlane, ui
from lens.catalog import LANES, ROLE_COLORS, ROOM_OBJECTS, ROOM_SIZE, SCENARIOS, object_group
from lens.data import all_tables, session_parts, training_sessions
from lens.ui import C, GAZE, MONO, SANS

T = all_tables()
S = training_sessions(T)
roster = T["roster"].set_index("learner_id")

ui.top("Learner · Session Replay", "Ghost Run",
       "One headset session, laid out so someone who was not in the room can see what happened, "
       "when, and how it compares with an expert run of the same scenario.")

# ---------------------------------------------------------------- selectors
names = roster.display_name.to_dict()
learners = sorted(S.learner_id.unique(), key=lambda x: names[x])
default_l = learners.index("L001") if "L001" in learners else 0
qp = st.query_params
c1, c2, c3 = st.columns([1.1, 1.6, 1])
lid = c1.selectbox("Learner", learners, index=learners.index(qp["l"]) if qp.get("l") in learners else default_l,
                   format_func=lambda x: f"{names[x]}  ·  {roster.loc[x, 'role']}")
mine = S[S.learner_id == lid].sort_values("started_at")
labels = {r.session_id: f"{SCENARIOS[r.scenario_id]['short']}  ·  attempt {r.attempt}  ·  {r.started_at:%b %d}"
          for r in mine.itertuples()}
sids = list(labels)
sid = c2.selectbox("Session", sids, index=sids.index(qp["s"]) if qp.get("s") in sids else 0,
                   format_func=labels.get)
compare = c3.selectbox("Compare against", ["Expert reference", "Previous attempt"])

s = mine[mine.session_id == sid].iloc[0]
sc = SCENARIOS[s.scenario_id]
P = session_parts(T, sid)
acts = P["actions"].sort_values("order")
onset = float(s.onset_t)

# comparison run
if compare == "Previous attempt":
    prev = mine[(mine.scenario_id == s.scenario_id) & (mine.attempt == s.attempt - 1)]
    if prev.empty:
        st.info("No previous attempt of this scenario. Showing the expert reference.")
        compare = "Expert reference"
if compare == "Previous attempt":
    cmp_sid = prev.iloc[0].session_id
    cmp_acts = T["actions"][T["actions"].session_id == cmp_sid]
    cmp_rel = dict(zip(cmp_acts.action_id, cmp_acts.t_rel))
    cmp_name = f"Attempt {s.attempt - 1}"
else:
    cmp_rel = dict(zip(acts.action_id, acts.expert_rel))
    cmp_name = "Expert"
acts = acts.assign(cmp_rel=acts.action_id.map(cmp_rel))
acts["cmp_delta"] = acts.t_rel - acts.cmp_rel

ref = T["sessions"][T["sessions"].session_id == f"REF-{s.scenario_id}"].iloc[0]
st.markdown(f'<div class="small-note">{sc["name"].upper()} · {sc["patient"]} · '
            f'patient begins to change at {debrief.mmss(onset)}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- header strip
def fmt(v, unit="s"):
    return "--" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.0f}"

resc = s.time_to_rescue
ref_resc = ref.time_to_rescue
done_delta = acts.cmp_delta.dropna().sum()
ui.vitals_row([
    ("Score", f"{s.score:.0f}", "/100", f"{s.on_time} on time · {s.late} late · {s.missed} missed",
     C["on_time"] if s.score >= 85 else C["late"] if s.score >= 65 else C["missed"]),
    ("Cue to action", fmt(s.cue_to_action), "s", "change to first critical action", C["rr"]),
    ("Time to rescue", fmt(resc), "s",
     "rescue not done" if pd.isna(resc) else f"expert {ref_resc:.0f}s", C["spo2"]),
    ("Unstable time", f"{s.instability_sec}", "s", f"lowest SpO2 {s.min_spo2}%", C["sbp"]),
    (f"Delta vs {cmp_name.lower()}", f"{done_delta:+.0f}", "s", "summed over completed actions", C["ghost"]),
    ("Missed cues", f"{s.missed_cues}", "", f"{s.missed_cue_sec:.0f}s unstable and unwatched", C["violet"]),
])

# ---------------------------------------------------------------- 01 ghost run
ui.section("01", "Ghost run", f"each critical action, learner against {cmp_name.lower()}, "
           "in seconds after the patient starts to change")
gl, gr = st.columns([1.75, 1])
fig = go.Figure()
lane_l, lane_c = 1.0, 0.0
for a in acts.itertuples():
    y_lab = a.order
    if not pd.isna(a.cmp_rel) and not pd.isna(a.t_rel):
        fig.add_trace(go.Scatter(x=[a.cmp_rel, a.t_rel], y=[lane_c, lane_l], mode="lines",
                                 line=dict(color=C[a.status], width=1.3, dash="dot"),
                                 hoverinfo="skip", showlegend=False))
# target windows on the learner lane
for a in acts.itertuples():
    fig.add_trace(go.Scatter(x=[a.target_sec, a.target_sec], y=[lane_l + 0.1, lane_l + 0.22], mode="lines",
                             line=dict(color=C["faint"], width=1), hoverinfo="skip", showlegend=False))
fig.add_trace(go.Scatter(
    x=acts.cmp_rel, y=[lane_c] * len(acts), mode="markers+text", text=acts.order.astype(str),
    textposition="bottom center", textfont=dict(family=MONO, size=10, color=C["muted"]),
    marker=dict(size=13, color=C["bg"], line=dict(color=C["ghost"], width=1.6), symbol="circle"),
    name=cmp_name, customdata=acts[["label", "cmp_rel"]].values,
    hovertemplate="%{customdata[0]}<br>" + cmp_name + " %{customdata[1]:.0f}s<extra></extra>"))
done = acts.dropna(subset=["t_rel"])
fig.add_trace(go.Scatter(
    x=done.t_rel, y=[lane_l] * len(done), mode="markers+text", text=done.order.astype(str),
    textposition="top center", textfont=dict(family=MONO, size=10, color=C["text"]),
    marker=dict(size=15, color=[C[x] for x in done.status], line=dict(color=C["bg"], width=1.5)),
    name=names[lid], customdata=done[["label", "t_rel", "target_sec", "status"]].values,
    hovertemplate="%{customdata[0]}<br>%{customdata[1]:.0f}s (target %{customdata[2]}s)"
                  "<br>%{customdata[3]}<extra></extra>"))
miss = acts[acts.t_rel.isna()]
if len(miss):
    xmax = max(acts.t_rel.max(skipna=True) if done.size else 0, acts.target_sec.max()) + 15
    fig.add_trace(go.Scatter(
        x=[xmax] * len(miss), y=[lane_l - 0.28 * (i % 2) for i in range(len(miss))], mode="markers+text",
        text=[f"#{o} missed" for o in miss.order], textposition="middle right",
        textfont=dict(family=MONO, size=10, color=C["missed"]),
        marker=dict(size=11, symbol="x-thin", line=dict(color=C["missed"], width=2)),
        name="Missed", hovertext=miss.label, hoverinfo="text"))
fig.update_yaxes(tickvals=[lane_c, lane_l], ticktext=[cmp_name.upper(), names[lid].upper()],
                 range=[-0.55, 1.5], showgrid=False,
                 tickfont=dict(family=MONO, size=11, color=C["muted"]))
xr = max(acts.t_rel.max(skipna=True) if len(done) else 0, acts.cmp_rel.max(), acts.target_sec.max())
fig.update_xaxes(title=dict(text="seconds after change", font=dict(size=11, color=C["muted"])),
                 range=[-5, xr + (60 if len(miss) else 15)])
fig.update_layout(legend=dict(y=1.15))
with gl:
    ui.chart(fig, height=300, key="ghost")

with gr:
    d = acts.copy()
    d["lab"] = d.order.astype(str) + "  " + d.label
    d["val"] = d.cmp_delta.fillna(0)
    bar = go.Figure(go.Bar(
        y=d.lab, x=d.val, orientation="h",
        marker=dict(color=[C[x] for x in d.status]),
        text=[("missed" if pd.isna(v) else f"{v:+.0f}s") for v in d.cmp_delta],
        textposition="outside", textfont=dict(family=MONO, size=11, color=C["muted"]),
        hovertemplate="%{y}<br>%{x:+.0f}s<extra></extra>"))
    bar.add_vline(x=0, line=dict(color=C["ghost"], width=1))
    bar.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=11, color=C["text"],
                     family=SANS))
    bar.update_xaxes(title=dict(text=f"seconds behind {cmp_name.lower()}", font=dict(size=11, color=C["muted"])))
    vmax = max(d.val.max(), 10)
    bar.update_xaxes(range=[min(d.val.min(), 0) * 1.25 - 5, vmax * 1.3])
    bar.update_layout(margin=dict(l=10, r=10, t=30, b=10))
    ui.chart(bar, height=300, key="delta")

# ---------------------------------------------------------------- 02 cue to action
ui.section("02", "Cue to action", "patient state, where the learner was looking, and what they did, on one clock")
v = P["vitals"]
fx = P["fixations"].copy()
fx["group"] = fx.object.map(object_group)
cues = metrics.missed_cues(fx, v, s.scenario_id, onset)
unst = metrics.unstable_mask(v, s.scenario_id).values

fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                    row_heights=[0.58, 0.14, 0.28], specs=[[{"secondary_y": True}], [{}], [{}]])
fig.add_trace(go.Scatter(x=v.t, y=v.spo2, name="SpO2 %", line=dict(color=C["spo2"], width=2)), 1, 1)
fig.add_trace(go.Scatter(x=v.t, y=v.hr, name="HR", line=dict(color=C["hr"], width=1.4)), 1, 1, secondary_y=True)
fig.add_trace(go.Scatter(x=v.t, y=v.rr, name="RR", line=dict(color=C["rr"], width=1.1, dash="dot"),
                         visible="legendonly"), 1, 1, secondary_y=True)
fig.add_trace(go.Scatter(x=v.t, y=v.sbp, name="SBP", line=dict(color=C["sbp"], width=1.1, dash="dot"),
                         visible="legendonly"), 1, 1, secondary_y=True)
# unstable bands
runs, start = [], None
for i, u in enumerate(unst):
    if u and start is None:
        start = i
    if (not u or i == len(unst) - 1) and start is not None:
        runs.append((v.t.iloc[start], v.t.iloc[i]))
        start = None
for a0, a1 in runs:
    fig.add_vrect(x0=a0, x1=a1, fillcolor=C["sbp"], opacity=0.07, line_width=0, row=1, col=1)
for a0, a1 in cues:
    fig.add_vrect(x0=a0, x1=a1, fillcolor=C["violet"], opacity=0.22, line_width=0, row=2, col=1)
# attention ribbon
for g, col in GAZE.items():
    f = fx[fx.group == g]
    fig.add_trace(go.Bar(x=f.t1 - f.t0, base=f.t0, y=["gaze"] * len(f), orientation="h",
                         marker=dict(color=col, line_width=0), name=f"looking at {g}",
                         customdata=f.object, width=0.9,
                         hovertemplate="%{customdata}<br>%{base:.1f}s<extra></extra>"), 2, 1)
# actions
evt = acts.dropna(subset=["t_abs"])
fig.add_trace(go.Scatter(x=evt.t_abs, y=[1] * len(evt), mode="markers+text", text=evt.label,
                         textposition=["top center" if i % 2 == 0 else "bottom center" for i in range(len(evt))], textfont=dict(size=10, color=C["text"]),
                         marker=dict(size=11, symbol="diamond", color=[C[x] for x in evt.status]),
                         name="critical action", hovertemplate="%{text}<br>%{x:.1f}s<extra></extra>"), 3, 1)
tp = P["taps"]
if len(tp):
    fig.add_trace(go.Scatter(x=tp.t, y=[0.3] * len(tp), mode="markers",
                             marker=dict(size=7, symbol="line-ns-open", color=C["late"], line=dict(width=1.5)),
                             name="touch, no effect", customdata=tp[["object", "control"]].values,
                             hovertemplate="%{customdata[0]} · %{customdata[1]}<br>%{x:.1f}s<extra></extra>"), 3, 1)
for r in range(1, 4):
    fig.add_vline(x=onset, line=dict(color=C["rr"], width=1, dash="dash"), row=r, col=1)
    if not pd.isna(resc):
        fig.add_vline(x=onset + resc, line=dict(color=C["spo2"], width=1, dash="dash"), row=r, col=1)
fig.add_annotation(x=onset, y=1.02, yref="paper", text="change", showarrow=False,
                   font=dict(family=MONO, size=10, color=C["rr"]), xanchor="left")
if not pd.isna(resc):
    fig.add_annotation(x=onset + resc, y=1.02, yref="paper", text="rescue", showarrow=False,
                       font=dict(family=MONO, size=10, color=C["spo2"]), xanchor="left")
fig.update_yaxes(title_text="SpO2", range=[55, 101], row=1, col=1, secondary_y=False)
fig.update_yaxes(title_text="HR", row=1, col=1, secondary_y=True, showgrid=False, tickformat=".0f")
fig.update_yaxes(showticklabels=False, showgrid=False, row=2, col=1)
fig.update_yaxes(showticklabels=False, showgrid=False, range=[0.1, 1.9], row=3, col=1)
fig.update_xaxes(title_text="session time (s)", row=3, col=1)
fig.update_layout(barmode="overlay", bargap=0, legend=dict(y=1.1))
ui.chart(fig, height=520, key="cue")
st.markdown('<div class="small-note">Red bands: patient outside safe ranges. Violet: unstable and nobody '
            'looking at patient or monitor for 6 s or more. Ticks: touches on equipment that did nothing.</div>',
            unsafe_allow_html=True)

# ---------------------------------------------------------------- 03 room replay
ui.section("03", "Room replay", "top-down view rebuilt from head position and gaze. Press play or drag the slider")
rl, rr = st.columns([1.6, 1])
poses = P["poses"].set_index("t")
fx_sorted = fx.sort_values("t0")
step = 2
times = list(range(0, int(s.duration) + 1, step))


def gaze_at(t):
    hit = fx_sorted[(fx_sorted.t0 <= t) & (fx_sorted.t1 > t)]
    return hit.object.iloc[0] if len(hit) else None


obj_df = pd.DataFrame([{"obj": k, "label": v["label"], "x": v["xy"][0], "y": v["xy"][1], "group": v["group"]}
                       for k, v in ROOM_OBJECTS.items() if k not in ("penlight", "elsewhere")])
base = [
    go.Scatter(x=obj_df.x, y=obj_df.y, mode="markers+text", text=obj_df.label, textposition="bottom center",
               textfont=dict(size=10, color=C["muted"]),
               marker=dict(size=[26 if o == "patient" else 12 for o in obj_df.obj], symbol="square",
                           color=[GAZE[g] for g in obj_df.group], opacity=0.35,
                           line=dict(color=[GAZE[g] for g in obj_df.group], width=1)),
               hoverinfo="text", showlegend=False),
]


def frame_traces(t):
    lo = max(0, t - 12)
    trail = poses.loc[lo:t]
    x, y = (poses.loc[t, "x"], poses.loc[t, "y"]) if t in poses.index else (np.nan, np.nan)
    g = gaze_at(t)
    gx, gy = ROOM_OBJECTS.get(g or "elsewhere", ROOM_OBJECTS["elsewhere"])["xy"]
    gc = GAZE[object_group(g)] if g else C["faint"]
    return [
        go.Scatter(x=trail.x, y=trail.y, mode="lines", line=dict(color=C["accent"], width=2), opacity=0.5,
                   showlegend=False, hoverinfo="skip"),
        go.Scatter(x=[x, gx], y=[y, gy], mode="lines", line=dict(color=gc, width=2, dash="dot"),
                   showlegend=False, hoverinfo="skip"),
        go.Scatter(x=[x], y=[y], mode="markers", marker=dict(size=16, color=C["accent"],
                   line=dict(color=C["bg"], width=2)), showlegend=False, hoverinfo="skip"),
    ]


vit_idx = v.set_index("t")


def frame_title(t):
    row = vit_idx.loc[min(t, vit_idx.index.max())]
    g = gaze_at(t) or "-"
    phase = "baseline" if t < onset else "changing"
    return (f"<span style='font-family:var(--mono)'>{debrief.mmss(t)}  ·  SpO2 {row.spo2}  ·  HR {row.hr}"
            f"  ·  looking at {g}  ·  {phase}</span>")


frames = [go.Frame(data=base + frame_traces(t), name=str(t),
                   layout=go.Layout(title=dict(text=frame_title(t)))) for t in times]
room = go.Figure(data=base + frame_traces(0), frames=frames)
W, H = ROOM_SIZE
room.add_shape(type="rect", x0=0, y0=0, x1=W, y1=H, line=dict(color=C["line"], width=2))
room.update_xaxes(range=[-0.2, W + 0.2], showgrid=False, zeroline=False, showticklabels=False)
room.update_yaxes(range=[-0.3, H + 0.3], showgrid=False, zeroline=False, showticklabels=False,
                  scaleanchor="x", scaleratio=1)
room.update_layout(
    title=dict(text=frame_title(0), font=dict(size=12, color=C["text"]), x=0.01, y=0.98),
    margin=dict(l=10, r=10, t=40, b=10),
    updatemenus=[dict(type="buttons", showactive=False, x=0, y=-0.02, xanchor="left", yanchor="top",
                      bgcolor=C["panel"], bordercolor=C["line"], font=dict(color=C["text"], size=11),
                      buttons=[dict(label="▶ play", method="animate",
                                    args=[None, dict(frame=dict(duration=180, redraw=True), fromcurrent=True,
                                                     transition=dict(duration=0))]),
                               dict(label="❚❚ pause", method="animate",
                                    args=[[None], dict(frame=dict(duration=0), mode="immediate")])])],
    sliders=[dict(active=0, x=0.17, len=0.83, y=-0.02, yanchor="top", pad=dict(t=0),
                  currentvalue=dict(visible=False), bgcolor=C["panel"], bordercolor=C["line"],
                  tickcolor=C["faint"], font=dict(color=C["faint"], size=9),
                  steps=[dict(method="animate", label=debrief.mmss(t) if t % 30 == 0 else "",
                              args=[[str(t)], dict(mode="immediate", frame=dict(duration=0, redraw=True))])
                         for t in times])],
)
with rl:
    ui.chart(room, height=470, key="room")
with rr:
    after = fx[fx.t1 > onset].copy()
    after["dur"] = after.t1 - after.t0.clip(lower=onset)
    dw = after.groupby("object").dur.sum().sort_values()
    dw = dw[dw.index != "elsewhere"].tail(9)
    hb = go.Figure(go.Bar(y=[ROOM_OBJECTS[o]["label"] for o in dw.index], x=dw.values, orientation="h",
                          marker=dict(color=[GAZE[object_group(o)] for o in dw.index]),
                          text=[f"{x:.0f}s" for x in dw.values], textposition="outside",
                          textfont=dict(family=MONO, size=10, color=C["muted"]),
                          hovertemplate="%{y}: %{x:.1f}s<extra></extra>"))
    hb.update_layout(title=dict(text="Where attention went after the change", font=dict(size=13)),
                     margin=dict(l=10, r=40, t=40, b=10))
    hb.update_xaxes(showgrid=False, showticklabels=False, range=[0, dw.max() * 1.25])
    ui.chart(hb, height=300, key="dwell")
    shares = [("patient", s.gaze_patient), ("monitor", s.gaze_monitor),
              ("equipment", s.gaze_equipment), ("environment", s.gaze_environment)]
    seg = "".join(f'<div style="flex:{max(v_, 0.001)};background:{GAZE[g]};height:10px"></div>' for g, v_ in shares)
    leg = " ".join(f'<span style="color:{GAZE[g] if g != "environment" else C["muted"]}">{g} {v_ * 100:.0f}%</span>'
                   for g, v_ in shares)
    st.markdown(f'<div class="panel"><div style="display:flex;border-radius:3px;overflow:hidden">{seg}</div>'
                f'<div style="font-family:var(--mono);font-size:11px;margin-top:8px">{leg}</div></div>',
                unsafe_allow_html=True)

# ---------------------------------------------------------------- 04 debrief
# ---------------------------------------------------------------- 04 workflow map
role = roster.loc[lid, "role"] if lid in roster.index else "RN"
ui.section("04", "Workflow map", f"where this {role} gathered information, step by step, against the {role} "
           "standard workflow")
wsteps = T["workflow_steps"][T["workflow_steps"].session_id == sid].sort_values("step").to_dict("records")
std = T["role_standard"][T["role_standard"].role == role].sort_values("step").lane.tolist()
wm1, wm2 = st.columns([2.2, 1])
with wm1:
    ui.chart(swimlane.session_map(wsteps, std), key="swim")
with wm2:
    first_info = LANES.get(s.first_info_lane, {}).get("label", "--") if isinstance(s.first_info_lane, str) else "--"
    rows = [
        ("Workflow match", f"{s.workflow_match:.0f}%", f"vs {role} standard"),
        ("Steps", f"{int(s.workflow_steps)}", f"{role} standard has {len(std)}"),
        ("Started with", first_info, "first information source"),
        ("Epic before bedside", f"{int(s.epic_before_assessment)}", "Epic views before first assessment"),
        ("COMET viewed", "yes" if str(s.cds_viewed).lower() == "true" else "no",
         ("" if pd.isna(s.cds_view_after_change) else f"{s.cds_view_after_change:.0f}s after the change")),
    ]
    st.markdown(
        f'<div class="panel"><div class="lens-kicker" style="color:{ROLE_COLORS.get(role, C["accent"])}">'
        f'{role} workflow</div>' + "".join(
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;padding:8px 0;'
            f'border-bottom:1px solid {C["line"]}"><span style="font-size:13.5px">{a_}<br><span class="small-note">'
            f'{c_}</span></span><span style="font-family:var(--mono);font-size:18px;color:{C["accent"]}">{b_}</span></div>'
            for a_, b_, c_ in rows) + "</div>", unsafe_allow_html=True)
    st.page_link("views/workflows.py", label="Compare all roles in Role Workflows", icon=":material/arrow_forward:")

# ---------------------------------------------------------------- 05 debrief
ui.section("05", "Debrief", "written from the logged data, with timestamps the facilitator can point to")
current = T["ratings"]
mine_r = current[current.learner_id == lid].sort_values("rating")
weak = mine_r.competency.iloc[0] if len(mine_r) else None
F = debrief.facts(s, acts, cues, P["taps"], T["device_dwell"])
D = debrief.template(F, weak)
dl, dr = st.columns([1.5, 1])
with dl:
    st.markdown(
        '<div class="panel debrief">'
        f'<h4 style="color:{C["on_time"]}">Plus</h4><ul>' + "".join(f"<li>{x}</li>" for x in D["plus"]) + "</ul>"
        f'<h4 style="color:{C["late"]}">Delta</h4><ul>' + "".join(f"<li>{x}</li>" for x in D["delta"]) + "</ul>"
        f'<h4 style="color:{C["accent"]}">Next</h4><ul>' + "".join(f"<li>{x}</li>" for x in D["next"]) + "</ul>"
        "</div>", unsafe_allow_html=True)
with dr:
    st.markdown('<div class="panel"><div class="lens-kicker">Narrative debrief</div>'
                '<div style="color:#8391A8;font-size:13px;margin-top:4px">A short paragraph version for the '
                'learner, written from the same observations only.</div></div>', unsafe_allow_html=True)
    if debrief.llm_configured():
        if st.button("Write narrative", type="primary"):
            with st.spinner("Writing..."):
                txt = debrief.narrative(F, names[lid])
            if txt and not txt.startswith("__error__"):
                st.markdown(f'<div class="panel" style="margin-top:8px;font-size:14px;line-height:1.55">'
                            f'{txt}</div>', unsafe_allow_html=True)
            else:
                st.warning("Language model unavailable. The rule based debrief on the left is complete.")
    else:
        st.caption("Set LENS_LLM_BASE_URL and LENS_LLM_MODEL in .env to turn this on. "
                   "The rule based debrief works without it.")
