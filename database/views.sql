-- ============================================================================
-- Analytical views. Run after schema.sql (+ seed.sql for data to query).
-- Each view answers a specific business question rather than being a generic
-- dump, so it can be queried directly from the dashboard / API layer later.
-- ============================================================================

DROP VIEW IF EXISTS city_performance;
DROP VIEW IF EXISTS order_funnel;
DROP VIEW IF EXISTS customer_summary;
DROP VIEW IF EXISTS rider_performance;
DROP VIEW IF EXISTS delivery_performance;
DROP VIEW IF EXISTS daily_orders;

-- ----------------------------------------------------------------------------
-- daily_orders: "When is demand highest?"
-- Order volume and revenue by calendar day.
-- ----------------------------------------------------------------------------
CREATE VIEW daily_orders AS
SELECT
    DATE(order_placed_at) AS order_date,
    COUNT(*) AS total_orders,
    COUNT(*) FILTER (WHERE status = 'DELIVERED') AS delivered_orders,
    COUNT(*) FILTER (WHERE status = 'CANCELLED') AS cancelled_orders,
    ROUND(SUM(total_amount) FILTER (WHERE status <> 'CANCELLED'), 2) AS gross_revenue,
    ROUND(AVG(total_amount), 2) AS avg_order_value
FROM orders
GROUP BY DATE(order_placed_at)
ORDER BY order_date;

-- ----------------------------------------------------------------------------
-- delivery_performance: "What causes late deliveries?"
-- Per-order delivery timing. Row-level (not pre-aggregated) so the dashboard
-- / EDA layer can define and apply an on-time SLA threshold itself — no
-- SLA minute value is baked in here since that is a business assumption,
-- not a measured fact.
-- ----------------------------------------------------------------------------
CREATE VIEW delivery_performance AS
SELECT
    o.order_id,
    o.customer_id,
    d.rider_id,
    l.city,
    o.order_placed_at,
    d.assigned_at,
    d.picked_up_at,
    d.delivered_at,
    d.delivery_status,
    ROUND(EXTRACT(EPOCH FROM (d.delivered_at - o.order_placed_at)) / 60.0, 1) AS total_delivery_minutes,
    ROUND(EXTRACT(EPOCH FROM (d.picked_up_at - d.assigned_at)) / 60.0, 1) AS rider_pickup_wait_minutes,
    ROUND(EXTRACT(EPOCH FROM (d.delivered_at - d.picked_up_at)) / 60.0, 1) AS transit_minutes,
    d.distance_km
FROM orders o
JOIN deliveries d ON d.order_id = o.order_id
JOIN locations l ON l.location_id = o.delivery_location_id
WHERE d.delivery_status = 'delivered';

-- ----------------------------------------------------------------------------
-- rider_performance: "Which riders perform best?"
-- Per-rider completion counts, average transit time, and a rank within
-- their own city (window function over an aggregated CTE).
-- ----------------------------------------------------------------------------
CREATE VIEW rider_performance AS
WITH rider_stats AS (
    SELECT
        r.rider_id,
        r.first_name || ' ' || r.last_name AS rider_name,
        r.city,
        r.rating,
        COUNT(d.delivery_id) AS total_deliveries_assigned,
        COUNT(*) FILTER (WHERE d.delivery_status = 'delivered') AS completed_deliveries,
        COUNT(*) FILTER (WHERE d.delivery_status = 'failed') AS failed_deliveries,
        ROUND(AVG(EXTRACT(EPOCH FROM (d.delivered_at - d.picked_up_at)) / 60.0)
              FILTER (WHERE d.delivery_status = 'delivered'), 2) AS avg_transit_minutes
    FROM riders r
    LEFT JOIN deliveries d ON d.rider_id = r.rider_id
    GROUP BY r.rider_id, r.first_name, r.last_name, r.city, r.rating
)
SELECT
    rider_id,
    rider_name,
    city,
    rating,
    total_deliveries_assigned,
    completed_deliveries,
    failed_deliveries,
    avg_transit_minutes,
    RANK() OVER (PARTITION BY city ORDER BY completed_deliveries DESC) AS rank_in_city
FROM rider_stats;

-- ----------------------------------------------------------------------------
-- customer_summary: "What is customer repeat behavior?"
-- Per-customer order count, spend, and a repeat-customer flag.
-- ----------------------------------------------------------------------------
CREATE VIEW customer_summary AS
SELECT
    c.customer_id,
    c.first_name || ' ' || c.last_name AS customer_name,
    l.city,
    COUNT(o.order_id) AS total_orders,
    COUNT(*) FILTER (WHERE o.status = 'CANCELLED') AS cancelled_orders,
    ROUND(SUM(o.total_amount) FILTER (WHERE o.status <> 'CANCELLED'), 2) AS lifetime_spend,
    MIN(o.order_placed_at) AS first_order_at,
    MAX(o.order_placed_at) AS last_order_at,
    CASE
        WHEN COUNT(o.order_id) FILTER (WHERE o.status <> 'CANCELLED') > 1 THEN TRUE
        ELSE FALSE
    END AS is_repeat_customer
FROM customers c
LEFT JOIN locations l ON l.location_id = c.default_location_id
LEFT JOIN orders o ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.first_name, c.last_name, l.city;

-- ----------------------------------------------------------------------------
-- order_funnel: "What operational bottlenecks exist?"
-- How many distinct orders reached each lifecycle stage.
-- ----------------------------------------------------------------------------
CREATE VIEW order_funnel AS
SELECT
    status,
    COUNT(DISTINCT order_id) AS orders_reached_stage
FROM order_status_history
GROUP BY status
ORDER BY
    CASE status
        WHEN 'PLACED'            THEN 1
        WHEN 'CONFIRMED'         THEN 2
        WHEN 'PREPARING'         THEN 3
        WHEN 'READY_FOR_PICKUP'  THEN 4
        WHEN 'RIDER_ASSIGNED'    THEN 5
        WHEN 'PICKED_UP'         THEN 6
        WHEN 'OUT_FOR_DELIVERY'  THEN 7
        WHEN 'DELIVERED'         THEN 8
        WHEN 'CANCELLED'         THEN 9
        WHEN 'FAILED'            THEN 10
    END;

-- ----------------------------------------------------------------------------
-- city_performance: "Which cities perform best/worst?"
-- Order volume, cancellation rate, revenue, and average delivery time by city.
-- ----------------------------------------------------------------------------
CREATE VIEW city_performance AS
SELECT
    l.city,
    COUNT(DISTINCT o.order_id) AS total_orders,
    COUNT(DISTINCT o.order_id) FILTER (WHERE o.status = 'CANCELLED') AS cancelled_orders,
    ROUND(
        COUNT(DISTINCT o.order_id) FILTER (WHERE o.status = 'CANCELLED')::NUMERIC
        / NULLIF(COUNT(DISTINCT o.order_id), 0) * 100, 2
    ) AS cancellation_rate_pct,
    ROUND(SUM(o.total_amount) FILTER (WHERE o.status <> 'CANCELLED'), 2) AS gross_revenue,
    ROUND(AVG(EXTRACT(EPOCH FROM (d.delivered_at - o.order_placed_at)) / 60.0)
          FILTER (WHERE d.delivery_status = 'delivered'), 2) AS avg_delivery_minutes
FROM locations l
JOIN orders o ON o.delivery_location_id = l.location_id
LEFT JOIN deliveries d ON d.order_id = o.order_id
GROUP BY l.city
ORDER BY total_orders DESC;
