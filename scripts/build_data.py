"""Generate the synthetic dataset, load it into SQLite and write raw CSVs.

Usage:  python scripts/build_data.py [--customers 9000] [--seed 42]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecombi.db import DEFAULT_DB, build_database  # noqa: E402
from ecombi.generate import generate  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--customers", type=int, default=9000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--csv", action="store_true", help="also write raw tables to data/raw/*.csv")
    args = ap.parse_args()

    t0 = time.time()
    ds = generate(n_customers=args.customers, seed=args.seed)
    path = build_database(ds, DEFAULT_DB)
    for name, df in ds.tables().items():
        print(f"  {name:<12} {len(df):>8,} rows")
    if args.csv:
        raw = ROOT / "data" / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        for name, df in ds.tables().items():
            df.to_csv(raw / f"{name}.csv", index=False)
        print(f"Raw CSVs written to {raw}")
    print(f"SQLite warehouse: {path}  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
