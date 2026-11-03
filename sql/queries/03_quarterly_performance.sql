-- title: Quarterly performance vs. same quarter last year
-- question: Which quarters grew fastest year over year?
WITH q AS (
    SELECT order_quarter,
           SUBSTR(order_quarter, 1, 4) AS year,
           SUBSTR(order_quarter, 6, 2) AS qtr,
           ROUND(SUM(net_revenue), 2)  AS net_revenue,
           ROUND(SUM(gross_profit), 2) AS gross_profit
    FROM v_order_lines
    GROUP BY order_quarter
)
SELECT
    cur.order_quarter,
    cur.net_revenue,
    cur.gross_profit,
    prev.net_revenue AS net_revenue_last_year,
    ROUND(100.0 * (cur.net_revenue - prev.net_revenue) / prev.net_revenue, 1) AS yoy_growth_pct
FROM q cur
LEFT JOIN q prev
       ON prev.qtr = cur.qtr AND CAST(prev.year AS INTEGER) = CAST(cur.year AS INTEGER) - 1
ORDER BY cur.order_quarter;
