"""Visual system: colours, CSS, Plotly template and small HTML components."""
import html

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# Colours follow bedside monitor conventions so clinicians read them instantly:
# HR green, SpO2 cyan, RR yellow, BP red.
C = {
    "bg": "#0A0F1A", "panel": "#111A2B", "panel2": "#0E1524", "line": "#1E2A41",
    "text": "#E6EDF7", "muted": "#8391A8", "faint": "#4A5670",
    "hr": "#3DDC97", "spo2": "#4FC3F7", "rr": "#F4D35E", "sbp": "#F47174",
    "on_time": "#3DDC97", "late": "#F4B740", "missed": "#F47174",
    "ghost": "#9AA7BD", "accent": "#4FC3F7", "violet": "#A88BFA",
}
GAZE = {"patient": "#F28DB2", "monitor": "#4FC3F7", "equipment": "#A88BFA", "environment": "#3A465E"}
MONO = "IBM Plex Mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
SANS = "IBM Plex Sans, system-ui, -apple-system, Segoe UI, sans-serif"
COMP_COL = {"REC": "#F4D35E", "COM": "#F28DB2", "AIR": "#4FC3F7", "CIR": "#F47174", "EQP": "#A88BFA"}
STATUS_LABEL = {"on_time": "On time", "late": "Late", "missed": "Missed"}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, p, li, label, .stSelectbox, .stRadio {{
  font-family: 'IBM Plex Sans', system-ui, sans-serif;
}}
:root {{ --mono: 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
.stApp {{ background: radial-gradient(1200px 600px at 85% -10%, #12203a 0%, {C['bg']} 55%); }}
header[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer {{ visibility: hidden; }}
.block-container {{ padding-top: 2.2rem; max-width: 1380px; }}
section[data-testid="stSidebar"] {{ background: {C['panel2']}; border-right: 1px solid {C['line']}; }}
h1, h2, h3 {{ letter-spacing: -0.01em; font-weight: 500; }}

.lens-top {{ display:flex; align-items:flex-end; justify-content:space-between; gap:24px;
  border-bottom:1px solid {C['line']}; padding-bottom:14px; margin-bottom:18px; }}
.lens-kicker {{ font-family:var(--mono); font-size:11px; letter-spacing:.16em; color:{C['accent']};
  text-transform:uppercase; }}
.lens-title {{ font-size:30px; font-weight:500; color:{C['text']}; margin:4px 0 2px; line-height:1.15; }}
.lens-sub {{ color:{C['muted']}; font-size:14px; max-width:760px; }}
.lens-chip {{ font-family:var(--mono); font-size:11px; color:{C['muted']}; border:1px solid {C['line']};
  padding:4px 8px; border-radius:3px; white-space:nowrap; }}

.vital-row {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap:10px; margin: 4px 0 14px; }}
.vital {{ background:{C['panel']}; border:1px solid {C['line']}; border-radius:6px; padding:10px 14px 12px;
  position:relative; overflow:hidden; }}
.vital:before {{ content:''; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--c); }}
.vital .lab {{ font-family:var(--mono); font-size:10.5px; letter-spacing:.12em; text-transform:uppercase; color:{C['muted']}; }}
.vital .val {{ font-family:var(--mono); font-size:30px; font-weight:500; color:var(--c); line-height:1.1; margin-top:4px; }}
.vital .val.word {{ font-size:20px; padding-top:8px; }}
.vital .val small {{ font-size:13px; color:{C['muted']}; margin-left:4px; font-weight:400; }}
.vital .note {{ font-size:12px; color:{C['muted']}; margin-top:2px; }}

.panel {{ background:{C['panel']}; border:1px solid {C['line']}; border-radius:6px; padding:14px 16px; }}
.sec {{ display:flex; align-items:baseline; gap:10px; margin: 18px 0 6px; }}
.sec .n {{ font-family:var(--mono); font-size:11px; color:{C['accent']}; }}
.sec .t {{ font-size:16px; font-weight:500; color:{C['text']}; }}
.sec .d {{ font-size:13px; color:{C['muted']}; }}

.debrief h4 {{ font-family:var(--mono); font-size:11px; letter-spacing:.14em; text-transform:uppercase; margin:10px 0 4px; }}
.debrief ul {{ margin:0 0 4px 0; padding-left:18px; }}
.debrief li {{ font-size:14px; color:{C['text']}; margin-bottom:3px; }}
.tag {{ font-family:var(--mono); font-size:10.5px; padding:2px 6px; border-radius:3px; border:1px solid; }}
.rec {{ border:1px solid {C['line']}; border-left:3px solid {C['accent']}; background:{C['panel']};
  border-radius:6px; padding:12px 14px; margin-bottom:8px; }}
.rec .nm {{ font-weight:500; font-size:15px; }}
.rec .why {{ color:{C['muted']}; font-size:13px; margin-top:3px; }}
.small-note {{ color:{C['faint']}; font-size:12px; font-family:var(--mono); }}
div[data-testid="stMetricValue"] {{ font-family:var(--mono); }}
</style>
"""


def setup(page_title):
    st.markdown(CSS, unsafe_allow_html=True)


def top(kicker, title, sub="", chip="SYNTHETIC SAMPLE DATA"):
    st.markdown(
        f"""<div class="lens-top"><div><div class="lens-kicker">{html.escape(kicker)}</div>
        <div class="lens-title">{html.escape(title)}</div><div class="lens-sub">{sub}</div></div>
        <div class="lens-chip">{chip}</div></div>""", unsafe_allow_html=True)


def section(n, title, desc=""):
    st.markdown(f'<div class="sec"><span class="n">{n}</span><span class="t">{html.escape(title)}</span>'
                f'<span class="d">{desc}</span></div>', unsafe_allow_html=True)


def vitals_row(items):
    """items: list of (label, value, unit, note, colour)."""
    cells = "".join(
        f'<div class="vital" style="--c:{c}"><div class="lab">{html.escape(lab)}</div>'
        f'<div class="val{"" if any(ch.isdigit() for ch in str(val)) else " word"}">{val}<small>{unit}</small></div>'
        f'<div class="note">{note}</div></div>'
        for lab, val, unit, note, c in items)
    st.markdown(f'<div class="vital-row">{cells}</div>', unsafe_allow_html=True)


def tag(text, colour):
    return f'<span class="tag" style="color:{colour};border-color:{colour}55">{html.escape(text)}</span>'


def _template():
    t = go.layout.Template()
    t.layout = go.Layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=SANS, color=C["text"], size=12),
        colorway=[C["spo2"], C["hr"], C["rr"], C["sbp"], C["violet"], GAZE["patient"], C["ghost"]],
        xaxis=dict(gridcolor=C["line"], zerolinecolor=C["line"], linecolor=C["line"],
                   tickfont=dict(family=MONO, size=11, color=C["muted"])),
        yaxis=dict(gridcolor=C["line"], zerolinecolor=C["line"], linecolor=C["line"],
                   tickfont=dict(family=MONO, size=11, color=C["muted"])),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color=C["muted"]),
                    orientation="h", y=1.08, x=0),
        margin=dict(l=10, r=10, t=30, b=10),
        hoverlabel=dict(bgcolor=C["panel"], bordercolor=C["line"],
                        font=dict(family=MONO, size=12, color=C["text"])),
    )
    return t


pio.templates["lens"] = _template()
pio.templates.default = "lens"


def chart(fig, height=None, key=None):
    if height:
        fig.update_layout(height=height)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)
