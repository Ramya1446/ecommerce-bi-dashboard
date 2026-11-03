"""Export a Power BI / Tableau-ready star schema to exports/.

Produces flat CSV extracts (fact + dimension tables, a date dimension, RFM segments
and the generated recommendations). Load them in Power BI Desktop (Get Data > Text/CSV)
or Tableau (Connect > Text file) and follow docs/POWERBI_TABLEAU.md.

Usage:  python scripts/export_bi.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecombi import analytics as an  # noqa: E402
from ecombi import insights  # noqa: E402
from ecombi.db import DEFAULT_DB, build_database, read_sql  # noqa: E402
from ecombi.generate import generate  # noqa: E402

OUT = ROOT / "exports"


def main() -> None:
    if not DEFAULT_DB.exists():
        build_database(generate())
    OUT.mkdir(exist_ok=True)

    tables = {
        "fact_order_lines": "SELECT * FROM v_order_lines",
        "fact_orders": "SELECT * FROM v_orders",
        "fact_sessions": "SELECT * FROM sessions",
        "dim_customer": "SELECT * FROM customers",
        "dim_product": "SELECT *, ROUND(1 - unit_cost / unit_price, 4) AS list_margin FROM products",
    }
    for name, sql in tables.items():
        df = read_sql(sql)
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"  {name:<18} {len(df):>8,} rows")

    dates = pd.date_range("2024-01-01", "2025-12-31", freq="D")
    dim_date = pd.DataFrame({
        "date": dates.date, "year": dates.year, "quarter": "Q" + dates.quarter.astype(str),
        "year_quarter": dates.year.astype(str) + "-Q" + dates.quarter.astype(str),
        "month_num": dates.month, "month_name": dates.strftime("%b"), "year_month": dates.strftime("%Y-%m"),
        "week_of_year": dates.isocalendar().week.to_numpy(), "weekday": dates.strftime("%a"),
        "is_weekend": (dates.dayofweek >= 5).astype(int),
    })
    dim_date.to_csv(OUT / "dim_date.csv", index=False)
    print(f"  {'dim_date':<18} {len(dim_date):>8,} rows")

    fr = an.load_frames()
    rfm = an.rfm(fr.orders)
    rfm.drop(columns=["last"]).to_csv(OUT / "customer_rfm_segments.csv", index=False)
    print(f"  {'customer_rfm':<18} {len(rfm):>8,} rows")
    recs = insights.to_frame(insights.generate(fr))
    recs.to_csv(OUT / "recommendations.csv", index=False)
    print(f"  {'recommendations':<18} {len(recs):>8,} rows")
    print(f"Exports written to {OUT}")


if __name__ == "__main__":
    main()
