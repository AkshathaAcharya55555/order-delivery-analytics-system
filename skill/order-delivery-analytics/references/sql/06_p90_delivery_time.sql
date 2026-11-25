-- Business Question: How slow is delivery for the worst 10% of orders in each city?
-- Expected Output Columns: city, p90_delivery_minutes
-- Business Relevance: P90 (90th percentile) is the standard SLA-planning metric —
-- it answers "what delivery time should we promise/guarantee so 9 out of 10
-- customers are satisfied," which the mean or median alone can't answer.
-- Technique(s) demonstrated: JOIN, GROUP BY, PostgreSQL percentile function (PERCENTILE_CONT)

SELECT
    l.city,
    ROUND(
        PERCENTILE_CONT(0.9) WITHIN GROUP (
            ORDER BY EXTRACT(EPOCH FROM (d.delivered_at - o.order_placed_at)) / 60.0
        )::numeric, 1
    ) AS p90_delivery_minutes
FROM deliveries d
JOIN orders o ON o.order_id = d.order_id
JOIN locations l ON l.location_id = o.delivery_location_id
WHERE d.delivery_status = 'delivered'
GROUP BY l.city
ORDER BY p90_delivery_minutes;
