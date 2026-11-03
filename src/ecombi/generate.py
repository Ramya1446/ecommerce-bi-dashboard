"""Synthetic e-commerce dataset generator.

Produces a realistic, internally consistent star-schema dataset:

    customers      one row per customer (demographics, channel, loyalty flag)
    products       catalogue with category, price and unit cost
    sessions       web sessions with funnel flags (view -> cart -> checkout -> purchase)
                   plus an A/B checkout-experiment arm
    orders         one row per purchase (status, discount, shipping)
    order_items    order lines (product, quantity, price, discount)

Behaviour baked in so the analyses have something real to find:
    * ~25% YoY growth and a strong Nov/Dec seasonal peak (Black Friday spike).
    * Customer lifetimes are exponential; loyalty members churn slower and convert more.
    * Conversion differs by channel and device (mobile converts worse than desktop).
    * Checkout variant B has a small true uplift in checkout -> purchase completion.
    * Fashion has a higher return rate; Electronics has high revenue but thin margins.

Everything is driven by a single seed, so the dataset is reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

START = pd.Timestamp("2024-01-01")
END = pd.Timestamp("2025-12-31")

REGIONS = {
    "North": 0.24, "South": 0.27, "East": 0.19, "West": 0.22, "Central": 0.08,
}
CHANNELS = {  # share of customers, base conversion multiplier
    "Organic Search": (0.30, 1.00),
    "Paid Search": (0.22, 0.90),
    "Social Media": (0.20, 0.65),
    "Email": (0.13, 1.45),
    "Referral": (0.15, 1.20),
}
DEVICES = {"Mobile": (0.58, 0.78), "Desktop": (0.34, 1.30), "Tablet": (0.08, 1.00)}
AGE_GROUPS = {"18-24": 0.17, "25-34": 0.33, "35-44": 0.25, "45-54": 0.15, "55+": 0.10}
GENDERS = {"Female": 0.52, "Male": 0.46, "Other": 0.02}

# category: (popularity weight, price range, margin range, return rate, n_products)
CATEGORIES = {
    "Electronics": (0.20, (35, 520), (0.10, 0.22), 0.06, 38),
    "Fashion": (0.24, (15, 160), (0.45, 0.62), 0.16, 52),
    "Home & Kitchen": (0.17, (12, 180), (0.30, 0.45), 0.05, 40),
    "Beauty": (0.13, (8, 90), (0.50, 0.68), 0.04, 30),
    "Sports & Outdoors": (0.11, (15, 220), (0.28, 0.42), 0.06, 28),
    "Books": (0.08, (6, 45), (0.20, 0.32), 0.02, 24),
    "Toys & Games": (0.07, (10, 120), (0.32, 0.48), 0.05, 22),
}

ADJECTIVES = ["Classic", "Pro", "Ultra", "Eco", "Smart", "Essential", "Premium", "Lite",
              "Urban", "Nova", "Prime", "Flex", "Aero", "Zen", "Max"]
NOUNS = {
    "Electronics": ["Earbuds", "Smartwatch", "Speaker", "Tablet", "Laptop", "Monitor",
                    "Keyboard", "Camera", "Charger", "Headphones"],
    "Fashion": ["Sneakers", "Jacket", "Hoodie", "Jeans", "Dress", "T-Shirt", "Backpack",
                "Sunglasses", "Boots", "Scarf"],
    "Home & Kitchen": ["Blender", "Cookware Set", "Lamp", "Kettle", "Knife Set", "Bedding",
                       "Air Fryer", "Coffee Maker", "Rug", "Vacuum"],
    "Beauty": ["Serum", "Moisturiser", "Lipstick", "Perfume", "Shampoo", "Face Mask",
               "Sunscreen", "Hair Dryer", "Cleanser", "Palette"],
    "Sports & Outdoors": ["Yoga Mat", "Dumbbells", "Tent", "Water Bottle", "Running Shorts",
                          "Bike Helmet", "Fitness Band", "Hiking Pack", "Jump Rope", "Kettlebell"],
    "Books": ["Novel", "Cookbook", "Biography", "Notebook", "Atlas", "Workbook",
              "Comic", "Guide", "Anthology", "Planner"],
    "Toys & Games": ["Puzzle", "Board Game", "Building Set", "Plush", "RC Car", "Doll",
                     "Card Game", "Science Kit", "Drone", "Art Set"],
}


@dataclass
class Dataset:
    customers: pd.DataFrame
    products: pd.DataFrame
    sessions: pd.DataFrame
    orders: pd.DataFrame
    order_items: pd.DataFrame

    def tables(self) -> dict[str, pd.DataFrame]:
        return {
            "customers": self.customers,
            "products": self.products,
            "sessions": self.sessions,
            "orders": self.orders,
            "order_items": self.order_items,
        }


def _pick(rng: np.random.Generator, mapping: dict, n: int, idx: int | None = None) -> np.ndarray:
    keys = list(mapping)
    weights = np.array([v[idx] if idx is not None else v for v in mapping.values()], float)
    return rng.choice(keys, size=n, p=weights / weights.sum())


def _seasonality(dates: pd.DatetimeIndex) -> np.ndarray:
    """Relative demand for each date: growth trend x month seasonality x weekday x promos."""
    month_factor = np.array([0.85, 0.80, 0.92, 0.95, 1.00, 0.96,
                             0.98, 1.02, 0.97, 1.05, 1.45, 1.65])[dates.month - 1]
    weekday_factor = np.array([0.95, 0.94, 0.97, 1.00, 1.06, 1.08, 1.00])[dates.dayofweek]
    days = (dates - START).days.to_numpy()
    trend = 1.25 ** (days / 365.0)  # ~25% YoY growth
    promo = np.ones(len(dates))
    for year in (2024, 2025):
        # Black Friday (4th Friday of Nov) through Cyber Monday
        nov = pd.date_range(f"{year}-11-01", f"{year}-11-30")
        bf = nov[nov.dayofweek == 4][3]
        promo[(dates >= bf) & (dates <= bf + pd.Timedelta(days=3))] = 2.6
        promo[(dates.month == 7) & (dates.day >= 10) & (dates.day <= 12)] = 1.8  # summer sale
    return month_factor * weekday_factor * trend * promo


def generate(n_customers: int = 9000, seed: int = 42) -> Dataset:
    rng = np.random.default_rng(seed)
    all_days = pd.date_range(START, END, freq="D")
    n_days = len(all_days)
    day_weight = _seasonality(all_days)

    # ------------------------------------------------------------------ products
    rows = []
    pid = 1
    for cat, (_, (lo, hi), (mlo, mhi), _, n) in CATEGORIES.items():
        for _ in range(n):
            price = float(np.round(np.exp(rng.uniform(np.log(lo), np.log(hi))), 0) - 0.01)
            margin = rng.uniform(mlo, mhi)
            rows.append({
                "product_id": pid,
                "product_name": f"{rng.choice(ADJECTIVES)} {rng.choice(NOUNS[cat])}",
                "category": cat,
                "unit_price": round(price, 2),
                "unit_cost": round(price * (1 - margin), 2),
                "popularity": float(rng.lognormal(0, 0.9)),
            })
            pid += 1
    products = pd.DataFrame(rows)
    # disambiguate duplicate names
    dup = products.groupby("product_name").cumcount()
    products.loc[dup > 0, "product_name"] += " " + (dup[dup > 0] + 1).astype(str)

    # ----------------------------------------------------------------- customers
    # signups follow the same growth/seasonality curve as demand
    # ~22% are an existing customer base that signed up before the analysis window
    legacy = rng.random(n_customers) < 0.22
    signup_w = day_weight[:-14] * np.linspace(0.6, 1.6, n_days - 14)  # acquisition accelerates
    signup_idx = rng.choice(n_days - 14, size=n_customers, p=signup_w / signup_w.sum())
    legacy_signup = START - pd.to_timedelta(rng.integers(1, 540, n_customers), unit="D")
    signup = pd.DatetimeIndex(np.where(legacy, legacy_signup, all_days[signup_idx]))
    signup_idx = np.where(legacy, 0, signup_idx)  # active window starts at START for legacy
    loyalty = rng.random(n_customers) < np.where(legacy, 0.40, 0.25)
    lifetime_days = rng.exponential(np.where(loyalty, 520, 230))
    window_start = all_days[signup_idx]
    churn = window_start + pd.to_timedelta(np.ceil(lifetime_days), unit="D")
    churn = churn.where(churn < END, END)

    customers = pd.DataFrame({
        "customer_id": np.arange(1, n_customers + 1),
        "signup_date": signup,
        "region": _pick(rng, REGIONS, n_customers),
        "age_group": _pick(rng, AGE_GROUPS, n_customers),
        "gender": _pick(rng, GENDERS, n_customers),
        "acquisition_channel": _pick(rng, CHANNELS, n_customers, 0),
        "preferred_device": _pick(rng, DEVICES, n_customers, 0),
        "is_loyalty_member": loyalty.astype(int),
        "favourite_category": _pick(rng, {k: v[0] for k, v in CATEGORIES.items()}, n_customers),
    })
    engagement = rng.gamma(2.0, 1.0, n_customers)  # per-customer activity level

    # ------------------------------------------------------------------ sessions
    active_days = (churn - window_start).days.to_numpy() + 1
    expected = engagement * active_days / 30.0 * 2.0  # ~4 sessions / month at mean engagement
    n_sess = rng.poisson(expected) + 1  # every customer visits at least once (signup visit)
    cust_rep = np.repeat(np.arange(n_customers), n_sess)
    first = np.r_[0, np.cumsum(n_sess)[:-1]]
    is_first = np.zeros(len(cust_rep), bool)
    is_first[first] = ~legacy  # new customers' first session is the signup visit

    # Session dates: oversample uniform offsets in [signup, churn] and accept by seasonality
    s_start = signup_idx[cust_rep]
    s_span = active_days[cust_rep]
    offs = np.floor(rng.random(len(cust_rep)) * s_span).astype(int)
    for _ in range(6):  # rejection sampling towards the seasonal curve
        idx = np.clip(s_start + offs, 0, n_days - 1)
        accept = rng.random(len(idx)) < day_weight[idx] / day_weight.max()
        redraw = ~accept & ~is_first
        offs[redraw] = np.floor(rng.random(redraw.sum()) * s_span[redraw]).astype(int)
    offs[is_first] = 0
    day_idx = np.clip(s_start + offs, 0, n_days - 1)

    n_s = len(cust_rep)
    pref_dev = customers["preferred_device"].to_numpy()[cust_rep]
    device = np.where(rng.random(n_s) < 0.75, pref_dev, _pick(rng, DEVICES, n_s, 0))
    acq = customers["acquisition_channel"].to_numpy()[cust_rep]
    traffic = np.where(is_first | (rng.random(n_s) < 0.55), acq, _pick(rng, CHANNELS, n_s, 0))
    variant = np.where(rng.random(n_s) < 0.5, "A", "B")

    ch_mult = np.vectorize(lambda c: CHANNELS[c][1])(traffic)
    dev_mult = np.vectorize(lambda d: DEVICES[d][1])(device)
    loy = customers["is_loyalty_member"].to_numpy()[cust_rep] == 1
    month = all_days[day_idx].month.to_numpy()
    season_mult = np.where(np.isin(month, [11, 12]), 1.18, 1.0)

    p_view = np.clip(0.72 * np.where(loy, 1.08, 1.0), 0, 0.97)
    p_cart = np.clip(0.17 * ch_mult * dev_mult * np.where(loy, 1.30, 1.0) * season_mult, 0, 0.95)
    p_checkout = np.clip(0.62 * np.where(device == "Mobile", 0.88, 1.0), 0, 0.95)
    p_purchase = np.clip(0.60 * np.where(variant == "B", 1.06, 1.0) * np.where(loy, 1.12, 1.0), 0, 0.97)

    viewed = rng.random(n_s) < p_view
    carted = viewed & (rng.random(n_s) < p_cart)
    checkout = carted & (rng.random(n_s) < p_checkout)
    purchased = checkout & (rng.random(n_s) < p_purchase)

    # time of day: quiet overnight, lunch bump, evening peak (mobile skews later)
    hour_w = np.array([1.2, 0.7, 0.4, 0.3, 0.3, 0.5, 1.0, 1.8, 2.6, 3.2, 3.6, 4.0,
                       4.6, 4.4, 3.8, 3.6, 3.7, 4.0, 4.6, 5.4, 6.0, 5.8, 4.4, 2.6])
    hour = rng.choice(24, size=n_s, p=hour_w / hour_w.sum())
    late = (device == "Mobile") & (rng.random(n_s) < 0.25)
    hour = np.where(late, rng.choice([20, 21, 22, 23], size=n_s), hour)
    sess_ts = all_days[day_idx] + pd.to_timedelta(hour * 3600 + rng.integers(0, 3600, n_s), unit="s")
    sessions = pd.DataFrame({
        "session_id": np.arange(1, n_s + 1),
        "customer_id": cust_rep + 1,
        "session_start": sess_ts,
        "traffic_channel": traffic,
        "device": device,
        "checkout_variant": variant,
        "viewed_product": viewed.astype(int),
        "added_to_cart": carted.astype(int),
        "began_checkout": checkout.astype(int),
        "purchased": purchased.astype(int),
        "pages_viewed": np.where(viewed, rng.poisson(5, n_s) + 2, 1) + carted * rng.poisson(2, n_s),
        "duration_sec": (rng.gamma(2.0, 90, n_s) * (1 + 1.5 * carted + 1.0 * checkout)).astype(int),
    }).sort_values("session_start", kind="stable").reset_index(drop=True)
    sessions["session_id"] = np.arange(1, n_s + 1)

    # -------------------------------------------------------------------- orders
    buy = sessions[sessions["purchased"] == 1].reset_index(drop=True)
    n_o = len(buy)
    order_dates = buy["session_start"] + pd.to_timedelta(rng.integers(60, 1800, n_o), unit="s")
    order_dates = order_dates.clip(upper=END + pd.Timedelta(hours=23, minutes=59, seconds=59))
    is_bf = np.zeros(n_o, bool)
    for year in (2024, 2025):
        nov = pd.date_range(f"{year}-11-01", f"{year}-11-30")
        bf = nov[nov.dayofweek == 4][3]
        is_bf |= (order_dates.dt.normalize() >= bf).to_numpy() & (order_dates.dt.normalize() <= bf + pd.Timedelta(days=3)).to_numpy()
    promo_prob = np.where(is_bf, 0.85, np.where(order_dates.dt.month.isin([11, 12]), 0.40, 0.18))
    has_promo = rng.random(n_o) < promo_prob
    discount_pct = np.where(has_promo, rng.choice([0.10, 0.15, 0.20, 0.25], n_o, p=[0.4, 0.3, 0.2, 0.1]), 0.0)
    discount_pct = np.where(is_bf & has_promo, np.maximum(discount_pct, 0.20), discount_pct)

    orders = pd.DataFrame({
        "order_id": np.arange(100001, 100001 + n_o),
        "customer_id": buy["customer_id"].to_numpy(),
        "session_id": buy["session_id"].to_numpy(),
        "order_date": order_dates.dt.floor("s"),
        "channel": buy["traffic_channel"].to_numpy(),
        "device": buy["device"].to_numpy(),
        "promo_code": np.where(has_promo, np.where(is_bf, "BLACKFRIDAY", rng.choice(["SAVE10", "WELCOME", "VIP", "FLASH"], n_o)), None),
        "discount_pct": discount_pct,
    })

    # ---------------------------------------------------------------- order items
    n_lines = np.minimum(rng.poisson(0.9, n_o) + 1, 6)
    line_order = np.repeat(np.arange(n_o), n_lines)
    cust_of_line = orders["customer_id"].to_numpy()[line_order] - 1
    fav = customers["favourite_category"].to_numpy()[cust_of_line]
    cat_names = list(CATEGORIES)
    cat_w = np.array([CATEGORIES[c][0] for c in cat_names])
    rand_cat = rng.choice(cat_names, size=len(line_order), p=cat_w / cat_w.sum())
    line_cat = np.where(rng.random(len(line_order)) < 0.45, fav, rand_cat)

    prod_by_cat = {c: products[products["category"] == c] for c in cat_names}
    product_id = np.empty(len(line_order), int)
    for c in cat_names:
        mask = line_cat == c
        pool = prod_by_cat[c]
        w = pool["popularity"].to_numpy()
        product_id[mask] = rng.choice(pool["product_id"].to_numpy(), size=mask.sum(), p=w / w.sum())
    qty = rng.choice([1, 1, 1, 1, 1, 1, 2, 2, 3], size=len(line_order))
    pinfo = products.set_index("product_id").loc[product_id]
    order_items = pd.DataFrame({
        "order_item_id": np.arange(1, len(line_order) + 1),
        "order_id": orders["order_id"].to_numpy()[line_order],
        "product_id": product_id,
        "quantity": qty,
        "unit_price": pinfo["unit_price"].to_numpy(),
        "unit_cost": pinfo["unit_cost"].to_numpy(),
        "discount_pct": orders["discount_pct"].to_numpy()[line_order],
    })
    order_items = order_items.drop_duplicates(["order_id", "product_id"]).reset_index(drop=True)
    order_items["order_item_id"] = np.arange(1, len(order_items) + 1)

    # status: return probability driven by the riskiest category in the basket
    ret_rate = {c: v[3] for c, v in CATEGORIES.items()}
    oi_cat = products.set_index("product_id").loc[order_items["product_id"], "category"].to_numpy()
    order_ret = pd.Series(np.vectorize(ret_rate.get)(oi_cat)).groupby(order_items["order_id"].to_numpy()).max()
    p_ret = orders["order_id"].map(order_ret).to_numpy()
    u = rng.random(n_o)
    status = np.where(u < 0.035, "Cancelled", np.where(u < 0.035 + p_ret, "Returned", "Completed"))
    gross = (order_items["quantity"] * order_items["unit_price"]).groupby(order_items["order_id"]).sum()
    orders["subtotal"] = orders["order_id"].map(gross).round(2)
    orders["shipping_fee"] = np.where(orders["subtotal"] >= 75, 0.0, 6.99)
    orders["status"] = status

    products = products.drop(columns="popularity")
    customers["signup_date"] = customers["signup_date"].dt.date
    return Dataset(customers, products, sessions, orders, order_items)
