-- title: Monthly revenue trend with MoM growth and 3-month moving average
-- question: Is revenue growing month over month, and what does the smoothed trend look like?
WITH monthly AS (
    SELECT order_month,
           ROUND(SUM(net_revenue), 2) AS net_revenue,
           COUNT(DISTINCT CASE WHEN status = 'Completed' THEN order_id END) AS orders
    FROM v_orders
    GROUP BY order_month
)
SELECT
    order_month,
    net_revenue,
    orders,
    ROUND(100.0 * (net_revenue - LAG(net_revenue) OVER w) / LAG(net_revenue) OVER w, 1) AS mom_growth_pct,
    ROUND(AVG(net_revenue) OVER (ORDER BY order_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS moving_avg_3m,
    ROUND(SUM(net_revenue) OVER (PARTITION BY SUBSTR(order_month, 1, 4) ORDER BY order_month), 2) AS ytd_revenue
FROM monthly
WINDOW w AS (ORDER BY order_month)
ORDER BY order_month;
