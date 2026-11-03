import numpy as np

from ecombi.generate import END, START, generate


def test_reproducible():
    a, b = generate(400, seed=3), generate(400, seed=3)
    assert a.orders.equals(b.orders)
    assert a.sessions.equals(b.sessions)


def test_referential_integrity(dataset):
    assert dataset.orders["customer_id"].isin(dataset.customers["customer_id"]).all()
    assert dataset.order_items["order_id"].isin(dataset.orders["order_id"]).all()
    assert dataset.order_items["product_id"].isin(dataset.products["product_id"]).all()
    assert dataset.orders["session_id"].isin(dataset.sessions["session_id"]).all()


def test_funnel_is_monotonic(dataset):
    s = dataset.sessions
    assert (s["added_to_cart"] <= s["viewed_product"]).all()
    assert (s["began_checkout"] <= s["added_to_cart"]).all()
    assert (s["purchased"] <= s["began_checkout"]).all()
    assert s["purchased"].sum() == len(dataset.orders)


def test_dates_within_window(dataset):
    o = dataset.orders["order_date"]
    assert o.min() >= START
    assert o.max() < END + np.timedelta64(1, "D")


def test_prices_and_costs_sane(dataset):
    p = dataset.products
    assert (p["unit_cost"] < p["unit_price"]).all()
    assert (dataset.order_items["quantity"] >= 1).all()
