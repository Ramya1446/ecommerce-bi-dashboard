-- title: Category performance: revenue, margin, return rate
-- question: Which categories drive revenue, which drive profit, and which leak value through returns?
SELECT
    category,
    ROUND(SUM(net_revenue), 2)                                         AS net_revenue,
    ROUND(SUM(gross_profit), 2)                                        AS gross_profit,
    ROUND(100.0 * SUM(gross_profit) / NULLIF(SUM(net_revenue), 0), 1)  AS margin_pct,
    SUM(CASE WHEN status = 'Completed' THEN quantity ELSE 0 END)       AS units_sold,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN status = 'Returned' THEN order_id END)
          / COUNT(DISTINCT CASE WHEN status <> 'Cancelled' THEN order_id END), 1) AS return_rate_pct,
    ROUND(100.0 * SUM(net_revenue) / SUM(SUM(net_revenue)) OVER (), 1) AS revenue_share_pct
FROM v_order_lines
GROUP BY category
ORDER BY net_revenue DESC;
