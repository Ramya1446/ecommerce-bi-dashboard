import pandas as pd
import pytest

from ecombi import analytics as an
from ecombi import insights
from ecombi.db import load_queries, read_sql, run_readonly


@pytest.fixture(scope="module")
def frames(db_path):
    return an.load_frames(db_path)


def test_all_named_queries_run(db_path):
    qs = load_queries()
    assert len(qs) >= 10
    for q in qs:
        df = read_sql(q.sql, db_path)
        assert not df.empty, q.slug
        assert q.title and q.question, q.slug


def test_sql_and_pandas_revenue_agree(db_path, frames):
    sql_rev = read_sql("SELECT SUM(net_revenue) AS r FROM v_order_lines", db_path)["r"].iloc[0]
    assert an.kpis(frames)["revenue"] == pytest.approx(sql_rev)


def test_readonly_guard(db_path):
    with pytest.raises(ValueError):
        run_readonly("DELETE FROM orders", db_path)
    with pytest.raises(ValueError):
        run_readonly("SELECT 1; DROP TABLE orders", db_path)
    assert run_readonly("SELECT COUNT(*) AS n FROM orders", db_path)["n"].iloc[0] > 0


def test_filters_narrow_data(frames):
    full = an.Filters(pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31"))
    books = an.Filters(full.start, full.end, categories=["Books"])
    f_all, f_books = an.apply_filters(frames, full), an.apply_filters(frames, books)
    assert set(f_books.lines["category"]) == {"Books"}
    assert an.kpis(f_books)["revenue"] < an.kpis(f_all)["revenue"]


def test_rfm_scores_and_segments(frames):
    r = an.rfm(frames.orders)
    assert r["R"].between(1, 5).all() and r["F"].between(1, 5).all() and r["M"].between(1, 5).all()
    assert set(r["segment"]) <= set(an.SEGMENT_ORDER)
    seg = an.segment_summary(r)
    assert seg["customers"].sum() == len(r)
    assert seg["revenue_share"].sum() == pytest.approx(1.0)


def test_cohort_month_zero_is_full(frames):
    pct, sizes = an.cohort_matrix(frames.orders)
    assert (pct[0] == 1.0).all()
    assert (pct.drop(columns=0).fillna(0) <= 1.0).all().all()


def test_funnel_and_pareto(frames):
    fn = an.funnel(frames.sessions)
    assert fn["count"].is_monotonic_decreasing
    prod = an.product_performance(frames.lines)
    assert prod["cum_share"].iloc[-1] == pytest.approx(1.0)
    assert set(prod["abc"]) <= {"A", "B", "C"}


def test_recommendations_are_data_driven(frames):
    recs = insights.generate(frames)
    assert len(recs) >= 5
    assert {r.priority for r in recs} <= {"High", "Medium", "Low"}
    order = {"High": 0, "Medium": 1, "Low": 2}
    keys = [(order[r.priority], -r.impact) for r in recs]
    assert keys == sorted(keys)
