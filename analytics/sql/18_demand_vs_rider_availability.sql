-- Business Question: Do we have enough riders in each city relative to order volume?
-- Expected Output Columns: city, total_orders, active_riders, orders_per_active_rider
-- Business Relevance: Directly answers a rider-supply planning question — a
-- high orders-per-rider ratio signals an understaffed market likely to have
-- slower deliveries and more cancellations; this is the single number an ops
-- lead would look at before approving new rider hiring in a city.
-- Technique(s) demonstrated: CTE, JOIN, LEFT JOIN, GROUP BY

WITH demand AS (
    SELECT l.city, COUNT(*) AS total_orders
    FROM orders o
    JOIN locations l ON l.location_id = o.delivery_location_id
    GROUP BY l.city
),
supply AS (
    SELECT city, COUNT(*) FILTER (WHERE is_active) AS active_riders
    FROM riders
    GROUP BY city
)
SELECT
    d.city,
    d.total_orders,
    COALESCE(s.active_riders, 0) AS active_riders,
    ROUND(d.total_orders::NUMERIC / NULLIF(s.active_riders, 0), 1) AS orders_per_active_rider
FROM demand d
LEFT JOIN supply s ON s.city = d.city
ORDER BY orders_per_active_rider DESC NULLS FIRST;
