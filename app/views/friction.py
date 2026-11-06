import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lens import ui
from lens.catalog import ROOM_OBJECTS, SCENARIOS, object_group
from lens.data import all_tables, training_sessions
from lens.ui import C, GAZE, MONO

T = all_tables()
S = training_sessions(T)
sids = set(S.session_id)

ui.top("Partner · Friction Lens", "Where equipment slows clinicians down",
       "Human factors view for device makers and usability teams. DISCOVER already records every touch "
       "and every glance; this page shows where interfaces cost time during a crisis.")

taps = T["taps"][T["taps"].session_id.isin(sids)]
dwell = T["device_dwell"][T["device_dwell"].session_id.isin(sids)]
uses = dwell.groupby("object").session_id.nunique()
tap_n = taps.groupby("object").size().reindex(uses.index, fill_value=0)
dw = dwell.groupby("object").pre_touch_dwell.mean()
F = pd.DataFrame({"uses": uses, "taps_per_use": (tap_n / uses).round(2), "dwell": dw}).dropna()
F["label"] = [ROOM_OBJECTS[o]["label"] for o in F.index]
worst = F.sort_values("taps_per_use").index[-1]

ui.vitals_row([
    ("Devices observed", f"{len(F)}", "", f"{int(F.uses.sum())} device uses", C["spo2"]),
    ("Touches, no effect", f"{len(taps)}", "", f"{len(taps) / len(sids):.1f} per session", C["late"]),
    ("Highest friction", ROOM_OBJECTS[worst]["label"], "", f"{F.loc[worst, 'taps_per_use']:.1f} wasted touches per use",
     C["sbp"]),
    ("Longest look before use", ROOM_OBJECTS[F.dwell.idxmax()]["label"], "",
     f"{F.dwell.max():.1f}s on average", C["violet"]),
])

ui.section("01", "Friction map", "top right is where an interface confuses people: long look, then wrong touches")
p1, p2 = st.columns([1.2, 1])
with p1:
    bub = go.Figure(go.Scatter(
        x=F.dwell, y=F.taps_per_use, mode="markers+text", text=F.label, textposition="top center",
        textfont=dict(size=11, color=C["text"]),
        marker=dict(size=np.sqrt(F.uses) * 6, color=F.taps_per_use, colorscale=[[0, C["spo2"]], [1, C["sbp"]]],
                    line=dict(color=C["bg"], width=1), opacity=0.85),
        customdata=F.uses, hovertemplate="%{text}<br>mean look before use %{x:.1f}s<br>"
                                         "%{y:.2f} wasted touches per use<br>%{customdata} uses<extra></extra>"))
    bub.update_xaxes(title=dict(text="mean seconds looking before first effective use",
                                font=dict(size=11, color=C["muted"])))
    bub.update_yaxes(title=dict(text="touches with no effect, per use", font=dict(size=11, color=C["muted"])))
    ui.chart(bub, height=380, key="bubble")
with p2:
    ct = taps.groupby(["object", "control"]).size().reset_index(name="n")
    ct["dev"] = ct.object.map(lambda o: ROOM_OBJECTS[o]["label"])
    piv = ct.pivot(index="control", columns="dev", values="n").fillna(0)
    piv = piv.loc[piv.sum(axis=1).sort_values(ascending=False).index]
    hm = go.Figure(go.Heatmap(z=piv.values, x=piv.columns, y=[c.replace("_", " ") for c in piv.index],
                              colorscale=[[0, C["panel"]], [0.3, "#4a3a1c"], [1, C["late"]]],
                              texttemplate="%{z:.0f}", textfont=dict(family=MONO, size=10), xgap=2, ygap=2,
                              showscale=False, hovertemplate="%{x} · %{y}<br>%{z:.0f} touches<extra></extra>"))
    hm.update_layout(title=dict(text="Which control gets the wasted touches", font=dict(size=13)),
                     margin=dict(l=10, r=10, t=40, b=10))
    hm.update_yaxes(autorange="reversed", tickfont=dict(size=11))
    ui.chart(hm, height=380, key="controls")

ui.section("02", "Attention flow", "where eyes go next, during the crisis phase only")
fx = T["fixations"][T["fixations"].session_id.isin(sids)].merge(
    T["sessions"][["session_id", "onset_t"]], on="session_id")
fx = fx[fx.t0 >= fx.onset_t].sort_values(["session_id", "t0"])
keep = ["patient", "monitor", "bvm", "o2_flow", "iv_pump", "vent", "med_cart", "phone", "suction"]
fx = fx[fx.object.isin(keep)]
fx["nxt"] = fx.groupby("session_id").object.shift(-1)
tr = fx.dropna(subset=["nxt"])
tr = tr[tr.object != tr.nxt]
mat = pd.crosstab(tr.object, tr.nxt, normalize="index").reindex(index=keep, columns=keep).fillna(0)
lab = [ROOM_OBJECTS[k]["label"] for k in keep]
g1, g2 = st.columns([1.1, 1])
with g1:
    tm = go.Figure(go.Heatmap(z=mat.values * 100, x=lab, y=lab, colorscale=[[0, C["panel"]], [1, C["spo2"]]],
                              texttemplate="%{z:.0f}", textfont=dict(family=MONO, size=9), xgap=1, ygap=1,
                              colorbar=dict(thickness=8, tickfont=dict(size=9)),
                              hovertemplate="from %{y}<br>to %{x}: %{z:.0f}%<extra></extra>"))
    tm.update_yaxes(autorange="reversed", title=dict(text="looking at", font=dict(size=11, color=C["muted"])))
    tm.update_xaxes(title=dict(text="looks next at", font=dict(size=11, color=C["muted"])), tickangle=-35)
    ui.chart(tm, height=420, key="trans")
with g2:
    sc = st.selectbox("Order of first three critical actions in", list(SCENARIOS),
                      format_func=lambda x: SCENARIOS[x]["name"])
    acts = T["actions"][T["actions"].session_id.isin(S[S.scenario_id == sc].session_id)].dropna(subset=["t_rel"])
    seqs = acts.sort_values("t_rel").groupby("session_id").label.apply(lambda x: list(x)[:3])
    seqs = seqs[seqs.map(len) == 3]
    nodes, links = {}, {}

    def nid(step, name):
        key = (step, name)
        if key not in nodes:
            nodes[key] = len(nodes)
        return nodes[key]

    for sq in seqs:
        for i in range(2):
            k = (nid(i, sq[i]), nid(i + 1, sq[i + 1]))
            links[k] = links.get(k, 0) + 1
    names = [f"{n}" for (_, n) in sorted(nodes, key=nodes.get)]
    sk = go.Figure(go.Sankey(
        node=dict(label=names, pad=14, thickness=10, color=C["violet"], line=dict(width=0)),
        link=dict(source=[k[0] for k in links], target=[k[1] for k in links], value=list(links.values()),
                  color="rgba(168,139,250,0.25)"),
        textfont=dict(size=11, color=C["text"])))
    sk.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    ui.chart(sk, height=360, key="sankey")
    st.caption(f"{len(seqs)} sessions. Wide early branches mean the order of care is not standardized yet.")

ui.section("03", "Partner export", "de-identified interaction records, ready for a usability study")
exp = taps.merge(T["sessions"][["session_id", "scenario_id", "attempt", "build"]], on="session_id")
exp = exp.assign(session_key=exp.session_id.astype("category").cat.codes)[
    ["session_key", "scenario_id", "attempt", "build", "t", "object", "control"]]
st.dataframe(exp.head(200), hide_index=True, width="stretch", height=220)
st.download_button("Download interaction export (CSV)", exp.to_csv(index=False),
                   file_name="discover_interaction_export.csv", mime="text/csv", icon=":material/download:")
