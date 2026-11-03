-- E-commerce BI star schema (SQLite dialect; portable to Postgres/MySQL with minor type changes)

DROP VIEW IF EXISTS v_order_lines;
DROP VIEW IF EXISTS v_orders;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id          INTEGER PRIMARY KEY,
    signup_date          DATE    NOT NULL,
    region               TEXT    NOT NULL,
    age_group            TEXT    NOT NULL,
    gender               TEXT    NOT NULL,
    acquisition_channel  TEXT    NOT NULL,
    preferred_device     TEXT    NOT NULL,
    is_loyalty_member    INTEGER NOT NULL CHECK (is_loyalty_member IN (0, 1)),
    favourite_category   TEXT    NOT NULL
);

CREATE TABLE products (
    product_id    INTEGER PRIMARY KEY,
    product_name  TEXT NOT NULL,
    category      TEXT NOT NULL,
    unit_price    REAL NOT NULL CHECK (unit_price > 0),
    unit_cost     REAL NOT NULL CHECK (unit_cost >= 0)
);

CREATE TABLE sessions (
    session_id        INTEGER PRIMARY KEY,
    customer_id       INTEGER NOT NULL REFERENCES customers(customer_id),
    session_start     TIMESTAMP NOT NULL,
    traffic_channel   TEXT NOT NULL,
    device            TEXT NOT NULL,
    checkout_variant  TEXT NOT NULL CHECK (checkout_variant IN ('A', 'B')),
    viewed_product    INTEGER NOT NULL,
    added_to_cart     INTEGER NOT NULL,
    began_checkout    INTEGER NOT NULL,
    purchased         INTEGER NOT NULL,
    pages_viewed      INTEGER NOT NULL,
    duration_sec      INTEGER NOT NULL
);

CREATE TABLE orders (
    order_id      INTEGER PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES customers(customer_id),
    session_id    INTEGER REFERENCES sessions(session_id),
    order_date    TIMESTAMP NOT NULL,
    channel       TEXT NOT NULL,
    device        TEXT NOT NULL,
    promo_code    TEXT,
    discount_pct  REAL NOT NULL DEFAULT 0,
    subtotal      REAL NOT NULL,
    shipping_fee  REAL NOT NULL DEFAULT 0,
    status        TEXT NOT NULL CHECK (status IN ('Completed', 'Returned', 'Cancelled'))
);

CREATE TABLE order_items (
    order_item_id  INTEGER PRIMARY KEY,
    order_id       INTEGER NOT NULL REFERENCES orders(order_id),
    product_id     INTEGER NOT NULL REFERENCES products(product_id),
    quantity       INTEGER NOT NULL CHECK (quantity > 0),
    unit_price     REAL NOT NULL,
    unit_cost      REAL NOT NULL,
    discount_pct   REAL NOT NULL DEFAULT 0
);

CREATE INDEX ix_orders_customer   ON orders(customer_id);
CREATE INDEX ix_orders_date       ON orders(order_date);
CREATE INDEX ix_items_order       ON order_items(order_id);
CREATE INDEX ix_items_product     ON order_items(product_id);
CREATE INDEX ix_sessions_customer ON sessions(customer_id);
CREATE INDEX ix_sessions_start    ON sessions(session_start);

-- Line-level fact with money already computed. Net revenue counts only Completed orders
-- (returns are refunded, cancellations never shipped).
CREATE VIEW v_order_lines AS
SELECT
    oi.order_item_id,
    oi.order_id,
    o.customer_id,
    DATE(o.order_date)                                         AS order_date,
    STRFTIME('%Y-%m', o.order_date)                            AS order_month,
    STRFTIME('%Y', o.order_date) || '-Q' ||
        ((CAST(STRFTIME('%m', o.order_date) AS INTEGER) + 2) / 3) AS order_quarter,
    o.status,
    o.channel,
    o.device,
    p.product_id,
    p.product_name,
    p.category,
    oi.quantity,
    oi.unit_price,
    oi.unit_cost,
    oi.discount_pct,
    ROUND(oi.quantity * oi.unit_price, 2)                              AS gross_sales,
    ROUND(oi.quantity * oi.unit_price * oi.discount_pct, 2)            AS discount_amount,
    ROUND(oi.quantity * oi.unit_price * (1 - oi.discount_pct), 2)      AS net_sales,
    ROUND(oi.quantity * oi.unit_cost, 2)                               AS cogs,
    CASE WHEN o.status = 'Completed'
         THEN ROUND(oi.quantity * oi.unit_price * (1 - oi.discount_pct), 2) ELSE 0 END AS net_revenue,
    CASE WHEN o.status = 'Completed'
         THEN ROUND(oi.quantity * (oi.unit_price * (1 - oi.discount_pct) - oi.unit_cost), 2) ELSE 0 END AS gross_profit
FROM order_items oi
JOIN orders   o ON o.order_id   = oi.order_id
JOIN products p ON p.product_id = oi.product_id;

-- Order-level fact.
CREATE VIEW v_orders AS
SELECT
    o.order_id,
    o.customer_id,
    o.order_date,
    STRFTIME('%Y-%m', o.order_date) AS order_month,
    o.channel,
    o.device,
    o.status,
    o.promo_code,
    o.discount_pct,
    o.shipping_fee,
    SUM(l.gross_sales)   AS gross_sales,
    SUM(l.net_sales)     AS net_sales,
    SUM(l.net_revenue)   AS net_revenue,
    SUM(l.gross_profit)  AS gross_profit,
    SUM(l.quantity)      AS units
FROM orders o
JOIN v_order_lines l ON l.order_id = o.order_id
GROUP BY o.order_id;
