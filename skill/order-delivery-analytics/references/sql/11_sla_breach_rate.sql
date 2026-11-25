-- Business Question: How often do we miss a delivery-time SLA, and does it vary by city?
-- Expected Output Columns: city, delivered_orders, sla_breaches, sla_breach_rate_pct
-- Business Relevance: SLA breach rate is what operations reports to leadership
-- as a headline reliability number, and a city breakdown shows exactly where
-- to invest in more riders or better restaurant coordination.
--
-- ASSUMED SLA: 45 minutes from order_placed_at to delivered_at. This is a
-- documented ASSUMPTION for this analysis, not a measured or contractual
-- business requirement (none exists in this project) — see README.
-- Technique(s) demonstrated: JOIN, GROUP BY, CASE WHEN, date/time function (EXTRACT EPOCH)

SELECT
    l.city,
    COUNT(*) AS delivered_orders,
    SUM(CASE WHEN EXTRACT(EPOCH FROM (d.delivered_at - o.order_placed_at)) / 60.0 > 45 THEN 1 ELSE 0 END) AS sla_breaches,
    ROUND(
        100.0 * SUM(CASE WHEN EXTRACT(EPOCH FROM (d.delivered_at - o.order_placed_at)) / 60.0 > 45 THEN 1 ELSE 0 END)
        / COUNT(*), 2
    ) AS sla_breach_rate_pct
FROM deliveries d
JOIN orders o ON o.order_id = d.order_id
JOIN locations l ON l.location_id = o.delivery_location_id
WHERE d.delivery_status = 'delivered'
GROUP BY l.city
ORDER BY sla_breach_rate_pct DESC;
