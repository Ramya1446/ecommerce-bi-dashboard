-- title: Regional performance
-- question: Where are our customers and revenue concentrated, and where is value per customer highest?
SELECT
    c.region,
    COUNT(DISTINCT c.customer_id)                              AS customers,
    COUNT(DISTINCT v.customer_id)                              AS buyers,
    ROUND(SUM(v.net_revenue), 2)                               AS net_revenue,
    ROUND(SUM(v.net_revenue) / COUNT(DISTINCT v.customer_id), 2) AS revenue_per_buyer,
    ROUND(100.0 * COUNT(DISTINCT v.customer_id) / COUNT(DISTINCT c.customer_id), 1) AS buyer_rate_pct
FROM customers c
LEFT JOIN v_orders v ON v.customer_id = c.customer_id AND v.status = 'Completed'
GROUP BY c.region
ORDER BY net_revenue DESC;
