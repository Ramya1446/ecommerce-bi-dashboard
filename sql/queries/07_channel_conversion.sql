-- title: Funnel conversion by traffic channel
-- question: Which acquisition channels convert visits into purchases most efficiently?
SELECT
    traffic_channel,
    COUNT(*)                                                    AS sessions,
    ROUND(100.0 * AVG(added_to_cart), 2)                        AS add_to_cart_pct,
    ROUND(100.0 * SUM(began_checkout) / NULLIF(SUM(added_to_cart), 0), 1)  AS cart_to_checkout_pct,
    ROUND(100.0 * SUM(purchased) / NULLIF(SUM(began_checkout), 0), 1)      AS checkout_to_purchase_pct,
    ROUND(100.0 * AVG(purchased), 2)                            AS conversion_rate_pct,
    ROUND(100.0 * (1 - 1.0 * SUM(purchased) / NULLIF(SUM(added_to_cart), 0)), 1) AS cart_abandonment_pct
FROM sessions
GROUP BY traffic_channel
ORDER BY conversion_rate_pct DESC;
