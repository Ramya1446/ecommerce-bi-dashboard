-- title: Monthly cohort retention (first 6 months)
-- question: Of customers who first bought in month M, what % bought again in each following month?
WITH first_order AS (
    SELECT customer_id, MIN(order_month) AS cohort
    FROM v_orders WHERE status <> 'Cancelled' GROUP BY customer_id
),
activity AS (
    SELECT DISTINCT o.customer_id, f.cohort,
           (CAST(SUBSTR(o.order_month, 1, 4) AS INTEGER) - CAST(SUBSTR(f.cohort, 1, 4) AS INTEGER)) * 12
         + (CAST(SUBSTR(o.order_month, 6, 2) AS INTEGER) - CAST(SUBSTR(f.cohort, 6, 2) AS INTEGER)) AS month_n
    FROM v_orders o JOIN first_order f USING (customer_id)
    WHERE o.status <> 'Cancelled'
)
SELECT cohort,
       COUNT(DISTINCT CASE WHEN month_n = 0 THEN customer_id END) AS cohort_size,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN month_n = 1 THEN customer_id END) / COUNT(DISTINCT CASE WHEN month_n = 0 THEN customer_id END), 1) AS m1_pct,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN month_n = 2 THEN customer_id END) / COUNT(DISTINCT CASE WHEN month_n = 0 THEN customer_id END), 1) AS m2_pct,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN month_n = 3 THEN customer_id END) / COUNT(DISTINCT CASE WHEN month_n = 0 THEN customer_id END), 1) AS m3_pct,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN month_n = 6 THEN customer_id END) / COUNT(DISTINCT CASE WHEN month_n = 0 THEN customer_id END), 1) AS m6_pct
FROM activity
GROUP BY cohort
ORDER BY cohort;
