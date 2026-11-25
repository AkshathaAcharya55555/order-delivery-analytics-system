-- Business Question: Which specific deliveries were statistical outliers — far
-- slower than the rest — and who was involved?
-- Expected Output Columns: order_id, city, rider_name, total_minutes
-- Business Relevance: These are the individual cases worth manually
-- investigating (rider issue? bad address? restaurant delay?) rather than a
-- fixed arbitrary cutoff — the threshold is derived from the data itself
-- (95th percentile), so it adapts if overall delivery speed changes.
-- Technique(s) demonstrated: CTE, JOIN (multiple), PostgreSQL percentile
-- function (PERCENTILE_CONT), subquery (cross join to a scalar threshold)

WITH delivery_minutes AS (
    SELECT
        d.order_id,
        l.city,
        r.first_name || ' ' || r.last_name AS rider_name,
        EXTRACT(EPOCH FROM (d.delivered_at - o.order_placed_at)) / 60.0 AS total_minutes
    FROM deliveries d
    JOIN orders o ON o.order_id = d.order_id
    JOIN locations l ON l.location_id = o.delivery_location_id
    JOIN riders r ON r.rider_id = d.rider_id
    WHERE d.delivery_status = 'delivered'
),
threshold AS (
    SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_minutes) AS p95_minutes
    FROM delivery_minutes
)
SELECT
    dm.order_id, dm.city, dm.rider_name, ROUND(dm.total_minutes::numeric, 1) AS total_minutes
FROM delivery_minutes dm
CROSS JOIN threshold t
WHERE dm.total_minutes > t.p95_minutes
ORDER BY dm.total_minutes DESC
LIMIT 20;
