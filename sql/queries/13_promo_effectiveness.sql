-- title: Promo code effectiveness
-- question: Which promo codes bring revenue, and at what margin cost?
SELECT
    COALESCE(promo_code, '(none)')                             AS promo_code,
    COUNT(*)                                                   AS orders,
    ROUND(AVG(discount_pct) * 100, 1)                          AS avg_discount_pct,
    ROUND(SUM(net_revenue), 2)                                 AS net_revenue,
    ROUND(AVG(CASE WHEN status = 'Completed' THEN net_revenue END), 2) AS avg_order_value,
    ROUND(100.0 * SUM(gross_profit) / NULLIF(SUM(net_revenue), 0), 1)  AS margin_pct
FROM v_orders
GROUP BY COALESCE(promo_code, '(none)')
ORDER BY net_revenue DESC;
