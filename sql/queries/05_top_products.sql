-- title: Top 15 products by net revenue (with in-category rank)
-- question: What are our hero products and how do they rank inside their category?
WITH p AS (
    SELECT product_id, product_name, category,
           SUM(CASE WHEN status = 'Completed' THEN quantity ELSE 0 END) AS units,
           ROUND(SUM(net_revenue), 2)  AS net_revenue,
           ROUND(SUM(gross_profit), 2) AS gross_profit
    FROM v_order_lines
    GROUP BY product_id
)
SELECT
    RANK() OVER (ORDER BY net_revenue DESC)                        AS overall_rank,
    product_name,
    category,
    RANK() OVER (PARTITION BY category ORDER BY net_revenue DESC)  AS rank_in_category,
    units,
    net_revenue,
    ROUND(100.0 * gross_profit / NULLIF(net_revenue, 0), 1)        AS margin_pct
FROM p
ORDER BY net_revenue DESC
LIMIT 15;
