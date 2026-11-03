-- title: Repeat purchase behaviour
-- question: What share of customers buy again, and how long until the second order?
WITH c AS (
    SELECT customer_id,
           COUNT(*)          AS orders,
           MIN(order_date)   AS first_order,
           SUM(net_revenue)  AS revenue
    FROM v_orders WHERE status <> 'Cancelled'
    GROUP BY customer_id
),
second AS (
    SELECT customer_id, order_date AS second_order
    FROM (SELECT customer_id, order_date,
                 ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date) AS rn
          FROM v_orders WHERE status <> 'Cancelled')
    WHERE rn = 2
)
SELECT
    CASE WHEN orders = 1 THEN '1 order'
         WHEN orders = 2 THEN '2 orders'
         WHEN orders BETWEEN 3 AND 5 THEN '3-5 orders'
         ELSE '6+ orders' END                                 AS frequency_band,
    COUNT(*)                                                  AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)        AS pct_customers,
    ROUND(SUM(revenue), 2)                                    AS net_revenue,
    ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 1) AS pct_revenue,
    ROUND(AVG(JULIANDAY(s.second_order) - JULIANDAY(c.first_order)), 0) AS avg_days_to_2nd_order
FROM c LEFT JOIN second s USING (customer_id)
GROUP BY frequency_band
ORDER BY MIN(orders);
