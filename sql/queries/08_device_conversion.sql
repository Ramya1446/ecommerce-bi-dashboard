-- title: Conversion and order value by device
-- question: Is there a mobile conversion gap, and how big is it in revenue terms?
WITH s AS (
    SELECT device, COUNT(*) AS sessions, SUM(purchased) AS purchases
    FROM sessions GROUP BY device
),
o AS (
    SELECT device, AVG(net_sales) AS aov
    FROM v_orders WHERE status <> 'Cancelled' GROUP BY device
)
SELECT s.device,
       s.sessions,
       s.purchases,
       ROUND(100.0 * s.purchases / s.sessions, 2) AS conversion_rate_pct,
       ROUND(o.aov, 2)                            AS avg_order_value,
       ROUND(1.0 * s.purchases / s.sessions * o.aov, 2) AS revenue_per_session
FROM s JOIN o USING (device)
ORDER BY conversion_rate_pct DESC;
