"""Swim-lane workflow charts in the style of the hackathon team's VR observation maps."""
import html

import plotly.graph_objects as go

from .catalog import LANE_ORDER, LANES
from .ui import C, MONO

Y = {k: len(LANE_ORDER) - i for i, k in enumerate(LANE_ORDER)}   # Epic on top, communication at the bottom


def _bands(fig, xmax):
    for k in LANE_ORDER:
        fig.add_shape(type="rect", x0=0, x1=xmax, y0=Y[k] - 0.42, y1=Y[k] + 0.42, line_width=0,
                      fillcolor=LANES[k]["color"], opacity=0.16, layer="below")
        fig.add_shape(type="rect", x0=-0.9, x1=0, y0=Y[k] - 0.42, y1=Y[k] + 0.42, line_width=0,
                      fillcolor=LANES[k]["color"], opacity=0.9, layer="below")
    fig.update_yaxes(tickvals=[Y[k] for k in LANE_ORDER], ticktext=[LANES[k]["label"] for k in LANE_ORDER],
                     range=[0.4, len(LANE_ORDER) + 0.75], showgrid=False, zeroline=False,
                     tickfont=dict(size=11.5, color=C["text"]))


def session_map(steps, standard=None, title="", show_notes=True, height=430):
    """One learner's path (thin line, sticky notes) with the role's standard path (thick, numbered)."""
    n = max(len(steps), len(standard or []), 1)
    xmax = n + 0.6
    fig = go.Figure()
    _bands(fig, xmax)
    # CDS touchpoint highlight, like the blue box on the team's map
    for i, s in enumerate(steps, start=1):
        if s["lane"] == "comet":
            fig.add_shape(type="rect", x0=i - 0.42, x1=i + 0.42, y0=0.45, y1=len(LANE_ORDER) + 0.45,
                          line=dict(color="#7FDBFF", width=1.5), fillcolor="#7FDBFF", opacity=0.14, layer="below")
            fig.add_annotation(x=i, y=len(LANE_ORDER) + 0.62, text="CDS touchpoint", showarrow=False,
                               font=dict(family=MONO, size=10, color="#7FDBFF"))
    if standard:
        fig.add_trace(go.Scatter(
            x=list(range(1, len(standard) + 1)), y=[Y[k] for k in standard], mode="lines+markers+text",
            line=dict(color="#E6EDF7", width=4), marker=dict(size=20, color="rgba(0,0,0,0)",
                                                            line=dict(color="#E6EDF7", width=2.5)),
            text=[str(i) for i in range(1, len(standard) + 1)], textposition="middle center",
            textfont=dict(family=MONO, size=11, color="#E6EDF7"), name="Role standard", opacity=0.55,
            hovertemplate="standard step %{text}<extra></extra>"))
    if steps:
        fig.add_trace(go.Scatter(
            x=list(range(1, len(steps) + 1)), y=[Y[s["lane"]] for s in steps], mode="lines+markers",
            line=dict(color=C["text"], width=1.4), name="This session",
            marker=dict(size=11, color=[LANES[s["lane"]]["color"] for s in steps], line=dict(color=C["bg"], width=1.5)),
            customdata=[[s["what"], s["t"]] for s in steps],
            hovertemplate="%{customdata[0]}<br>%{customdata[1]:.0f}s<extra></extra>"))
        if show_notes:
            for i, s in enumerate(steps, start=1):
                note = s["what"].split(";")[0]
                note = note if len(note) <= 22 else note[:20] + "…"
                fig.add_annotation(x=i, y=Y[s["lane"]] + (0.27 if i % 2 else -0.27), text=html.escape(note),
                                   showarrow=False, bgcolor="#F4D35E", bordercolor="#C9A92F", borderpad=2,
                                   font=dict(size=9, color="#1B1B1B"))
    fig.update_xaxes(range=[-0.95, xmax], showgrid=False, zeroline=False, tickvals=list(range(1, n + 1)),
                     title=dict(text="step", font=dict(size=11, color=C["muted"])))
    fig.update_layout(title=dict(text=title, font=dict(size=13)), legend=dict(y=1.12), height=height,
                      margin=dict(l=10, r=10, t=50, b=10))
    return fig


def overlay_map(paths, standard, colour, height=360):
    """Every session of a role as faint lines, with the standard path thick and numbered (the team's slide 3)."""
    n = max([len(p) for p in paths] + [len(standard), 1])
    n = min(n, 16)
    fig = go.Figure()
    _bands(fig, n + 0.6)
    for p in paths:
        p = p[:n]
        fig.add_trace(go.Scatter(x=list(range(1, len(p) + 1)), y=[Y[k] for k in p], mode="lines",
                                 line=dict(color=colour, width=1), opacity=0.16, hoverinfo="skip",
                                 showlegend=False))
    fig.add_trace(go.Scatter(
        x=list(range(1, len(standard) + 1)), y=[Y[k] for k in standard], mode="lines+markers+text",
        line=dict(color="#F2F5FA", width=3.5), marker=dict(size=20, color=C["bg"], line=dict(color="#F2F5FA", width=2.5)),
        text=[str(i) for i in range(1, len(standard) + 1)], textposition="middle center",
        textfont=dict(family=MONO, size=11, color="#F2F5FA"), showlegend=False,
        hovertemplate="standard step %{text}<extra></extra>"))
    fig.update_xaxes(range=[-0.95, n + 0.6], showgrid=False, zeroline=False, showticklabels=False)
    fig.update_yaxes(tickfont=dict(size=10, color=C["text"]))
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10))
    return fig
