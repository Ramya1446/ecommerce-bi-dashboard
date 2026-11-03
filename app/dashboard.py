"""E-commerce Business Intelligence Dashboard (Streamlit).

Run:  streamlit run app/dashboard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ecombi import analytics as an  # noqa: E402
from ecombi import insights  # noqa: E402
from ecombi import stats as st_tests  # noqa: E402
from ecombi.db import DEFAULT_DB, build_database, load_queries, read_sql, run_readonly  # noqa: E402
from ecombi.generate import generate  # noqa: E402

import theme as T  # noqa: E402

st.set_page_config(page_title="E-commerce BI Dashboard", page_icon="📊", layout="wide",
                   initial_sidebar_state="expanded")
T.register_template()
st.markdown(T.CSS, unsafe_allow_html=True)
PLOT_CFG = {"displayModeBar": False, "responsive": True}


def pad_x(fig: go.Figure, xmax: float, factor: float = 1.18) -> None:
    """Leave room for outside labels on horizontal bars so they are never clipped."""
    fig.update_xaxes(range=[0, float(xmax) * factor])


def chart(fig: go.Figure, height: int = 360) -> None:
    fig.update_layout(height=height)
    st.plotly_chart(fig, width="stretch", config=PLOT_CFG)


# ------------------------------------------------------------------------- data
@st.cache_resource(show_spinner="Building the sample warehouse (first run only)…")
def ensure_db() -> Path:
    if not DEFAULT_DB.exists():
        build_database(generate())
    return DEFAULT_DB


@st.cache_resource(show_spinner="Loading warehouse…")
def frames() -> an.Frames:
    ensure_db()
    return an.load_frames()


fr_all = frames()
min_d = fr_all.orders["order_date"].min().normalize()
max_d = fr_all.orders["order_date"].max().normalize()

# ---------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown('<div class="sidebar-brand">📊 Commerce BI</div>'
                '<div class="sidebar-sub">Filters apply to every tab</div>', unsafe_allow_html=True)
    preset = st.selectbox("Period", ["All time", "Last 12 months", "Last 6 months", "Last 90 days",
                                     "Year 2025", "Year 2024", "Custom"], index=1, key="period")
    if preset == "All time":
        start, end = min_d, max_d
    elif preset == "Last 12 months":
        start, end = max_d - pd.DateOffset(months=12) + pd.Timedelta(days=1), max_d
    elif preset == "Last 6 months":
        start, end = max_d - pd.DateOffset(months=6) + pd.Timedelta(days=1), max_d
    elif preset == "Last 90 days":
        start, end = max_d - pd.Timedelta(days=89), max_d
    elif preset == "Year 2025":
        start, end = pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31")
    elif preset == "Year 2024":
        start, end = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31")
    else:
        rng = st.date_input("Custom range", (min_d.date(), max_d.date()),
                            min_value=min_d.date(), max_value=max_d.date())
        if isinstance(rng, tuple) and len(rng) == 2:
            start, end = pd.Timestamp(rng[0]), pd.Timestamp(rng[1])
        else:
            start, end = min_d, max_d

    cats = sorted(fr_all.lines["category"].unique())
    sel_cats = st.multiselect("Category", cats, placeholder="All categories")
    sel_ch = st.multiselect("Channel", sorted(fr_all.orders["channel"].unique()), placeholder="All channels")
    sel_reg = st.multiselect("Region", sorted(fr_all.customers["region"].unique()), placeholder="All regions")
    sel_dev = st.multiselect("Device", ["Mobile", "Desktop", "Tablet"], placeholder="All devices")
    sel_loy = st.multiselect("Customer type", ["Loyalty member", "Non-member"], placeholder="All customers")
    st.divider()
    st.caption("Data: reproducible synthetic dataset (seed 42) - 9K customers, 230K sessions, "
               "12K orders, Jan 2024 - Dec 2025. Rebuild with `python scripts/build_data.py`.")

flt = an.Filters(pd.Timestamp(start), pd.Timestamp(end), sel_cats or None, sel_ch or None,
                 sel_reg or None, sel_dev or None, sel_loy or None)


fr = an.apply_filters(fr_all, flt)
prev_f = an.previous_period(flt)
has_prev = prev_f.start >= min_d - pd.Timedelta(days=1)
fr_prev = an.apply_filters(fr_all, prev_f) if has_prev else None

if fr.orders.empty or fr.sessions.empty:
    st.markdown(T.hero("E-commerce Business Intelligence", "Revenue · Customers · Products · Conversion",
                       [("Period", f"{start:%d %b %Y} – {end:%d %b %Y}")]), unsafe_allow_html=True)
    st.warning("No data matches the current filters. Widen the period or clear a filter.")
    st.stop()

k = an.kpis(fr)
kp = an.kpis(fr_prev) if fr_prev is not None and not fr_prev.orders.empty else None

st.markdown(T.hero(
    "E-commerce Business Intelligence",
    "Revenue · Customers · Products · Retention & Conversion · Experiments",
    [("Period", f"{start:%d %b %Y} – {end:%d %b %Y}"),
     ("Compared with", f"{prev_f.start:%d %b %Y} – {prev_f.end:%d %b %Y}" if kp else "n/a"),
     ("Orders in view", f"{len(fr.orders):,}")]), unsafe_allow_html=True)


def delta(key: str, points: bool = False):
    if not kp:
        return None
    if points:
        return k[key] - kp[key]
    return an.pct_change(k[key], kp[key])


tabs = st.tabs(["Overview", "Sales & Trends", "Customers", "Products", "Retention & Conversion",
                "Hypothesis Lab", "SQL Insights", "Recommendations"])

# ===================================================================== OVERVIEW
with tabs[0]:
    nd = None if kp else "no prior period in data"
    cards = [
        T.kpi_card("Net revenue", T.money(k["revenue"], 2), delta("revenue"), note=nd),
        T.kpi_card("Gross profit", T.money(k["profit"], 2), delta("profit"), note=nd),
        T.kpi_card("Gross margin", f"{k['margin']:.1%}", delta("margin", True), delta_is_points=True, note=nd),
        T.kpi_card("Orders", T.num(k["orders"]), delta("orders"), note=nd),
        T.kpi_card("Avg order value", f"${k['aov']:,.0f}", delta("aov"), note=nd),
        T.kpi_card("Customers", T.num(k["customers"]), delta("customers"), note=nd),
        T.kpi_card("Conversion rate", f"{k['conversion']:.2%}", delta("conversion", True), delta_is_points=True, note=nd),
        T.kpi_card("Return rate", f"{k['return_rate']:.1%}", delta("return_rate", True), invert=True,
                   delta_is_points=True, note=nd),
    ]
    st.markdown(T.kpi_grid(cards), unsafe_allow_html=True)

    c1, c2 = st.columns([1.7, 1])
    with c1:
        with st.container(border=True):
            tr = an.revenue_trend(fr.lines, "MS")
            tr["ma3"] = tr["revenue"].rolling(3, min_periods=1).mean()
            fig = go.Figure()
            fig.add_bar(x=tr["order_date"], y=tr["revenue"], name="Net revenue", marker_color=T.BLUE_RAMP[2],
                        hovertemplate="%{x|%b %Y}<br>Revenue: $%{y:,.0f}<extra></extra>")
            fig.add_scatter(x=tr["order_date"], y=tr["ma3"], name="3-month moving avg", mode="lines",
                            line=dict(color=T.SERIES[1], width=2.5),
                            hovertemplate="3M avg: $%{y:,.0f}<extra></extra>")
            fig.update_layout(title="Monthly net revenue", hovermode="x unified", yaxis_tickprefix="$",
                              yaxis_tickformat="~s")
            chart(fig, 340)
    with c2:
        with st.container(border=True):
            cat = an.category_performance(fr.lines)
            fig = px.bar(cat.sort_values("revenue"), x="revenue", y="category", orientation="h",
                         color="category", color_discrete_map=T.CATEGORY_COLORS,
                         custom_data=["share", "margin"])
            fig.update_traces(hovertemplate="<b>%{y}</b><br>Revenue: $%{x:,.0f}<br>Share: %{customdata[0]:.1%}"
                                            "<br>Margin: %{customdata[1]:.1%}<extra></extra>",
                              texttemplate="%{customdata[0]:.0%}", textposition="outside", cliponaxis=False)
            fig.update_layout(title="Revenue by category", showlegend=False, xaxis_tickprefix="$",
                              xaxis_tickformat="~s", yaxis_title=None, xaxis_title=None)
            pad_x(fig, cat["revenue"].max())
            chart(fig, 340)

    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            ch = an.dimension_breakdown(fr.orders, "channel")
            fig = px.pie(ch, values="revenue", names="channel", hole=0.62, color="channel",
                         color_discrete_map=T.CHANNEL_COLORS)
            fig.update_traces(textinfo="percent", marker=dict(line=dict(color=T.SURFACE, width=2)),
                              hovertemplate="<b>%{label}</b><br>$%{value:,.0f} (%{percent})<extra></extra>")
            fig.update_layout(title="Revenue by channel", legend=dict(orientation="v", y=0.5, x=1.02,
                                                                     yanchor="middle"))
            chart(fig, 300)
    with c2:
        with st.container(border=True):
            fn = an.funnel(fr.sessions)
            fig = go.Figure(go.Funnel(y=fn["stage"], x=fn["count"],
                                      texttemplate="%{value:,}<br>%{percentInitial:.1%}",
                                      marker=dict(color=[T.BLUE_RAMP[i] for i in (2, 3, 4, 5, 6)]),
                                      connector=dict(line=dict(color=T.GRID, width=1)),
                                      hovertemplate="<b>%{y}</b><br>%{x:,} sessions<extra></extra>"))
            fig.update_layout(title="Purchase funnel")
            chart(fig, 300)
    with c3:
        with st.container(border=True):
            seg = an.segment_summary(an.rfm(fr.orders))
            top = seg.sort_values("revenue", ascending=True).tail(6)
            fig = px.bar(top, x="revenue_share", y="segment", orientation="h", custom_data=["customers"])
            fig.update_traces(marker_color=T.SERIES[0], texttemplate="%{x:.0%}", textposition="outside",
                              cliponaxis=False,
                              hovertemplate="<b>%{y}</b><br>Revenue share: %{x:.1%}<br>"
                                            "Customers: %{customdata[0]:,}<extra></extra>")
            fig.update_layout(title="Revenue share by RFM segment", xaxis_tickformat=".0%", xaxis_title=None,
                              yaxis_title=None)
            pad_x(fig, top["revenue_share"].max())
            chart(fig, 300)

    st.markdown(T.section("Top recommendations", "Generated from the data in view - see the Recommendations "
                                                 "tab for the full list."), unsafe_allow_html=True)
    recs = insights.generate(fr)
    cols = st.columns(3)
    for col, rec in zip(cols, recs[:3]):
        col.markdown(T.rec_card(rec), unsafe_allow_html=True)

# =============================================================== SALES & TRENDS
with tabs[1]:
    gran = st.segmented_control("Granularity", ["Daily", "Weekly", "Monthly", "Quarterly"], default="Monthly",
                                key="gran")
    freq = {"Daily": "D", "Weekly": "W-MON", "Monthly": "MS", "Quarterly": "QS"}[gran or "Monthly"]
    tr = an.revenue_trend(fr.lines, freq)
    with st.container(border=True):
        metric = st.radio("Metric", ["Revenue", "Profit", "Orders"], horizontal=True, key="trend_metric",
                          label_visibility="collapsed")
        col = metric.lower()
        fig = go.Figure(go.Scatter(x=tr["order_date"], y=tr[col], mode="lines", fill="tozeroy",
                                   line=dict(color=T.SERIES[0], width=2), fillcolor="rgba(42,120,214,0.12)",
                                   hovertemplate="%{x|%d %b %Y}<br>" + metric + ": %{y:,.0f}<extra></extra>"))
        if col != "orders":
            fig.update_layout(yaxis_tickprefix="$", yaxis_tickformat="~s")
        fig.update_layout(title=f"{metric} over time ({(gran or 'Monthly').lower()})", hovermode="x unified")
        chart(fig, 360)

    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            g = tr.dropna(subset=["growth"]).copy()
            if freq == "D":
                g = an.revenue_trend(fr.lines, "MS").dropna(subset=["growth"])
            fig = go.Figure(go.Bar(
                x=g["order_date"], y=g["growth"],
                marker_color=np.where(g["growth"] >= 0, T.SERIES[0], T.SERIES[7]),
                hovertemplate="%{x|%b %Y}<br>Growth: %{y:+.1%}<extra></extra>"))
            fig.update_layout(title="Period-over-period revenue growth", yaxis_tickformat="+.0%",
                              showlegend=False)
            fig.add_hline(y=0, line_color=T.AXIS, line_width=1)
            chart(fig, 320)
            st.caption("Blue = growth, red = decline versus the previous period.")
    with c2:
        with st.container(border=True):
            yo = an.yoy_monthly(fr.lines)
            fig = go.Figure()
            for i, (yr, d) in enumerate(yo.groupby("year")):
                fig.add_scatter(x=d["month"], y=d["net_revenue"], name=str(yr), mode="lines+markers",
                                line=dict(color=T.SERIES[i % len(T.SERIES)], width=2), marker=dict(size=8),
                                hovertemplate=f"{yr} " + "%{x}: $%{y:,.0f}<extra></extra>")
            fig.update_layout(title="Year-over-year monthly comparison", yaxis_tickprefix="$",
                              yaxis_tickformat="~s", hovermode="x unified",
                              xaxis=dict(tickmode="array", tickvals=list(range(1, 13)),
                                         ticktext=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
                                                   "Sep", "Oct", "Nov", "Dec"]))
            chart(fig, 320)

    c1, c2 = st.columns([1, 1.2])
    with c1:
        with st.container(border=True):
            q = an.quarterly(fr.lines)
            fig = px.bar(q, x="quarter", y="revenue", color="year", barmode="group",
                         color_discrete_sequence=T.SERIES, custom_data=["yoy", "margin"])
            fig.update_traces(hovertemplate="%{x} %{fullData.name}<br>Revenue: $%{y:,.0f}<br>"
                                            "YoY: %{customdata[0]:+.1%}<br>Margin: %{customdata[1]:.1%}<extra></extra>")
            fig.update_layout(title="Quarterly revenue by year", yaxis_tickprefix="$", yaxis_tickformat="~s",
                              xaxis_title=None, yaxis_title=None)
            chart(fig, 330)
    with c2:
        with st.container(border=True):
            hm = an.weekday_hour_heatmap(fr.orders)
            fig = go.Figure(go.Heatmap(z=hm.values, x=hm.columns, y=hm.index,
                                       colorscale=[[0, T.BLUE_RAMP[0]], [1, T.BLUE_RAMP[7]]],
                                       xgap=2, ygap=2, colorbar=dict(thickness=10, tickprefix="$",
                                                                     tickformat="~s"),
                                       hovertemplate="%{y} %{x}:00<br>Revenue: $%{z:,.0f}<extra></extra>"))
            fig.update_layout(title="When do customers buy? (weekday × hour)", xaxis_title="Hour of day",
                              yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)"))
            chart(fig, 330)

    with st.expander("Quarterly table"):
        qt = an.quarterly(fr.lines)[["order_quarter", "revenue", "profit", "margin", "yoy"]]
        st.dataframe(qt, hide_index=True, width="stretch", column_config={
            "order_quarter": "Quarter",
            "revenue": st.column_config.NumberColumn("Net revenue", format="dollar"),
            "profit": st.column_config.NumberColumn("Gross profit", format="dollar"),
            "margin": st.column_config.NumberColumn("Margin", format="percent"),
            "yoy": st.column_config.NumberColumn("YoY growth", format="percent"),
        })

# ==================================================================== CUSTOMERS
with tabs[2]:
    r = an.rfm(fr.orders)
    seg = an.segment_summary(r)
    life = an.customer_lifetime(fr.orders)
    cards = [
        T.kpi_card("Buyers", T.num(len(r)), note="with ≥1 completed order"),
        T.kpi_card("Revenue / customer", f"${life['avg_revenue_per_customer']:,.0f}", delta("revenue_per_customer")),
        T.kpi_card("Orders / customer", f"{life['avg_orders_per_customer']:.2f}"),
        T.kpi_card("Repeat customer rate", f"{life['repeat_customer_rate']:.1%}", delta("repeat_rate", True),
                   delta_is_points=True),
        T.kpi_card("Median days between orders", f"{life['median_days_between_orders']:.0f}",
                   note="repeat buyers only"),
    ]
    st.markdown(T.kpi_grid(cards), unsafe_allow_html=True)

    st.markdown(T.section("RFM segmentation", "Customers scored 1-5 on Recency, Frequency and Monetary value, "
                                              "then mapped to actionable segments."), unsafe_allow_html=True)
    c1, c2 = st.columns([1.15, 1])
    with c1:
        with st.container(border=True):
            fig = go.Figure(go.Treemap(
                labels=seg["segment"], parents=[""] * len(seg), values=seg["customers"],
                customdata=seg[["customers", "revenue_share", "avg_monetary"]].to_numpy(),
                marker=dict(colors=seg["revenue_share"], coloraxis="coloraxis"), tiling=dict(pad=2)))
            fig.update_layout(coloraxis=dict(colorscale=[[0, T.BLUE_RAMP[0]], [1, T.BLUE_RAMP[6]]]))
            fig.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:,} customers<br>"
                                           "%{customdata[1]:.0%} of revenue",
                              hovertemplate="<b>%{label}</b><br>Customers: %{customdata[0]:,}<br>Revenue share: "
                                            "%{customdata[1]:.1%}<br>Avg spend: $%{customdata[2]:,.0f}<extra></extra>",
                              marker_line=dict(color=T.SURFACE, width=2), root_color=T.SURFACE)
            fig.update_layout(title="Segments sized by customers, shaded by revenue share",
                              coloraxis_colorbar=dict(title="Rev. share", tickformat=".0%", thickness=10),
                              margin=dict(t=56, l=4, r=4, b=4))
            chart(fig, 420)
    with c2:
        with st.container(border=True):
            fig = go.Figure()
            fig.add_bar(y=seg["segment"], x=seg["customer_share"], name="Share of customers", orientation="h",
                        marker_color=T.SERIES[0], hovertemplate="%{y}: %{x:.1%} of customers<extra></extra>")
            fig.add_bar(y=seg["segment"], x=seg["revenue_share"], name="Share of revenue", orientation="h",
                        marker_color=T.SERIES[1], hovertemplate="%{y}: %{x:.1%} of revenue<extra></extra>")
            fig.update_layout(title="Customer share vs revenue share", barmode="group", xaxis_tickformat=".0%",
                              yaxis=dict(autorange="reversed", title=None))
            chart(fig, 420)

    with st.container(border=True):
        st.dataframe(seg[["segment", "customers", "revenue", "avg_recency", "avg_frequency", "avg_monetary",
                          "action"]], hide_index=True, width="stretch", column_config={
            "segment": "Segment",
            "customers": st.column_config.NumberColumn("Customers", format="%d"),
            "revenue": st.column_config.NumberColumn("Revenue", format="dollar"),
            "avg_recency": st.column_config.NumberColumn("Avg recency (days)", format="%.0f"),
            "avg_frequency": st.column_config.NumberColumn("Avg orders", format="%.1f"),
            "avg_monetary": st.column_config.NumberColumn("Avg spend", format="dollar"),
            "action": st.column_config.TextColumn("Recommended action", width="large"),
        })

    st.markdown(T.section("Who are our customers?", "Revenue and value per customer across attributes."),
                unsafe_allow_html=True)
    dim_label = st.segmented_control("Breakdown", ["Acquisition channel", "Region", "Age group", "Gender",
                                                   "Device", "Customer type"], default="Acquisition channel",
                                     key="cust_dim")
    dim = {"Acquisition channel": "acquisition_channel", "Region": "region", "Age group": "age_group",
           "Gender": "gender", "Device": "device", "Customer type": "loyalty"}[dim_label or "Acquisition channel"]
    bd = an.dimension_breakdown(fr.orders, dim)
    if dim == "age_group":
        bd = bd.sort_values(dim)
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            fig = px.bar(bd, x=dim, y="revenue", custom_data=["customers", "orders"])
            fig.update_traces(marker_color=T.SERIES[0],
                              hovertemplate="<b>%{x}</b><br>Revenue: $%{y:,.0f}<br>Customers: %{customdata[0]:,}"
                                            "<br>Orders: %{customdata[1]:,}<extra></extra>")
            fig.update_layout(title=f"Net revenue by {dim_label.lower()}", yaxis_tickprefix="$",
                              yaxis_tickformat="~s", xaxis_title=None, yaxis_title=None)
            chart(fig, 320)
    with c2:
        with st.container(border=True):
            fig = px.bar(bd, x=dim, y="revenue_per_customer", custom_data=["aov"])
            fig.update_traces(marker_color=T.SERIES[2],
                              hovertemplate="<b>%{x}</b><br>Revenue / customer: $%{y:,.0f}<br>AOV: "
                                            "$%{customdata[0]:,.0f}<extra></extra>")
            fig.update_layout(title=f"Revenue per customer by {dim_label.lower()}", yaxis_tickprefix="$",
                              xaxis_title=None, yaxis_title=None)
            chart(fig, 320)

    with st.container(border=True):
        sample = r.sample(min(len(r), 2500), random_state=1)
        fig = px.scatter(sample, x="recency", y="monetary", size="frequency", color="segment",
                         category_orders={"segment": an.SEGMENT_ORDER}, size_max=18, opacity=0.65,
                         color_discrete_sequence=T.SERIES + ["#898781", "#52514e"], log_y=True,
                         hover_data={"customer_id": True, "frequency": True, "recency": True, "monetary": ":$,.0f"})
        fig.update_traces(marker=dict(line=dict(color=T.SURFACE, width=1)))
        fig.update_layout(legend_title_text="", margin=dict(t=100),
                          title="Recency vs spend (bubble = order count, sample of 2,500 buyers)",
                          xaxis_title="Days since last order", yaxis_title="Lifetime spend ($, log)",
                          yaxis=dict(tickvals=[10, 30, 100, 300, 1000, 3000, 10000],
                                     ticktext=["$10", "$30", "$100", "$300", "$1K", "$3K", "$10K"]))
        chart(fig, 440)
        st.caption("Ten segments exceed what colour alone can separate - hover a bubble or use the table above "
                   "for exact segment membership.")

# ===================================================================== PRODUCTS
with tabs[3]:
    cat = an.category_performance(fr.lines)
    prod = an.product_performance(fr.lines)
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            cs = cat.sort_values("revenue")
            fig = go.Figure()
            fig.add_bar(y=cs["category"], x=cs["revenue"], name="Net revenue", orientation="h",
                        marker_color=T.SERIES[0], hovertemplate="%{y}<br>Net revenue: $%{x:,.0f}<extra></extra>")
            fig.add_bar(y=cs["category"], x=cs["profit"], name="Gross profit", orientation="h",
                        marker_color=T.SERIES[2], hovertemplate="%{y}<br>Gross profit: $%{x:,.0f}<extra></extra>")
            fig.update_layout(title="Revenue vs gross profit by category", barmode="group", xaxis_tickprefix="$",
                              xaxis_tickformat="~s", xaxis_title=None, yaxis_title=None)
            chart(fig, 350)
    with c2:
        with st.container(border=True):
            fig = px.scatter(cat, x="margin", y="revenue", size="units", text="category", size_max=34,
                             custom_data=["return_rate", "units"])
            # alternate label positions by revenue rank so neighbouring bubbles don't stack labels
            pos = cat["revenue"].rank(ascending=False).astype(int).map(
                lambda r: "middle right" if r == 1 else ("top center" if r % 2 else "bottom center"))
            fig.update_traces(marker=dict(color=T.SERIES[0], opacity=0.75, line=dict(color=T.SURFACE, width=2)),
                              textposition=pos.tolist(), textfont=dict(color=T.INK_2, size=11),
                              hovertemplate="<b>%{text}</b><br>Margin: %{x:.1%}<br>Revenue: $%{y:,.0f}<br>"
                                            "Units: %{customdata[1]:,}<br>Return rate: %{customdata[0]:.1%}<extra></extra>")
            fig.add_vline(x=k["margin"], line_dash="dot", line_color=T.MUTED,
                          annotation_text=f"avg margin {k['margin']:.0%}", annotation_font_color=T.MUTED)
            fig.update_yaxes(range=[-0.08 * cat["revenue"].max(), cat["revenue"].max() * 1.22])
            fig.update_xaxes(range=[cat["margin"].min() - 0.06, cat["margin"].max() + 0.08])
            fig.update_layout(title="Category portfolio: margin vs revenue (bubble = units)",
                              xaxis_tickformat=".0%", yaxis_tickprefix="$", yaxis_tickformat="~s",
                              xaxis_title="Gross margin", yaxis_title="Net revenue")
            chart(fig, 350)

    c1, c2 = st.columns([1.3, 1])
    with c1:
        with st.container(border=True):
            fig = go.Figure()
            fig.add_scatter(x=prod["rank"] / len(prod), y=prod["cum_share"], mode="lines",
                            line=dict(color=T.SERIES[0], width=2.5), fill="tozeroy",
                            fillcolor="rgba(42,120,214,0.10)", name="Cumulative revenue",
                            customdata=prod[["product_name", "abc"]],
                            hovertemplate="Top %{x:.0%} of products<br>= %{y:.1%} of revenue<br>"
                                          "%{customdata[0]} (class %{customdata[1]})<extra></extra>")
            a_share = (prod["abc"] == "A").mean()
            fig.add_hline(y=0.8, line_dash="dot", line_color=T.MUTED)
            fig.add_vline(x=a_share, line_dash="dot", line_color=T.MUTED,
                          annotation_text=f"{a_share:.0%} of products → 80% of revenue",
                          annotation_position="bottom right", annotation_font_color=T.INK_2)
            fig.update_layout(title="Pareto curve (ABC analysis)", xaxis_tickformat=".0%", yaxis_tickformat=".0%",
                              xaxis_title="Share of products (ranked by revenue)", yaxis_title="Cumulative revenue",
                              showlegend=False)
            chart(fig, 340)
    with c2:
        with st.container(border=True):
            fig = px.bar(cat.sort_values("return_rate"), x="return_rate", y="category", orientation="h")
            avg_ret = cat["return_rate"].mean()
            fig.update_traces(marker_color=np.where(cat.sort_values("return_rate")["return_rate"] > avg_ret * 1.4,
                                                    T.SERIES[7], T.BLUE_RAMP[3]),
                              texttemplate="%{x:.1%}", textposition="outside", cliponaxis=False,
                              hovertemplate="%{y}: %{x:.1%} of orders returned<extra></extra>")
            fig.add_vline(x=avg_ret, line_dash="dot", line_color=T.MUTED)
            fig.update_layout(title="Return rate by category", xaxis_tickformat=".0%", xaxis_title=None,
                              yaxis_title=None)
            pad_x(fig, cat["return_rate"].max())
            chart(fig, 340)
            st.caption("Red bars: return rate more than 40% above the category average (dotted line).")

    with st.container(border=True):
        cm = an.category_month_matrix(fr.lines)
        cm_share = cm.div(cm.sum(axis=0), axis=1)
        fig = go.Figure(go.Heatmap(z=cm_share.values, x=cm_share.columns, y=cm_share.index,
                                   colorscale=[[0, T.BLUE_RAMP[0]], [1, T.BLUE_RAMP[7]]], xgap=2, ygap=2,
                                   customdata=cm.values,
                                   colorbar=dict(thickness=10, tickformat=".0%", title="Share"),
                                   hovertemplate="%{y} · %{x}<br>Share of month: %{z:.1%}<br>"
                                                 "Revenue: $%{customdata:,.0f}<extra></extra>"))
        fig.update_layout(title="Category mix by month (share of monthly revenue)",
                          yaxis=dict(gridcolor="rgba(0,0,0,0)"))
        chart(fig, 330)

    st.markdown(T.section("Product leaderboard"), unsafe_allow_html=True)
    c1, c2 = st.columns([1, 3])
    with c1:
        sort_by = st.radio("Rank by", ["revenue", "profit", "units", "margin"], horizontal=False,
                           format_func=str.title)
        top_n = st.slider("Show top", 10, 50, 15, step=5)
    with c2:
        lb = prod.sort_values(sort_by, ascending=False).head(top_n)
        st.dataframe(lb[["product_name", "category", "abc", "units", "orders", "revenue", "profit", "margin"]],
                     hide_index=True, width="stretch", height=min(38 * (top_n + 1), 560), column_config={
            "product_name": "Product", "category": "Category", "abc": "ABC",
            "units": st.column_config.NumberColumn("Units", format="%d"),
            "orders": st.column_config.NumberColumn("Orders", format="%d"),
            "revenue": st.column_config.ProgressColumn("Net revenue", format="dollar", min_value=0,
                                                       max_value=float(prod["revenue"].max())),
            "profit": st.column_config.NumberColumn("Gross profit", format="dollar"),
            "margin": st.column_config.NumberColumn("Margin", format="percent"),
        })

# ======================================================= RETENTION & CONVERSION
with tabs[4]:
    fn = an.funnel(fr.sessions)
    carts = fr.sessions["added_to_cart"].sum()
    abandon = 1 - fr.sessions["purchased"].sum() / carts if carts else np.nan
    pct, sizes = an.cohort_matrix(fr.orders, 12)
    curve = an.retention_curve(pct, sizes)
    m1 = curve.loc[curve["month"] == 1, "retention"]
    m3 = curve.loc[curve["month"] == 3, "retention"]
    cards = [
        T.kpi_card("Sessions", T.num(k["sessions"]), delta("sessions")),
        T.kpi_card("Conversion rate", f"{k['conversion']:.2%}", delta("conversion", True), delta_is_points=True),
        T.kpi_card("Add-to-cart rate", f"{fn.loc[2, 'pct_of_sessions']:.1%}", note="of all sessions"),
        T.kpi_card("Cart abandonment", f"{abandon:.1%}", note="carts without purchase"),
        T.kpi_card("Month-1 retention", f"{m1.iloc[0]:.1%}" if len(m1) else "–", note="bought again next month"),
        T.kpi_card("Month-3 retention", f"{m3.iloc[0]:.1%}" if len(m3) else "–", note="bought in month 3"),
    ]
    st.markdown(T.kpi_grid(cards), unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1.2])
    with c1:
        with st.container(border=True):
            fig = go.Figure(go.Funnel(
                y=fn["stage"], x=fn["count"], texttemplate="%{value:,} · %{percentPrevious:.0%} of prev.",
                marker=dict(color=[T.BLUE_RAMP[i] for i in (2, 3, 4, 5, 6)]),
                connector=dict(line=dict(color=T.GRID, width=1)),
                hovertemplate="<b>%{y}</b><br>%{x:,} sessions<br>%{percentPrevious:.1%} of previous step<extra></extra>"))
            fig.update_layout(title="Session funnel (with step conversion)")
            chart(fig, 360)
    with c2:
        with st.container(border=True):
            mc = an.monthly_conversion(fr.sessions)
            fig = go.Figure(go.Scatter(x=mc["session_start"], y=mc["conversion"], mode="lines+markers",
                                       line=dict(color=T.SERIES[0], width=2), marker=dict(size=8),
                                       customdata=mc[["sessions", "purchases"]],
                                       hovertemplate="%{x|%b %Y}<br>Conversion: %{y:.2%}<br>Sessions: "
                                                     "%{customdata[0]:,}<br>Purchases: %{customdata[1]:,}<extra></extra>"))
            fig.update_layout(title="Monthly session conversion rate", yaxis_tickformat=".1%",
                              hovermode="x unified")
            chart(fig, 360)

    c1, c2 = st.columns(2)
    for col, dim, title, cmap in [(c1, "traffic_channel", "Conversion by traffic channel", T.CHANNEL_COLORS),
                                  (c2, "device", "Conversion by device", T.DEVICE_COLORS)]:
        with col:
            with st.container(border=True):
                cb = an.conversion_by(fr.sessions, dim).sort_values("conversion")
                fig = px.bar(cb, x="conversion", y=dim, orientation="h", color=dim, color_discrete_map=cmap,
                             custom_data=["sessions", "cart_rate", "cart_abandonment"])
                fig.update_traces(texttemplate="%{x:.2%}", textposition="outside", cliponaxis=False,
                                  hovertemplate="<b>%{y}</b><br>Conversion: %{x:.2%}<br>Sessions: %{customdata[0]:,}"
                                                "<br>Add-to-cart: %{customdata[1]:.1%}<br>Cart abandonment: "
                                                "%{customdata[2]:.1%}<extra></extra>")
                fig.update_layout(title=title, showlegend=False, xaxis_tickformat=".1%", xaxis_title=None,
                                  yaxis_title=None)
                pad_x(fig, cb["conversion"].max())
                chart(fig, 300)

    st.markdown(T.section("Cohort retention",
                          "Customers grouped by first-purchase month in the selected window; cells show the % who "
                          "ordered again N months later. Note: customers already active before the window "
                          "start appear in the first cohort."), unsafe_allow_html=True)
    c1, c2 = st.columns([1.6, 1])
    with c1:
        with st.container(border=True):
            show = pct.drop(columns=[0], errors="ignore")
            text = np.where(np.isnan(show.values), "", np.vectorize(lambda v: f"{v:.0%}")(np.nan_to_num(show.values)))
            fig = go.Figure(go.Heatmap(z=show.values, x=[f"M{c}" for c in show.columns],
                                       y=[f"{c} (n={sizes[c]:,})" for c in show.index],
                                       text=text, texttemplate="%{text}", textfont=dict(size=10),
                                       colorscale=[[0, T.BLUE_RAMP[0]], [1, T.BLUE_RAMP[6]]], xgap=2, ygap=2,
                                       colorbar=dict(thickness=10, tickformat=".0%"),
                                       hovertemplate="Cohort %{y}<br>%{x}: %{z:.1%} retained<extra></extra>"))
            fig.update_layout(title="Monthly cohort retention", yaxis=dict(autorange="reversed",
                                                                           gridcolor="rgba(0,0,0,0)"))
            chart(fig, max(360, 22 * len(show) + 80))
    with c2:
        with st.container(border=True):
            cv = curve[curve["month"] > 0]
            fig = go.Figure(go.Scatter(x=cv["month"], y=cv["retention"], mode="lines+markers",
                                       line=dict(color=T.SERIES[0], width=2), marker=dict(size=8),
                                       hovertemplate="Month %{x}: %{y:.1%} retained<extra></extra>"))
            fig.update_layout(title="Average retention curve (customer-weighted)", yaxis_tickformat=".0%",
                              xaxis_title="Months since first purchase", yaxis_rangemode="tozero")
            chart(fig, 360)
            rep = read_sql(next(q.sql for q in load_queries() if q.slug == "09_repeat_purchase"))
            st.dataframe(rep[["frequency_band", "pct_customers", "pct_revenue"]], hide_index=True,
                         width="stretch", column_config={
                             "frequency_band": "Orders (all-time)",
                             "pct_customers": st.column_config.NumberColumn("% customers", format="%.1f%%"),
                             "pct_revenue": st.column_config.NumberColumn("% revenue", format="%.1f%%")})
            st.caption("Frequency bands are all-time (unfiltered), from SQL query 09.")

# ================================================================ HYPOTHESIS LAB
with tabs[5]:
    st.markdown(T.section("Hypothesis Lab", "Compare two customer groups on conversion rate or order value and "
                                            "decide whether the difference is real or noise."),
                unsafe_allow_html=True)
    DIMS = {"Customer type (loyalty)": "loyalty", "Checkout A/B variant": "checkout_variant",
            "Device": "device", "Traffic channel": "traffic_channel", "Region": "region", "Age group": "age_group",
            "Gender": "gender"}
    c1, c2, c3 = st.columns([1.2, 1, 1])
    with c1:
        metric_kind = st.radio("Metric", ["Conversion rate (sessions → purchase)",
                                          "Checkout completion (checkout → purchase)",
                                          "Average order value"], key="ht_metric")
    with c2:
        dim_name = st.selectbox("Split customers by", list(DIMS), key="ht_dim")
        dim = DIMS[dim_name]
        if metric_kind == "Average order value" and dim == "traffic_channel":
            dim = "channel"
        src = fr.orders if metric_kind == "Average order value" else fr.sessions
        levels = sorted(src[dim].dropna().unique())
        if dim == "loyalty":
            levels = ["Non-member", "Loyalty member"]
        ga = st.selectbox("Group A (control / baseline)", levels, index=0, key="ht_a")
        gb = st.selectbox("Group B (treatment / comparison)", [x for x in levels if x != ga], index=0, key="ht_b")
    with c3:
        alpha = st.select_slider("Significance level α", [0.01, 0.05, 0.10], value=0.05, key="ht_alpha")
        alt_label = st.radio("Alternative hypothesis", ["B ≠ A (two-sided)", "B > A", "B < A"], key="ht_alt")
        alternative = {"B ≠ A (two-sided)": "two-sided", "B > A": "larger", "B < A": "smaller"}[alt_label]

    sym = {"two-sided": "≠", "larger": ">", "smaller": "<"}[alternative]
    try:
        if metric_kind.startswith("Average order value"):
            o = src[src["status"] == "Completed"]
            a_vals = o.loc[o[dim] == ga, "net_revenue"].to_numpy()
            b_vals = o.loc[o[dim] == gb, "net_revenue"].to_numpy()
            res = st_tests.welch_ttest(a_vals, b_vals, group_a=ga, group_b=gb, alpha=alpha, alternative=alternative)
            fmt = "${:,.2f}"
            h0 = f"H₀: μ({gb}) = μ({ga})  —  mean order value is the same"
            h1 = f"H₁: μ({gb}) {sym} μ({ga})"
        else:
            s = src if metric_kind.startswith("Conversion") else src[src["began_checkout"] == 1]
            label = "conversion rate" if metric_kind.startswith("Conversion") else "checkout completion rate"
            a = s.loc[s[dim] == ga, "purchased"]
            b = s.loc[s[dim] == gb, "purchased"]
            res = st_tests.two_proportion_ztest(int(a.sum()), len(a), int(b.sum()), len(b), group_a=ga,
                                                group_b=gb, metric=label, alpha=alpha, alternative=alternative)
            fmt = "{:.2%}"
            h0 = f"H₀: p({gb}) = p({ga})  —  {label} is the same"
            h1 = f"H₁: p({gb}) {sym} p({ga})"
    except (ValueError, KeyError) as e:
        st.warning(f"Can't run this test with the current filters: {e}")
        res = None

    if res is not None:
        st.markdown(f'<div class="hypo"><b>Null</b> &nbsp;<span class="h">{h0}</span><br>'
                    f'<b>Alternative</b> &nbsp;<span class="h">{h1}</span> &nbsp;·&nbsp; α = {alpha}</div>',
                    unsafe_allow_html=True)
        is_rate = fmt.startswith("{:.2%")
        diff_txt = f"{res.difference * 100:+.2f} pts" if is_rate else f"{res.difference:+,.2f}"
        ci_txt = (f"{res.ci_low * 100:+.2f} to {res.ci_high * 100:+.2f} pts" if is_rate
                  else f"${res.ci_low:+,.2f} to ${res.ci_high:+,.2f}")
        cards = [
            T.kpi_card(f"A · {ga}", fmt.format(res.value_a), note=f"n = {res.n_a:,}"),
            T.kpi_card(f"B · {gb}", fmt.format(res.value_b), note=f"n = {res.n_b:,}"),
            T.kpi_card("Difference (B − A)", diff_txt, res.relative_lift, suffix="relative lift"),
            T.kpi_card("p-value", res.p_text(), note=f"α = {alpha}"),
            T.kpi_card(f"{int((1 - alpha) * 100)}% CI of difference", ci_txt, note=res.test, small=True),
        ]
        st.markdown(T.kpi_grid(cards), unsafe_allow_html=True)

        cls = "sig" if res.significant else "ns"
        icon = "✅" if res.significant else "⚪"
        st.markdown(f'<div class="verdict {cls}">{icon} <b>{"Statistically significant" if res.significant else "Not significant"}</b> — '
                    f'{res.verdict(fmt)}</div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            with st.container(border=True):
                if is_rate:
                    vals = [res.value_a, res.value_b]
                    ses = [np.sqrt(v * (1 - v) / n) for v, n in [(res.value_a, res.n_a), (res.value_b, res.n_b)]]
                    from scipy.stats import norm
                    zc = norm.ppf(1 - alpha / 2)
                    fig = go.Figure(go.Bar(x=[f"A · {ga}", f"B · {gb}"], y=vals, marker_color=T.GROUP_COLORS,
                                           error_y=dict(type="data", array=[zc * s for s in ses], color=T.INK_2,
                                                        thickness=1.5, width=8),
                                           text=[f"{v:.2%}" for v in vals], textposition="inside",
                                           insidetextanchor="middle", textfont=dict(color="#fff"),
                                           hovertemplate="%{x}<br>%{y:.2%}<extra></extra>"))
                    fig.update_layout(title=f"{res.metric.capitalize()} with {int((1 - alpha) * 100)}% CI",
                                      yaxis_tickformat=".1%", showlegend=False)
                else:
                    cap = np.quantile(np.r_[a_vals, b_vals], 0.98)
                    fig = go.Figure()
                    for vals, name, colr in [(a_vals, f"A · {ga}", T.GROUP_COLORS[0]),
                                             (b_vals, f"B · {gb}", T.GROUP_COLORS[1])]:
                        fig.add_histogram(x=np.clip(vals, 0, cap), name=name, marker_color=colr, opacity=0.6,
                                          histnorm="probability density", nbinsx=50)
                        fig.add_vline(x=vals.mean(), line_color=colr, line_width=2, line_dash="dash")
                    fig.update_layout(title="Order value distribution (dashed = mean, top 2% clipped)",
                                      barmode="overlay", xaxis_tickprefix="$", yaxis_title="Density")
                chart(fig, 340)
        with c2:
            with st.container(border=True):
                if is_rate:
                    a_arr = np.r_[np.ones(int(round(res.value_a * res.n_a))), np.zeros(res.n_a - int(round(res.value_a * res.n_a)))]
                    b_arr = np.r_[np.ones(int(round(res.value_b * res.n_b))), np.zeros(res.n_b - int(round(res.value_b * res.n_b)))]
                else:
                    a_arr, b_arr = a_vals, b_vals
                lo, hi, boots = st_tests.bootstrap_diff_ci(a_arr, b_arr, n_boot=1500, alpha=alpha)
                scale = 100 if is_rate else 1
                fig = go.Figure(go.Histogram(x=boots * scale, nbinsx=50, marker_color=T.BLUE_RAMP[3],
                                             hovertemplate="Δ %{x:.2f}<br>%{y} resamples<extra></extra>"))
                fig.add_vrect(x0=lo * scale, x1=hi * scale, fillcolor=T.SERIES[0], opacity=0.08, line_width=0)
                fig.add_vline(x=0, line_color=T.SERIES[7], line_width=2,
                              annotation_text="no difference", annotation_font_color=T.SERIES[7])
                fig.add_vline(x=res.difference * scale, line_color=T.INK, line_width=2, line_dash="dash",
                              annotation_text="observed", annotation_position="top left")
                fig.update_layout(title=f"Bootstrap distribution of B − A ({'pts' if is_rate else '$'})",
                                  showlegend=False, yaxis_title="Resamples")
                chart(fig, 340)
                st.caption(f"Bootstrap {int((1 - alpha) * 100)}% CI: [{lo * scale:+.2f}, {hi * scale:+.2f}] "
                           f"{'pts' if is_rate else '$'}. If the shaded band excludes the red line, the difference "
                           "is unlikely to be noise.")

        with st.expander("Test details & assumptions"):
            rows = {"Test": res.test, "Statistic": f"{res.statistic:.4f}", "p-value": f"{res.p_value:.6g}",
                    "Effect size": f"{res.effect_size:.3f} ({res.effect_label}; "
                                   f"{'Cohen h' if is_rate else 'Cohen d'})",
                    "n (A / B)": f"{res.n_a:,} / {res.n_b:,}"}
            if is_rate:
                rows["Chi-square (cross-check)"] = f"χ² = {res.extra['chi2']:.3f}, p = {res.extra['chi2_p']:.6g}"
                rows["Achieved power"] = f"{st_tests.achieved_power(res.value_a, res.value_b, res.n_a, res.n_b, alpha):.1%}"
            else:
                rows["Welch df"] = f"{res.extra['df']:.1f}"
                rows["Mann-Whitney U (non-parametric)"] = f"U = {res.extra['mann_whitney_u']:,.0f}, p = {res.extra['mann_whitney_p']:.6g}"
                rows["Medians (A / B)"] = f"${res.extra['median_a']:,.2f} / ${res.extra['median_b']:,.2f}"
            st.table(pd.DataFrame(rows.items(), columns=["", "Value"]).set_index(""))
            st.markdown(
                "- **Two-proportion z-test** assumes independent observations and ≥10 successes and failures per "
                "group. Sessions from the same customer are not fully independent, so treat borderline p-values "
                "with care.\n"
                "- **Welch's t-test** does not assume equal variances; order values are right-skewed, so the "
                "**Mann-Whitney U** test and the **bootstrap** CI are shown as robustness checks.\n"
                "- Observational splits (loyalty, device, region) show *association*, not causation. Only the "
                "randomised **checkout A/B variant** supports a causal conclusion.")

        with st.container(border=True):
            st.markdown("**Sample-size planner** — how many observations per group to detect a given lift?")
            p1, p2, p3 = st.columns(3)
            base = p1.number_input("Baseline rate", 0.001, 0.99, float(round(res.value_a, 4)) if is_rate else 0.05,
                                   step=0.005, format="%.3f")
            mde = p2.number_input("Minimum detectable lift (relative)", 0.01, 2.0, 0.10, step=0.01, format="%.2f")
            power = p3.select_slider("Power", [0.7, 0.8, 0.9, 0.95], value=0.8)
            n_req = st_tests.required_sample_size(base, mde, alpha, power)
            st.markdown(f"Need **{n_req:,}** observations per group (α = {alpha}, power = {power:.0%}) to detect "
                        f"{base:.2%} → {base * (1 + mde):.2%}.")

# ================================================================== SQL INSIGHTS
with tabs[6]:
    st.markdown(T.section("SQL business insights", "Curated queries from sql/queries/ run live against the SQLite "
                                                   "warehouse (not affected by sidebar filters)."),
                unsafe_allow_html=True)
    queries = load_queries()
    c1, c2 = st.columns([1, 2.2])
    with c1:
        qsel = st.radio("Query", queries, format_func=lambda q: f"{q.slug[:2]} · {q.title}", key="sqlq",
                        label_visibility="collapsed")
    with c2:
        st.markdown(f"#### {qsel.title}")
        st.markdown(f"*Business question:* {qsel.question}")
        res_df = read_sql(qsel.sql)
        st.dataframe(res_df, hide_index=True, width="stretch")
        num_cols = [c for c in res_df.columns[1:] if pd.api.types.is_numeric_dtype(res_df[c])]
        if num_cols and len(res_df) > 1:
            ycol = st.selectbox("Chart column", num_cols, key=f"ycol_{qsel.slug}")
            xcol = res_df.columns[0] if res_df.columns[0] not in ("overall_rank", "customer_id") else res_df.columns[1]
            fig = px.bar(res_df.astype({xcol: str}), x=xcol, y=ycol)
            fig.update_xaxes(type="category")
            fig.update_traces(marker_color=T.SERIES[0], hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>")
            fig.update_layout(title=f"{ycol} by {xcol}", xaxis_title=None, yaxis_title=None)
            chart(fig, 300)
        with st.expander("Show SQL", expanded=False):
            st.code(qsel.sql, language="sql")
        st.download_button("Download result (CSV)", res_df.to_csv(index=False), f"{qsel.slug}.csv", "text/csv")

    st.markdown(T.section("Ad-hoc SQL", "Read-only. Tables: customers, products, sessions, orders, order_items; "
                                        "views: v_order_lines, v_orders."), unsafe_allow_html=True)
    sql = st.text_area("SQL", "SELECT category, ROUND(SUM(net_revenue), 0) AS revenue\nFROM v_order_lines\n"
                              "GROUP BY category\nORDER BY revenue DESC;", height=140, label_visibility="collapsed")
    if st.button("Run query", type="primary"):
        try:
            st.dataframe(run_readonly(sql), hide_index=True, width="stretch")
        except Exception as e:  # surface SQL errors to the user
            st.error(f"{type(e).__name__}: {e}")

# =============================================================== RECOMMENDATIONS
with tabs[7]:
    recs = insights.generate(fr)
    st.markdown(T.section("Actionable recommendations",
                          f"{len(recs)} recommendations generated from the data in view, ranked by priority and "
                          "estimated annual impact. Change the filters to re-run them for a segment."),
                unsafe_allow_html=True)
    areas = sorted({r.area for r in recs})
    pick = st.pills("Area", areas, selection_mode="multi", default=areas, key="rec_area")
    shown = [r for r in recs if r.area in (pick or areas)]
    total = sum(r.impact for r in shown)
    st.markdown(T.kpi_grid([T.kpi_card("Estimated annual opportunity (shown)", T.money(total),
                                       note="back-of-envelope, for prioritisation"),
                            T.kpi_card("High-priority items", str(sum(r.priority == "High" for r in shown)),
                                       note="≥3% of annual revenue at stake")]), unsafe_allow_html=True)
    st.write("")
    cols = st.columns(2)
    for i, rec in enumerate(shown):
        cols[i % 2].markdown(T.rec_card(rec), unsafe_allow_html=True)
    if recs:
        st.download_button("Download recommendations (CSV)", insights.to_frame(recs).to_csv(index=False),
                           "recommendations.csv", "text/csv")

st.markdown('<div class="footer">Built with SQL (SQLite) · Python (pandas, SciPy) · Streamlit & Plotly · '
            'Power BI / Tableau extracts in <code>exports/</code></div>', unsafe_allow_html=True)
