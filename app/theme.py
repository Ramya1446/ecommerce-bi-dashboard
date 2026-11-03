"""Visual system for the dashboard: palette, Plotly template, CSS and small HTML components."""

from __future__ import annotations

import html

import plotly.graph_objects as go
import plotly.io as pio

# Validated categorical palette (fixed order - colour follows the entity, never its rank)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]
DIVERGING = [[0.0, "#e34948"], [0.5, "#f0efec"], [1.0, "#2a78d6"]]

INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#fcfcfb"
PAGE = "#f6f5f1"
GOOD_TEXT = "#006300"
CRITICAL = "#d03b3b"
GOOD = "#0ca30c"
WARNING = "#fab219"

CATEGORY_COLORS = {
    "Electronics": SERIES[0], "Fashion": SERIES[1], "Home & Kitchen": SERIES[2], "Beauty": SERIES[3],
    "Sports & Outdoors": SERIES[4], "Books": SERIES[5], "Toys & Games": SERIES[6],
}
CHANNEL_COLORS = {
    "Organic Search": SERIES[0], "Paid Search": SERIES[1], "Social Media": SERIES[2],
    "Email": SERIES[3], "Referral": SERIES[4],
}
DEVICE_COLORS = {"Mobile": SERIES[0], "Desktop": SERIES[1], "Tablet": SERIES[2]}
GROUP_COLORS = [SERIES[0], SERIES[1]]

FONT = 'Inter, system-ui, -apple-system, "Segoe UI", sans-serif'


def register_template() -> None:
    t = go.layout.Template()
    t.layout = go.Layout(
        font=dict(family=FONT, size=13, color=INK_2),
        title=dict(font=dict(size=15, color=INK), x=0, xanchor="left", xref="container",
                   y=1, yref="container", yanchor="top", pad=dict(t=14, l=4)),
        colorway=SERIES,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=78, b=8),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=GRID, font=dict(family=FONT, color=INK, size=12)),
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(size=12, color=INK_2), bgcolor="rgba(0,0,0,0)", title_text=""),
        xaxis=dict(showgrid=False, linecolor=AXIS, tickcolor=AXIS, ticks="outside", ticklen=4,
                   tickfont=dict(color=MUTED, size=11), title=dict(font=dict(color=MUTED, size=12)),
                   zeroline=False),
        yaxis=dict(gridcolor=GRID, gridwidth=1, linecolor="rgba(0,0,0,0)", zeroline=False,
                   tickfont=dict(color=MUTED, size=11), title=dict(font=dict(color=MUTED, size=12))),
        bargap=0.28,
        bargroupgap=0.08,
    )
    t.data.bar = [go.Bar(marker=dict(line=dict(width=0), cornerradius=4))]
    t.data.scatter = [go.Scatter(line=dict(width=2))]
    pio.templates["bi"] = t
    pio.templates.default = "bi"


def money(x: float, decimals: int = 1) -> str:
    if x is None:
        return "-"
    a = abs(x)
    if a >= 1e6:
        return f"${x / 1e6:.{decimals}f}M"
    if a >= 1e3:
        return f"${x / 1e3:.{decimals}f}K"
    return f"${x:,.0f}"


def num(x: float) -> str:
    a = abs(x)
    if a >= 1e6:
        return f"{x / 1e6:.2f}M"
    if a >= 1e4:
        return f"{x / 1e3:.1f}K"
    return f"{x:,.0f}"


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea, select {{
    font-family: {FONT};
}}
.stApp {{ background: {PAGE}; }}
.block-container {{ padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1440px; }}
header[data-testid="stHeader"] {{ background: transparent; }}

/* Hero */
.hero {{
    display:flex; justify-content:space-between; align-items:flex-end; gap:24px; flex-wrap:wrap;
    padding: 22px 26px; border-radius: 16px; margin-bottom: 18px;
    background: linear-gradient(120deg, #0d366b 0%, #1c5cab 55%, #2a78d6 100%);
    color: #fff; box-shadow: 0 10px 30px -18px rgba(13,54,107,.8);
}}
.hero h1 {{ font-size: 1.65rem; font-weight: 700; margin: 0; color:#fff; letter-spacing:-0.01em; padding:0; }}
.hero p {{ margin: 4px 0 0; opacity: .85; font-size: .95rem; }}
.hero .meta {{ text-align:right; font-size:.82rem; opacity:.9; line-height:1.5; }}
.hero .meta b {{ font-weight:600; }}

/* KPI cards */
.kpi-grid {{ display:grid; grid-template-columns: repeat(var(--cols, 4), minmax(0, 1fr)); gap: 12px; margin: 4px 0 8px; }}
@media (max-width: 1100px) {{ .kpi-grid {{ grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }} }}
.kpi {{
    background: {SURFACE}; border: 1px solid rgba(11,11,11,.08); border-radius: 14px;
    padding: 14px 16px 12px; box-shadow: 0 1px 2px rgba(11,11,11,.04);
}}
.kpi .label {{ font-size: .74rem; text-transform: uppercase; letter-spacing: .06em; color: {MUTED}; font-weight:600; }}
.kpi .value.sm {{ font-size: 1.15rem; padding-top: 6px; }}
.kpi .value {{ font-size: 1.6rem; font-weight: 700; color: {INK}; margin-top: 4px; letter-spacing:-0.02em; }}
.kpi .delta {{ font-size: .78rem; margin-top: 4px; font-weight: 600; }}
.kpi .delta.up {{ color: {GOOD_TEXT}; }}
.kpi .delta.down {{ color: {CRITICAL}; }}
.kpi .delta.flat {{ color: {MUTED}; }}
.kpi .delta span {{ color: {MUTED}; font-weight: 500; }}

/* Section headings & cards */
.section-title {{ font-size: 1.05rem; font-weight: 700; color: {INK}; margin: 18px 0 2px; }}
.section-sub {{ font-size: .86rem; color: {INK_2}; margin: 0 0 8px; }}
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {SURFACE}; border-radius: 14px !important; border-color: rgba(11,11,11,.08) !important;
}}

/* Recommendation cards */
.rec {{
    background: {SURFACE}; border: 1px solid rgba(11,11,11,.08); border-left: 4px solid var(--accent);
    border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; height: 100%;
}}
.rec .top {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:6px; }}
.rec .title {{ font-weight: 700; color: {INK}; font-size: 1rem; }}
.rec .finding {{ color: {INK_2}; font-size: .9rem; margin: 4px 0; }}
.rec .action {{ color: {INK}; font-size: .9rem; margin: 6px 0 4px; }}
.rec .impact {{ color: {MUTED}; font-size: .8rem; }}
.badge {{ font-size: .7rem; font-weight: 700; padding: 2px 8px; border-radius: 999px; letter-spacing:.03em; }}
.badge.High {{ background: #fde8e8; color: #9b1c1c; }}
.badge.Medium {{ background: #fff4d6; color: #7a5200; }}
.badge.Low {{ background: #e7f0fb; color: #104281; }}
.badge.area {{ background: #f0efec; color: {INK_2}; }}

/* Hypotheses */
.hypo {{ background:{SURFACE}; border:1px solid rgba(11,11,11,.08); border-radius:12px; padding:10px 16px;
         margin: 6px 0 10px; font-size:.92rem; color:{INK}; line-height:1.7; }}
.hypo .h {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:.86rem; color:#1c5cab; }}

/* Test verdict */
.verdict {{ border-radius: 12px; padding: 14px 16px; font-size: .95rem; line-height: 1.5; }}
.verdict.sig {{ background: #e8f5e8; border: 1px solid #b7deb7; color: #0b3d0b; }}
.verdict.ns {{ background: #f0efec; border: 1px solid {AXIS}; color: {INK}; }}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {GRID}; flex-wrap: wrap; }}
.stTabs [data-baseweb="tab"] {{
    height: 42px; padding: 0 14px; border-radius: 10px 10px 0 0; font-weight: 600; color: {INK_2};
}}
.stTabs [aria-selected="true"] {{ color: #1c5cab; background: {SURFACE}; }}

section[data-testid="stSidebar"] {{ background: #ffffff; border-right: 1px solid {GRID}; }}
section[data-testid="stSidebar"] .sidebar-brand {{ font-weight:700; font-size:1.05rem; color:{INK}; margin-bottom: 2px; }}
section[data-testid="stSidebar"] .sidebar-sub {{ font-size:.8rem; color:{MUTED}; margin-bottom: 10px; }}
.footer {{ color:{MUTED}; font-size:.78rem; text-align:center; margin-top: 28px; }}
code {{ font-size: .82rem !important; }}
</style>
"""


def hero(title: str, subtitle: str, meta: list[tuple[str, str]]) -> str:
    m = "<br>".join(f"{html.escape(k)}: <b>{html.escape(v)}</b>" for k, v in meta)
    return (f'<div class="hero"><div><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>'
            f'<div class="meta">{m}</div></div>')


def kpi_card(label: str, value: str, delta: float | None = None, *, invert: bool = False,
             delta_is_points: bool = False, suffix: str = "vs prev. period", note: str | None = None,
             small: bool = False) -> str:
    """KPI tile. A delta gets an arrow + sign so direction never relies on colour alone."""
    if delta is not None:
        good = (delta >= 0) != invert
        if abs(delta) < 0.0005:  # rounds to zero at the displayed precision
            delta = 0.0
        cls = "flat" if delta == 0 else ("up" if good else "down")
        arrow = "▲" if delta > 0 else "▼" if delta < 0 else "■"
        txt = f"{delta * 100:+.1f} pts" if delta_is_points else f"{delta:+.1%}"
        d = f'<div class="delta {cls}">{arrow} {txt} <span>{html.escape(suffix)}</span></div>'
    elif note:
        d = f'<div class="delta flat"><span>{html.escape(note)}</span></div>'
    else:
        d = ""
    return (f'<div class="kpi"><div class="label">{html.escape(label)}</div>'
            f'<div class="value{" sm" if small else ""}">{value}</div>{d}</div>')


def kpi_grid(cards: list[str], cols: int | None = None) -> str:
    cols = cols or (4 if len(cards) == 8 else min(len(cards), 6))
    return f'<div class="kpi-grid" style="--cols:{cols}">' + "".join(cards) + "</div>"


def section(title: str, sub: str = "") -> str:
    s = f'<div class="section-title">{html.escape(title)}</div>'
    if sub:
        s += f'<div class="section-sub">{html.escape(sub)}</div>'
    return s


PRIORITY_ACCENT = {"High": CRITICAL, "Medium": WARNING, "Low": SERIES[0]}
PRIORITY_ICON = {"High": "●●●", "Medium": "●●○", "Low": "●○○"}


def rec_card(rec) -> str:
    impact = (f"Est. impact: <b>{money(rec.impact)}</b> / year — {html.escape(rec.impact_basis)}"
              if rec.impact > 0 else f"Impact: {html.escape(rec.impact_basis)}")
    return f"""
<div class="rec" style="--accent:{PRIORITY_ACCENT[rec.priority]}">
  <div class="top">
    <span class="badge {rec.priority}">{PRIORITY_ICON[rec.priority]} {rec.priority.upper()}</span>
    <span class="badge area">{html.escape(rec.area)}</span>
  </div>
  <div class="title">{html.escape(rec.title)}</div>
  <div class="finding">{html.escape(rec.finding)}</div>
  <div class="action"><b>Action:</b> {html.escape(rec.action)}</div>
  <div class="impact">{impact}</div>
</div>"""
