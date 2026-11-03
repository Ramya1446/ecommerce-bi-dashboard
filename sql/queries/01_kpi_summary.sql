-- title: Executive KPI summary by year
-- question: How did revenue, orders, AOV, profit and customers change year over year?
WITH yearly AS (
    SELECT
        STRFTIME('%Y', order_date)                               AS year,
        ROUND(SUM(net_revenue), 2)                               AS net_revenue,
        ROUND(SUM(gross_profit), 2)                              AS gross_profit,
        COUNT(CASE WHEN status = 'Completed' THEN 1 END)         AS completed_orders,
        COUNT(DISTINCT CASE WHEN status = 'Completed' THEN customer_id END) AS active_customers
    FROM v_orders
    GROUP BY year
)
SELECT
    year,
    net_revenue,
    completed_orders,
    active_customers,
    ROUND(net_revenue / completed_orders, 2)                     AS avg_order_value,
    ROUND(100.0 * gross_profit / net_revenue, 1)                 AS gross_margin_pct,
    ROUND(100.0 * (net_revenue - LAG(net_revenue) OVER (ORDER BY year))
          / LAG(net_revenue) OVER (ORDER BY year), 1)            AS revenue_yoy_pct
FROM yearly
ORDER BY year;
