-- title: RFM scoring in pure SQL (top 25 customers)
-- question: Who are our most valuable customers by Recency, Frequency and Monetary value?
WITH snapshot AS (SELECT DATE(MAX(order_date), '+1 day') AS d FROM orders),
base AS (
    SELECT customer_id,
           CAST(JULIANDAY((SELECT d FROM snapshot)) - JULIANDAY(MAX(order_date)) AS INTEGER) AS recency_days,
           COUNT(*)          AS frequency,
           SUM(net_revenue)  AS monetary
    FROM v_orders WHERE status = 'Completed'
    GROUP BY customer_id
),
scored AS (
    SELECT *,
           6 - NTILE(5) OVER (ORDER BY recency_days) AS r,
           NTILE(5) OVER (ORDER BY frequency)        AS f,
           NTILE(5) OVER (ORDER BY monetary)         AS m
    FROM base
)
SELECT customer_id, recency_days, frequency, ROUND(monetary, 2) AS monetary,
       r, f, m, r || f || m AS rfm_code,
       CASE WHEN r >= 4 AND f >= 4 THEN 'Champions'
            WHEN f >= 4            THEN 'Loyal'
            WHEN r <= 2 AND f >= 3 THEN 'At Risk'
            WHEN r >= 4            THEN 'Recent'
            ELSE 'Needs Attention' END AS segment
FROM scored
ORDER BY monetary DESC
LIMIT 25;
