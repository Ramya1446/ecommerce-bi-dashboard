-- title: Pareto / ABC analysis of the product catalogue
-- question: What share of products generates 80% of revenue?
WITH p AS (
    SELECT product_id, SUM(net_revenue) AS rev
    FROM v_order_lines GROUP BY product_id
),
ranked AS (
    SELECT product_id, rev,
           SUM(rev) OVER (ORDER BY rev DESC ROWS UNBOUNDED PRECEDING) / SUM(rev) OVER () AS cum_share
    FROM p
),
abc AS (
    SELECT *, CASE WHEN cum_share <= 0.80 THEN 'A'
                   WHEN cum_share <= 0.95 THEN 'B' ELSE 'C' END AS abc_class
    FROM ranked
)
SELECT abc_class,
       COUNT(*)                                            AS products,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)  AS pct_of_catalogue,
       ROUND(SUM(rev), 2)                                  AS net_revenue,
       ROUND(100.0 * SUM(rev) / SUM(SUM(rev)) OVER (), 1)  AS pct_of_revenue
FROM abc
GROUP BY abc_class
ORDER BY abc_class;
