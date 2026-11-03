"""Print an executive text report (KPIs, SQL insights, hypothesis tests, recommendations).

Usage:  python scripts/run_report.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecombi import analytics as an  # noqa: E402
from ecombi import insights  # noqa: E402
from ecombi import stats as st  # noqa: E402
from ecombi.db import DEFAULT_DB, build_database, load_queries, read_sql  # noqa: E402
from ecombi.generate import generate  # noqa: E402

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)


def rule(title: str) -> None:
    print(f"\n{'=' * 80}\n{title}\n{'=' * 80}")


def main() -> None:
    if not DEFAULT_DB.exists():
        build_database(generate())
    fr = an.load_frames()
    k = an.kpis(fr)

    rule("KPIs (all time)")
    print(f"Net revenue      ${k['revenue']:>14,.0f}")
    print(f"Gross profit     ${k['profit']:>14,.0f}   ({k['margin']:.1%} margin)")
    print(f"Completed orders  {k['orders']:>14,}")
    print(f"AOV              ${k['aov']:>14,.2f}")
    print(f"Buyers            {k['customers']:>14,}")
    print(f"Conversion        {k['conversion']:>14.2%}")
    print(f"Return rate       {k['return_rate']:>14.1%}")
    print(f"Repeat rate       {k['repeat_rate']:>14.1%}")

    for q in load_queries():
        rule(f"[SQL {q.slug}] {q.title}\n{q.question}")
        print(read_sql(q.sql).to_string(index=False))

    rule("Hypothesis tests")
    s = fr.sessions
    a, b = s[s["loyalty"] == "Non-member"]["purchased"], s[s["loyalty"] == "Loyalty member"]["purchased"]
    r1 = st.two_proportion_ztest(int(a.sum()), len(a), int(b.sum()), len(b),
                                 group_a="Non-members", group_b="Loyalty members")
    print("1) Conversion: loyalty members vs non-members\n  ", r1.verdict())
    c = s[s["began_checkout"] == 1]
    a, b = c[c["checkout_variant"] == "A"]["purchased"], c[c["checkout_variant"] == "B"]["purchased"]
    r2 = st.two_proportion_ztest(int(a.sum()), len(a), int(b.sum()), len(b), group_a="Variant A",
                                 group_b="Variant B", metric="checkout completion")
    print(f"2) Checkout A/B test (95% CI {r2.ci_low * 100:+.2f} to {r2.ci_high * 100:+.2f} pts)\n  ", r2.verdict())
    o = fr.orders[fr.orders["status"] == "Completed"]
    r3 = st.welch_ttest(o[o["loyalty"] == "Non-member"]["net_revenue"], o[o["loyalty"] == "Loyalty member"]["net_revenue"],
                        group_a="Non-members", group_b="Loyalty members")
    print("3) AOV: loyalty members vs non-members (Welch)\n  ", r3.verdict("${:,.2f}"),
          f"\n   Mann-Whitney p = {r3.extra['mann_whitney_p']:.4f}")

    rule("Recommendations")
    for i, rec in enumerate(insights.generate(fr), 1):
        print(f"{i:>2}. [{rec.priority}] {rec.title}  (~${rec.impact:,.0f}/yr)")
        print(f"    Finding: {rec.finding}")
        print(f"    Action:  {rec.action}")


if __name__ == "__main__":
    main()
