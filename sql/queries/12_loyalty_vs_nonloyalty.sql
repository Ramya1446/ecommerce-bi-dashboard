-- title: Loyalty members vs. non-members
-- question: Do loyalty members convert better and spend more? (input for the hypothesis test)
WITH s AS (
    SELECT c.is_loyalty_member, COUNT(*) AS sessions, SUM(s.purchased) AS purchases
    FROM sessions s JOIN customers c USING (customer_id)
    GROUP BY c.is_loyalty_member
),
o AS (
    SELECT c.is_loyalty_member,
           COUNT(*)                         AS completed_orders,
           AVG(v.net_revenue)               AS aov,
           COUNT(DISTINCT v.customer_id)    AS buyers,
           SUM(v.net_revenue)               AS revenue
    FROM v_orders v JOIN customers c USING (customer_id)
    WHERE v.status = 'Completed'
    GROUP BY c.is_loyalty_member
)
SELECT CASE s.is_loyalty_member WHEN 1 THEN 'Loyalty member' ELSE 'Non-member' END AS customer_group,
       s.sessions,
       s.purchases,
       ROUND(100.0 * s.purchases / s.sessions, 2)  AS conversion_rate_pct,
       o.completed_orders,
       ROUND(o.aov, 2)                             AS avg_order_value,
       ROUND(o.revenue / o.buyers, 2)              AS revenue_per_buyer
FROM s JOIN o USING (is_loyalty_member)
ORDER BY s.is_loyalty_member DESC;
