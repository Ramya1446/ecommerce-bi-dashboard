"""Pandas analytics layer: loads the warehouse once, then computes every dashboard metric
from filtered frames so all charts respect the same sidebar filters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .db import DEFAULT_DB, read_sql


@dataclass
class Frames:
    lines: pd.DataFrame      # one row per order line (v_order_lines + customer attributes)
    orders: pd.DataFrame     # one row per order (v_orders + customer attributes)
    sessions: pd.DataFrame   # one row per session (+ customer attributes)
    customers: pd.DataFrame


CUSTOMER_COLS = "c.region, c.age_group, c.gender, c.acquisition_channel, c.is_loyalty_member"


def load_frames(db_path: Path = DEFAULT_DB) -> Frames:
    lines = read_sql(f"""SELECT l.*, {CUSTOMER_COLS}
                        FROM v_order_lines l JOIN customers c USING (customer_id)""", db_path)
    orders = read_sql(f"""SELECT o.*, s.checkout_variant, {CUSTOMER_COLS}
                         FROM v_orders o
                         JOIN orders   r ON r.order_id = o.order_id
                         LEFT JOIN sessions s ON s.session_id = r.session_id
                         JOIN customers c ON c.customer_id = o.customer_id""", db_path)
    sessions = read_sql(f"""SELECT s.*, {CUSTOMER_COLS}
                           FROM sessions s JOIN customers c USING (customer_id)""", db_path)
    customers = read_sql("SELECT * FROM customers", db_path)

    lines["order_date"] = pd.to_datetime(lines["order_date"])
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    sessions["session_start"] = pd.to_datetime(sessions["session_start"])
    customers["signup_date"] = pd.to_datetime(customers["signup_date"])
    for df in (lines, orders, sessions, customers):
        df["loyalty"] = np.where(df["is_loyalty_member"] == 1, "Loyalty member", "Non-member")
    return Frames(lines, orders, sessions, customers)


@dataclass
class Filters:
    start: pd.Timestamp
    end: pd.Timestamp
    categories: list[str] | None = None
    channels: list[str] | None = None
    regions: list[str] | None = None
    devices: list[str] | None = None
    loyalty: list[str] | None = None


def _apply(df: pd.DataFrame, f: Filters, date_col: str, channel_col: str) -> pd.DataFrame:
    end = f.end + pd.Timedelta(days=1)
    m = (df[date_col] >= f.start) & (df[date_col] < end)
    if f.channels:
        m &= df[channel_col].isin(f.channels)
    if f.regions:
        m &= df["region"].isin(f.regions)
    if f.devices:
        m &= df["device"].isin(f.devices)
    if f.loyalty:
        m &= df["loyalty"].isin(f.loyalty)
    return df[m]


def apply_filters(fr: Frames, f: Filters) -> Frames:
    lines = _apply(fr.lines, f, "order_date", "channel")
    if f.categories:
        lines = lines[lines["category"].isin(f.categories)]
    orders = _apply(fr.orders, f, "order_date", "channel")
    if f.categories:  # keep orders that contain at least one line in the chosen categories
        orders = orders[orders["order_id"].isin(lines["order_id"])]
    sessions = _apply(fr.sessions, f, "session_start", "traffic_channel")
    return Frames(lines, orders, sessions, fr.customers)


def previous_period(f: Filters) -> Filters:
    span = f.end - f.start + pd.Timedelta(days=1)
    return Filters(f.start - span, f.start - pd.Timedelta(days=1), f.categories,
                   f.channels, f.regions, f.devices, f.loyalty)


# --------------------------------------------------------------------------- KPIs
def kpis(fr: Frames) -> dict[str, float]:
    lines, orders, sessions = fr.lines, fr.orders, fr.sessions
    completed = orders[orders["status"] == "Completed"]
    shipped = orders[orders["status"] != "Cancelled"]
    revenue = lines["net_revenue"].sum()
    n_completed = completed["order_id"].nunique()
    buyers = completed["customer_id"].nunique()
    repeat = (completed.groupby("customer_id").size() > 1).sum()
    return {
        "revenue": revenue,
        "profit": lines["gross_profit"].sum(),
        "margin": lines["gross_profit"].sum() / revenue if revenue else np.nan,
        "orders": n_completed,
        "aov": revenue / n_completed if n_completed else np.nan,
        "customers": buyers,
        "units": lines.loc[lines["status"] == "Completed", "quantity"].sum(),
        "conversion": sessions["purchased"].mean() if len(sessions) else np.nan,
        "sessions": len(sessions),
        "return_rate": (shipped["status"] == "Returned").mean() if len(shipped) else np.nan,
        "repeat_rate": repeat / buyers if buyers else np.nan,
        "revenue_per_customer": revenue / buyers if buyers else np.nan,
    }


def pct_change(cur: float, prev: float) -> float | None:
    if prev is None or prev == 0 or np.isnan(prev) or np.isnan(cur):
        return None
    return (cur - prev) / abs(prev)


# ------------------------------------------------------------------------- trends
def revenue_trend(lines: pd.DataFrame, freq: str = "MS") -> pd.DataFrame:
    """freq: 'D', 'W-MON', 'MS' (month) or 'QS' (quarter)."""
    g = (lines.set_index("order_date")
         .resample(freq)
         .agg(revenue=("net_revenue", "sum"), profit=("gross_profit", "sum"),
              orders=("order_id", "nunique"))
         .reset_index())
    g["growth"] = g["revenue"].pct_change()
    return g


def yoy_monthly(lines: pd.DataFrame) -> pd.DataFrame:
    g = lines.groupby([lines["order_date"].dt.year.rename("year"),
                       lines["order_date"].dt.month.rename("month")])["net_revenue"].sum()
    return g.reset_index()


def quarterly(lines: pd.DataFrame) -> pd.DataFrame:
    g = lines.groupby("order_quarter").agg(revenue=("net_revenue", "sum"),
                                           profit=("gross_profit", "sum")).reset_index()
    g["year"] = g["order_quarter"].str[:4]
    g["quarter"] = g["order_quarter"].str[-2:]
    g["margin"] = g["profit"] / g["revenue"]
    prev = g.set_index(["year", "quarter"])["revenue"]
    g["yoy"] = [
        (r / prev.get((str(int(y) - 1), q)) - 1) if (str(int(y) - 1), q) in prev.index else np.nan
        for y, q, r in zip(g["year"], g["quarter"], g["revenue"])
    ]
    return g


def weekday_hour_heatmap(orders: pd.DataFrame) -> pd.DataFrame:
    o = orders[orders["status"] == "Completed"]
    t = pd.to_datetime(o["order_date"])
    return (o.assign(weekday=t.dt.day_name().str[:3], hour=t.dt.hour)
             .pivot_table(index="weekday", columns="hour", values="net_revenue", aggfunc="sum", fill_value=0)
             .reindex(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]))


# ----------------------------------------------------------------------- products
def category_performance(lines: pd.DataFrame) -> pd.DataFrame:
    shipped = lines[lines["status"] != "Cancelled"]
    ret = (shipped.groupby("category")
           .apply(lambda g: g.loc[g["status"] == "Returned", "order_id"].nunique() / g["order_id"].nunique(),
                  include_groups=False)
           .rename("return_rate"))
    g = lines.groupby("category").agg(revenue=("net_revenue", "sum"), profit=("gross_profit", "sum"),
                                      discount=("discount_amount", "sum"))
    g["units"] = lines[lines["status"] == "Completed"].groupby("category")["quantity"].sum()
    g["margin"] = g["profit"] / g["revenue"]
    g["share"] = g["revenue"] / g["revenue"].sum()
    g = g.join(ret)
    return g.sort_values("revenue", ascending=False).reset_index()


def product_performance(lines: pd.DataFrame) -> pd.DataFrame:
    done = lines[lines["status"] == "Completed"]
    g = lines.groupby(["product_id", "product_name", "category"]).agg(
        revenue=("net_revenue", "sum"), profit=("gross_profit", "sum"),
        orders=("order_id", "nunique")).reset_index()
    g["units"] = g["product_id"].map(done.groupby("product_id")["quantity"].sum()).fillna(0).astype(int)
    g["margin"] = g["profit"] / g["revenue"].replace(0, np.nan)
    g = g.sort_values("revenue", ascending=False).reset_index(drop=True)
    total = g["revenue"].sum()
    g["cum_share"] = g["revenue"].cumsum() / total if total else 0
    g["abc"] = np.select([g["cum_share"] <= 0.80, g["cum_share"] <= 0.95], ["A", "B"], "C")
    g["rank"] = np.arange(1, len(g) + 1)
    return g


def category_month_matrix(lines: pd.DataFrame) -> pd.DataFrame:
    return lines.pivot_table(index="category", columns="order_month", values="net_revenue",
                             aggfunc="sum", fill_value=0)


# ---------------------------------------------------------------------- customers
SEGMENT_ORDER = ["Champions", "Loyal Customers", "Potential Loyalists", "New Customers",
                 "Promising", "Need Attention", "At Risk", "Can't Lose Them", "Hibernating", "Lost"]

SEGMENT_ACTIONS = {
    "Champions": "Reward them: early access, referral programme, ask for reviews.",
    "Loyal Customers": "Upsell higher-value items; invite to the loyalty tier.",
    "Potential Loyalists": "Offer membership / bundles to lock in the habit.",
    "New Customers": "Onboarding flow and a time-boxed second-order incentive.",
    "Promising": "Build familiarity: personalised recommendations, free shipping threshold.",
    "Need Attention": "Limited-time offers based on past categories.",
    "At Risk": "Win-back email series with a personalised discount.",
    "Can't Lose Them": "High-value lapsing customers: outreach and a strong save offer.",
    "Hibernating": "Low-cost reactivation; suppress from paid retargeting if no response.",
    "Lost": "Exclude from spend-heavy campaigns; one final reactivation attempt.",
}


def rfm(orders: pd.DataFrame, snapshot: pd.Timestamp | None = None) -> pd.DataFrame:
    done = orders[orders["status"] == "Completed"]
    if done.empty:
        return pd.DataFrame(columns=["customer_id", "recency", "frequency", "monetary", "R", "F", "M", "segment"])
    snapshot = snapshot or done["order_date"].max().normalize() + pd.Timedelta(days=1)
    g = done.groupby("customer_id").agg(
        last=("order_date", "max"), frequency=("order_id", "nunique"), monetary=("net_revenue", "sum"))
    g["recency"] = (snapshot - g["last"]).dt.days

    def score(s: pd.Series, reverse: bool = False) -> pd.Series:
        # rank first so ties do not break qcut's bin edges
        r = s.rank(method="first", ascending=not reverse)
        return pd.qcut(r, 5, labels=[1, 2, 3, 4, 5]).astype(int)

    g["R"] = score(g["recency"], reverse=True)
    g["F"] = score(g["frequency"])
    g["M"] = score(g["monetary"])
    g["RFM"] = g["R"].astype(str) + g["F"].astype(str) + g["M"].astype(str)
    g["segment"] = [_segment(r, f, m) for r, f, m in zip(g["R"], g["F"], g["M"])]
    return g.reset_index()


def _segment(r: int, f: int, m: int) -> str:
    fm = (f + m) / 2
    if r >= 4 and fm >= 4:
        return "Champions"
    if r >= 3 and fm >= 3.5:
        return "Loyal Customers"
    if r >= 4 and fm >= 2.5:
        return "Potential Loyalists"
    if r >= 4 and f <= 1:
        return "New Customers"
    if r >= 4:
        return "Promising"
    if r == 3 and fm >= 2:
        return "Need Attention"
    if r <= 2 and fm >= 4.5:
        return "Can't Lose Them"
    if r <= 2 and fm >= 3:
        return "At Risk"
    if r == 2 or (r == 3):
        return "Hibernating"
    return "Lost"


def segment_summary(r: pd.DataFrame) -> pd.DataFrame:
    if r.empty:
        return pd.DataFrame()
    g = r.groupby("segment").agg(customers=("customer_id", "count"), revenue=("monetary", "sum"),
                                 avg_recency=("recency", "mean"), avg_frequency=("frequency", "mean"),
                                 avg_monetary=("monetary", "mean"))
    g["customer_share"] = g["customers"] / g["customers"].sum()
    g["revenue_share"] = g["revenue"] / g["revenue"].sum()
    g["action"] = g.index.map(SEGMENT_ACTIONS)
    order = [s for s in SEGMENT_ORDER if s in g.index]
    return g.loc[order].reset_index()


def dimension_breakdown(orders: pd.DataFrame, dim: str) -> pd.DataFrame:
    done = orders[orders["status"] == "Completed"]
    g = done.groupby(dim).agg(revenue=("net_revenue", "sum"), orders=("order_id", "nunique"),
                              customers=("customer_id", "nunique"))
    g["aov"] = g["revenue"] / g["orders"]
    g["revenue_per_customer"] = g["revenue"] / g["customers"]
    return g.sort_values("revenue", ascending=False).reset_index()


# ------------------------------------------------------------ retention & conversion
def cohort_matrix(orders: pd.DataFrame, max_months: int = 12) -> tuple[pd.DataFrame, pd.Series]:
    o = orders[orders["status"] != "Cancelled"][["customer_id", "order_date"]].copy()
    if o.empty:
        return pd.DataFrame(), pd.Series(dtype=float)
    o["month"] = o["order_date"].dt.to_period("M")
    o["cohort"] = o.groupby("customer_id")["month"].transform("min")
    o["n"] = (o["month"] - o["cohort"]).apply(lambda x: x.n)
    o = o[o["n"] <= max_months]
    counts = o.groupby(["cohort", "n"])["customer_id"].nunique().unstack(fill_value=0)
    sizes = counts[0]
    pct = counts.div(sizes, axis=0)
    pct.index = pct.index.astype(str)
    sizes.index = sizes.index.astype(str)
    # blank out cells in the future (cohort + n beyond the data's last month)
    last = o["month"].max()
    for cohort in pct.index:
        horizon = (last - pd.Period(cohort, "M")).n
        pct.loc[cohort, pct.columns > horizon] = np.nan
    return pct, sizes


def retention_curve(pct: pd.DataFrame, sizes: pd.Series) -> pd.DataFrame:
    """Customer-weighted average retention by months since first purchase."""
    rows = []
    for n in pct.columns:
        valid = pct[n].notna()
        if valid.sum() == 0:
            continue
        w = sizes[valid]
        rows.append({"month": n, "retention": float((pct.loc[valid, n] * w).sum() / w.sum())})
    return pd.DataFrame(rows)


def funnel(sessions: pd.DataFrame) -> pd.DataFrame:
    steps = [("Sessions", None), ("Viewed product", "viewed_product"), ("Added to cart", "added_to_cart"),
             ("Began checkout", "began_checkout"), ("Purchased", "purchased")]
    n = len(sessions)
    vals = [n] + [int(sessions[c].sum()) for _, c in steps[1:]]
    df = pd.DataFrame({"stage": [s for s, _ in steps], "count": vals})
    df["pct_of_sessions"] = df["count"] / n if n else np.nan
    df["step_conversion"] = df["count"] / df["count"].shift(1)
    return df


def conversion_by(sessions: pd.DataFrame, dim: str) -> pd.DataFrame:
    g = sessions.groupby(dim).agg(sessions=("session_id", "count"), carts=("added_to_cart", "sum"),
                                  checkouts=("began_checkout", "sum"), purchases=("purchased", "sum"))
    g["conversion"] = g["purchases"] / g["sessions"]
    g["cart_rate"] = g["carts"] / g["sessions"]
    g["cart_abandonment"] = 1 - g["purchases"] / g["carts"].replace(0, np.nan)
    return g.sort_values("conversion", ascending=False).reset_index()


def monthly_conversion(sessions: pd.DataFrame) -> pd.DataFrame:
    return (sessions.set_index("session_start").resample("MS")
            .agg(sessions=("session_id", "count"), purchases=("purchased", "sum"))
            .assign(conversion=lambda d: d["purchases"] / d["sessions"]).reset_index())


def customer_lifetime(orders: pd.DataFrame) -> dict[str, float]:
    done = orders[orders["status"] == "Completed"]
    if done.empty:
        return {}
    per = done.groupby("customer_id").agg(orders=("order_id", "nunique"), revenue=("net_revenue", "sum"),
                                          first=("order_date", "min"), last=("order_date", "max"))
    repeaters = per[per["orders"] > 1]
    gaps = (repeaters["last"] - repeaters["first"]).dt.days / (repeaters["orders"] - 1)
    return {
        "avg_orders_per_customer": per["orders"].mean(),
        "avg_revenue_per_customer": per["revenue"].mean(),
        "median_days_between_orders": float(gaps.median()) if len(gaps) else np.nan,
        "repeat_customer_rate": (per["orders"] > 1).mean(),
        "repeat_revenue_share": per.loc[per["orders"] > 1, "revenue"].sum() / per["revenue"].sum(),
    }
