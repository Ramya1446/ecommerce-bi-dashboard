"""Rule-based recommendation engine.

Every recommendation is derived from the (filtered) data at runtime: the rule decides
*whether* to fire, the numbers in the text come from the data, and a rough annualised
impact estimate is attached so recommendations can be ranked. Impact estimates are
deliberately conservative, back-of-envelope figures - they are for prioritisation,
not forecasts.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import analytics as an
from . import stats as st


@dataclass
class Recommendation:
    area: str
    priority: str          # High / Medium / Low
    title: str
    finding: str
    action: str
    impact: float          # estimated annualised net revenue (or profit) at stake, in $
    impact_basis: str


def _p(p: float) -> str:
    return f"{p:.4f}" if p >= 1e-4 else f"{p:.1e}"


def _annualise(fr: an.Frames) -> float:
    if fr.orders.empty:
        return 1.0
    days = (fr.orders["order_date"].max() - fr.orders["order_date"].min()).days + 1
    return 365.0 / max(days, 1)


def _priority(impact: float, revenue: float) -> str:
    share = impact / revenue if revenue else 0
    return "High" if share >= 0.03 else "Medium" if share >= 0.01 else "Low"


def generate(fr: an.Frames) -> list[Recommendation]:
    if fr.orders.empty or fr.sessions.empty:
        return []
    recs: list[Recommendation] = []
    k = an.kpis(fr)
    ann = _annualise(fr)
    annual_rev = k["revenue"] * ann
    aov = k["aov"] if not np.isnan(k["aov"]) else 0

    # 1. Device conversion gap ----------------------------------------------------
    dev = an.conversion_by(fr.sessions, "device").set_index("device")
    if {"Mobile", "Desktop"} <= set(dev.index):
        m, d = dev.loc["Mobile"], dev.loc["Desktop"]
        gap = 1 - m["conversion"] / d["conversion"] if d["conversion"] else 0
        if gap > 0.15:
            uplift = m["sessions"] * (d["conversion"] - m["conversion"]) * 0.25 * aov * ann
            recs.append(Recommendation(
                "Conversion", "", "Close the mobile conversion gap",
                f"Mobile carries {m['sessions'] / dev['sessions'].sum():.0%} of sessions but converts at "
                f"{m['conversion']:.2%} vs {d['conversion']:.2%} on desktop ({gap:.0%} lower).",
                "Audit the mobile checkout (form length, payment options such as wallets, page speed). "
                "Prioritise one-tap payments and guest checkout on mobile.",
                uplift, "closing 25% of the mobile-desktop gap at current AOV"))

    # 2. Channel efficiency ---------------------------------------------------------
    ch = an.conversion_by(fr.sessions, "traffic_channel")
    if len(ch) >= 2:
        best, worst = ch.iloc[0], ch.iloc[-1]
        if worst["conversion"] > 0 and best["conversion"] / worst["conversion"] > 1.4:
            moved = worst["sessions"] * 0.15
            uplift = moved * (best["conversion"] - worst["conversion"]) * aov * ann
            recs.append(Recommendation(
                "Marketing", "", f"Shift budget from {worst['traffic_channel']} toward {best['traffic_channel']}",
                f"{best['traffic_channel']} converts at {best['conversion']:.2%}, "
                f"{best['conversion'] / worst['conversion']:.1f}x {worst['traffic_channel']} ({worst['conversion']:.2%}).",
                f"Re-allocate ~15% of {worst['traffic_channel']} spend to {best['traffic_channel']} "
                f"(e.g. list growth, lifecycle campaigns) and use {worst['traffic_channel']} for awareness, judged on assisted conversions.",
                uplift, f"15% of {worst['traffic_channel']} sessions converting at the {best['traffic_channel']} rate"))

    # 3. Cart abandonment -------------------------------------------------------------
    carts = fr.sessions["added_to_cart"].sum()
    purchases = fr.sessions["purchased"].sum()
    if carts:
        abandon = 1 - purchases / carts
        if abandon > 0.5:
            uplift = (carts - purchases) * 0.05 * aov * ann
            recs.append(Recommendation(
                "Conversion", "", "Launch a cart-abandonment recovery flow",
                f"{abandon:.0%} of carts are abandoned ({carts - purchases:,.0f} carts in the period).",
                "Trigger a 3-step email/push sequence (1h, 24h, 72h) with the cart contents; "
                "show shipping cost earlier to avoid checkout surprises.",
                uplift, "recovering 5% of abandoned carts at current AOV"))

    # 4. High-share, low-margin category ------------------------------------------------
    cat = an.category_performance(fr.lines)
    if len(cat) >= 2:
        overall_margin = k["margin"]
        thin = cat[(cat["share"] >= 0.2) & (cat["margin"] < overall_margin * 0.7)]
        for _, r in thin.iterrows():
            uplift = r["revenue"] * 0.02 * ann
            recs.append(Recommendation(
                "Product", "", f"Protect margin in {r['category']}",
                f"{r['category']} is {r['share']:.0%} of revenue but runs a {r['margin']:.1%} gross margin "
                f"vs {overall_margin:.1%} overall.",
                f"Attach high-margin accessories/bundles to {r['category']} orders, review supplier costs on the "
                f"top SKUs and cap promo depth on this category.",
                uplift, "+2pt margin on category revenue (profit)"))

        # 5. Return-heavy category
        avg_ret = cat["return_rate"].mean()
        hot = cat[cat["return_rate"] > avg_ret * 1.4]
        for _, r in hot.iterrows():
            lost = fr.lines[(fr.lines["category"] == r["category"]) & (fr.lines["status"] == "Returned")]["net_sales"].sum()
            recs.append(Recommendation(
                "Product", "", f"Reduce returns in {r['category']}",
                f"{r['category']} return rate is {r['return_rate']:.1%} vs a {avg_ret:.1%} category average; "
                f"${lost:,.0f} of sales were refunded in the period.",
                "Add size guides / fit predictors, richer photos and reviews mentioning fit; "
                "flag SKUs with the highest return share for supplier review.",
                lost * 0.25 * ann, "cutting refunded sales in the category by 25%"))

    # 6. RFM: at-risk value -----------------------------------------------------------------
    r = an.rfm(fr.orders)
    if not r.empty:
        risk = r[r["segment"].isin(["At Risk", "Can't Lose Them"])]
        if len(risk):
            uplift = risk["monetary"].sum() * ann * 0.15
            recs.append(Recommendation(
                "Retention", "", "Win back high-value lapsing customers",
                f"{len(risk):,} customers sit in 'At Risk' / 'Can't Lose Them' - they generated "
                f"${risk['monetary'].sum():,.0f} but haven't ordered in {risk['recency'].median():.0f} days (median).",
                "Run a personalised win-back series (favourite categories, a time-boxed offer) and add "
                "them to a suppression-tested retargeting audience.",
                uplift, "reactivating 15% of their historic annualised spend"))
        champs = r[r["segment"] == "Champions"]
        if len(champs):
            recs.append(Recommendation(
                "Retention", "", "Turn Champions into advocates",
                f"{len(champs):,} Champions ({len(champs) / len(r):.0%} of buyers) drive "
                f"{champs['monetary'].sum() / r['monetary'].sum():.0%} of revenue.",
                "Launch a referral programme and VIP early access; protect this group from discount-led "
                "campaigns they don't need.",
                champs["monetary"].sum() * ann * 0.03, "3% incremental spend via referrals"))

    # 7. One-time buyers ------------------------------------------------------------------
    life = an.customer_lifetime(fr.orders)
    if life and life["repeat_customer_rate"] < 0.6:
        one_timers = fr.orders[fr.orders["status"] == "Completed"].groupby("customer_id").size()
        n1 = int((one_timers == 1).sum())
        recs.append(Recommendation(
            "Retention", "", "Drive the second purchase",
            f"Only {life['repeat_customer_rate']:.0%} of buyers ordered more than once; repeat buyers produce "
            f"{life['repeat_revenue_share']:.0%} of revenue. Median gap between orders is "
            f"{life['median_days_between_orders']:.0f} days.",
            f"Send a post-purchase journey timed before day {max(int(life['median_days_between_orders'] * 0.8), 7)} "
            "with complementary products and a small second-order incentive.",
            n1 * 0.05 * aov * ann, "5% of one-time buyers placing one more order"))

    # 8. Loyalty programme -------------------------------------------------------------------
    loy = fr.sessions.groupby("loyalty")["purchased"].agg(["sum", "count"])
    if {"Loyalty member", "Non-member"} <= set(loy.index):
        a, b = loy.loc["Non-member"], loy.loc["Loyalty member"]
        res = st.two_proportion_ztest(int(a["sum"]), int(a["count"]), int(b["sum"]), int(b["count"]),
                                      group_a="Non-members", group_b="Loyalty members")
        if res.significant and res.difference > 0:
            uplift = a["count"] * 0.10 * res.difference * aov * ann
            recs.append(Recommendation(
                "Retention", "", "Grow loyalty-programme enrolment",
                f"Members convert at {res.value_b:.2%} vs {res.value_a:.2%} for non-members "
                f"({res.relative_lift:+.0%}, p = {_p(res.p_value)}). Correlation, not proven causation - "
                "members self-select.",
                "Prompt enrolment at checkout and in the post-purchase email; run a holdout test to "
                "measure the programme's causal lift before scaling incentives.",
                uplift, "10% of non-member sessions converting at the member rate"))

    # 9. Checkout A/B experiment --------------------------------------------------------------
    ab = fr.sessions[fr.sessions["began_checkout"] == 1].groupby("checkout_variant")["purchased"].agg(["sum", "count"])
    if {"A", "B"} <= set(ab.index):
        res = st.two_proportion_ztest(int(ab.loc["A", "sum"]), int(ab.loc["A", "count"]),
                                      int(ab.loc["B", "sum"]), int(ab.loc["B", "count"]),
                                      group_a="Variant A", group_b="Variant B", metric="checkout completion")
        if res.significant:
            better = "B" if res.difference > 0 else "A"
            uplift = ab["count"].sum() * abs(res.difference) * 0.5 * aov * ann
            recs.append(Recommendation(
                "Conversion", "", f"Roll out checkout variant {better}",
                f"Checkout completion: B {res.value_b:.1%} vs A {res.value_a:.1%} "
                f"(lift {res.relative_lift:+.1%}, p = {_p(res.p_value)}, 95% CI "
                f"{res.ci_low * 100:+.2f} to {res.ci_high * 100:+.2f} pts).",
                f"Ship variant {better} to 100% of checkout traffic and keep a 5% holdout to confirm the lift persists.",
                uplift, "moving the losing half of checkout traffic to the winning variant"))
        else:
            recs.append(Recommendation(
                "Conversion", "", "Keep the checkout test running",
                f"Variant B vs A completion: {res.value_b:.1%} vs {res.value_a:.1%} (p = {res.p_value:.3f}) - "
                "not significant yet.",
                "Don't ship on a hunch; continue until the pre-registered sample size is reached.",
                0.0, "no decision yet"))

    # 10. Promo depth -----------------------------------------------------------------------
    o = fr.orders[fr.orders["status"] == "Completed"]
    promo = o[o["promo_code"].notna()]
    nopromo = o[o["promo_code"].isna()]
    if len(promo) > 30 and len(nopromo) > 30:
        m_p = promo["gross_profit"].sum() / promo["net_revenue"].sum()
        m_n = nopromo["gross_profit"].sum() / nopromo["net_revenue"].sum()
        if m_n - m_p > 0.05:
            recs.append(Recommendation(
                "Pricing", "", "Tighten promotion depth",
                f"Promo orders ({len(promo) / len(o):.0%} of orders) run a {m_p:.1%} margin vs {m_n:.1%} without "
                f"a code, and AOV is ${promo['net_revenue'].mean():,.0f} vs ${nopromo['net_revenue'].mean():,.0f}.",
                "Replace blanket % codes with threshold offers (spend $X, save $Y) to lift basket size, and "
                "exclude thin-margin categories from site-wide codes.",
                promo["net_revenue"].sum() * 0.03 * ann, "+3pt margin on promo revenue (profit)"))

    # 11. Seasonality / inventory ------------------------------------------------------------
    m = fr.lines.groupby(fr.lines["order_date"].dt.month)["net_revenue"].sum()
    if len(m) == 12:
        q4 = m.loc[[10, 11, 12]].sum() / m.sum()
        if q4 > 0.30:
            recs.append(Recommendation(
                "Operations", "", "Plan inventory and staffing for the Q4 peak",
                f"Q4 delivers {q4:.0%} of annual revenue; December alone is {m.loc[12] / m.mean():.1f}x an average month.",
                "Lock in stock for A-class SKUs by September, scale support and fulfilment capacity for "
                "Black Friday week, and pre-build Q4 campaigns.",
                m.loc[[11, 12]].sum() * 0.02 * ann / (len(fr.lines['order_date'].dt.year.unique()) or 1),
                "avoiding 2% of Nov-Dec revenue lost to stock-outs"))

    # 12. Long tail ------------------------------------------------------------------------
    prod = an.product_performance(fr.lines)
    if len(prod) > 20:
        c = prod[prod["abc"] == "C"]
        a_cls = prod[prod["abc"] == "A"]
        recs.append(Recommendation(
            "Product", "", "Rationalise the long tail",
            f"{len(a_cls)} A-class products ({len(a_cls) / len(prod):.0%} of the catalogue) earn 80% of revenue; "
            f"{len(c)} C-class products earn just {c['revenue'].sum() / prod['revenue'].sum():.0%}.",
            "Review C-class SKUs for delisting or bundle-only status; redirect merchandising space to A-class products.",
            0.0, "cost saving (holding/merchandising), not revenue"))

    for rec in recs:
        rec.priority = _priority(rec.impact, annual_rev)
    order = {"High": 0, "Medium": 1, "Low": 2}
    recs.sort(key=lambda x: (order[x.priority], -x.impact))
    return recs


def to_frame(recs: list[Recommendation]) -> pd.DataFrame:
    return pd.DataFrame([r.__dict__ for r in recs])
