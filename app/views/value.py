import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lens import ui
from lens.catalog import SCENARIOS
from lens.data import all_tables, training_sessions
from lens.ui import C, MONO

T = all_tables()
S = training_sessions(T)

ui.top("Program · Value Ledger", "What the program is worth",
       "For administrators and partners who will never wear the headset. Every number is computed "
       "from the session data and the assumptions you set below, so the case can be argued line by line.")

with st.expander("Assumptions (edit to match your program)", expanded=False, icon=":material/tune:"):
    a1, a2, a3 = st.columns(3)
    m_fac_hr = a1.number_input("Mannequin sim: facilitator hours per session", 0.0, 10.0, 1.5, 0.25)
    m_tech_hr = a1.number_input("Mannequin sim: sim tech hours per session", 0.0, 10.0, 1.0, 0.25)
    fac_rate = a2.number_input("Facilitator cost per hour ($)", 0.0, 500.0, 95.0, 5.0)
    tech_rate = a2.number_input("Sim tech cost per hour ($)", 0.0, 300.0, 48.0, 2.0)
    m_room = a3.number_input("Mannequin sim: room, supplies, wear per session ($)", 0.0, 2000.0, 140.0, 10.0)
    vr_min = a3.number_input("VR: facilitator minutes per session", 0.0, 120.0, 12.0, 1.0)
    vr_hw = a1.number_input("VR: headset and licence cost per session ($)", 0.0, 500.0, 9.0, 1.0)
    target = a2.slider("Score that counts as 'ready'", 60, 100, 85)

n = len(S)
mannequin = n * (m_fac_hr * fac_rate + m_tech_hr * tech_rate + m_room)
vr = n * (vr_min / 60 * fac_rate + vr_hw)
hours_saved = n * (m_fac_hr + m_tech_hr - vr_min / 60)
ready_l = S.groupby("learner_id").score.max().ge(target).mean()
first = S[S.attempt == 1]
rep = S[S.attempt >= 2]

ui.vitals_row([
    ("Sessions delivered", f"{n}", "", f"{S.learner_id.nunique()} learners · {S.started_at.dt.to_period('M').nunique()}"
     " months", C["spo2"]),
    ("Staff hours freed", f"{hours_saved:,.0f}", "h", "compared with mannequin sim", C["on_time"]),
    ("Cost avoided", f"${(mannequin - vr) / 1000:,.1f}", "k", f"${(mannequin - vr) / n:,.0f} per session", C["rr"]),
    ("Learners ready", f"{ready_l * 100:.0f}", "%", f"reached {target}+ on some scenario", C["violet"]),
    ("Unstable time", f"{first.instability_sec.mean():.0f} → {rep.instability_sec.mean():.0f}", "s",
     "first run to repeat, mean", C["sbp"]),
])

ui.section("01", "Adoption", "sessions per month, stacked by scenario")
S2 = S.assign(month=S.started_at.dt.to_period("M").dt.to_timestamp())
m = S2.groupby(["month", "scenario_id"]).size().unstack(fill_value=0)
ad = go.Figure()
palette = [C["spo2"], C["hr"], C["rr"], C["sbp"], C["violet"]]
for i, sc in enumerate(m.columns):
    ad.add_trace(go.Bar(x=m.index, y=m[sc], name=SCENARIOS[sc]["short"], marker_color=palette[i % 5]))
ad.update_layout(barmode="stack", legend=dict(y=1.14), margin=dict(l=10, r=10, t=40, b=10))
ad.update_xaxes(tickformat="%b %Y", dtick="M1")

v1, v2 = st.columns([1.3, 1])
with v1:
    ui.chart(ad, height=320, key="adopt")
with v2:
    wf = go.Figure(go.Waterfall(
        orientation="v", measure=["absolute", "relative", "total"],
        x=["Mannequin sim<br>same volume", "Saved by<br>VR delivery", "VR cost"],
        y=[mannequin, -(mannequin - vr), 0],
        text=[f"${mannequin / 1000:,.1f}k", f"-${(mannequin - vr) / 1000:,.1f}k", f"${vr / 1000:,.1f}k"],
        textposition=["outside", "inside", "outside"], textfont=dict(family=MONO, size=11, color=C["text"]),
        connector=dict(line=dict(color=C["line"])),
        increasing=dict(marker=dict(color=C["sbp"])), decreasing=dict(marker=dict(color=C["on_time"])),
        totals=dict(marker=dict(color=C["spo2"]))))
    wf.update_layout(title=dict(text="Cost of delivering the same sessions", font=dict(size=13)),
                     margin=dict(l=10, r=10, t=40, b=10), showlegend=False)
    wf.update_yaxes(showticklabels=False, range=[0, mannequin * 1.2])
    wf.update_xaxes(tickfont=dict(family="IBM Plex Sans, system-ui, sans-serif", size=11, color=C["muted"]))
    ui.chart(wf, height=320, key="wf")

ui.section("02", "Outcome chain", "practice, then behaviour, then the simulated patient, then confidence")
o1, o2, o3, o4 = st.columns(4)


def mini(col, title, df, metric, colour, fmt="{:.0f}", suffix=""):
    g = df.groupby(df.attempt.clip(upper=3))[metric].mean()
    fig = go.Figure(go.Bar(x=["1st", "2nd", "3rd+"][:len(g)], y=g.values, marker_color=colour,
                           text=[fmt.format(v) + suffix for v in g.values], textposition="outside",
                           textfont=dict(family=MONO, size=11, color=C["text"])))
    fig.update_layout(title=dict(text=title, font=dict(size=12)), margin=dict(l=5, r=5, t=40, b=5))
    fig.update_yaxes(showticklabels=False, showgrid=False, range=[0, g.max() * 1.3])
    with col:
        ui.chart(fig, height=230, key=title)


mini(o1, "Score", S, "score", C["on_time"])
mini(o2, "Seconds to rescue", S.dropna(subset=["time_to_rescue"]), "time_to_rescue", C["spo2"], suffix="s")
mini(o3, "Seconds patient unstable", S, "instability_sec", C["sbp"], suffix="s")
sv = T["surveys"]
with o4:
    pre, post = sv.pre_confidence.mean(), sv.post_confidence.mean()
    fig = go.Figure(go.Bar(x=["Before", "After"], y=[pre, post], marker_color=[C["faint"], C["violet"]],
                           text=[f"{pre:.1f}", f"{post:.1f}"], textposition="outside",
                           textfont=dict(family=MONO, size=11, color=C["text"])))
    fig.update_layout(title=dict(text="Self-reported confidence (1-5)", font=dict(size=12)),
                      margin=dict(l=5, r=5, t=40, b=5))
    fig.update_yaxes(showticklabels=False, showgrid=False, range=[0, 5.5])
    ui.chart(fig, height=230, key="conf_all")

ui.section("03", "In one paragraph", "copy this into a proposal or a board update")
drop = 1 - rep.instability_sec.mean() / first.instability_sec.mean()
st.markdown(
    f'<div class="panel" style="font-size:15px;line-height:1.65">Across {n} DISCOVER sessions with '
    f'{S.learner_id.nunique()} clinicians, mean score rose from {first.score.mean():.0f} on a first attempt to '
    f'{rep.score.mean():.0f} on repeats, and the simulated patient spent {drop * 100:.0f}% less time outside safe '
    f'ranges. Delivering the same volume as mannequin simulation would have needed about {hours_saved:,.0f} more '
    f'staff hours and ${(mannequin - vr) / 1000:,.0f}k more in cost, under the assumptions above. '
    f'<span style="color:{C["muted"]}">These figures come from synthetic sample data and show how the measure '
    f'would work, not a result.</span></div>', unsafe_allow_html=True)
