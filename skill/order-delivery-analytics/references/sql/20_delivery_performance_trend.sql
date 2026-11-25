-- Business Question: Is delivery speed improving or getting worse week over week?
-- Expected Output Columns: week_start, delivered_orders, avg_delivery_minutes, prev_week_avg_minutes, change_minutes
-- Business Relevance: Operational leadership needs a trend, not a single
-- snapshot, to tell whether recent process changes (new riders, route
-- changes, restaurant partners) are actually helping or hurting delivery speed.
-- Technique(s) demonstrated: CTE, JOIN, GROUP BY, window function (LAG),
-- date/time function (DATE_TRUNC)

WITH weekly AS (
    SELECT
        DATE_TRUNC('week', o.order_placed_at)::date AS week_start,
        COUNT(*) AS delivered_orders,
        ROUND(AVG(EXTRACT(EPOCH FROM (d.delivered_at - o.order_placed_at)) / 60.0)::numeric, 1) AS avg_delivery_minutes
    FROM deliveries d
    JOIN orders o ON o.order_id = d.order_id
    WHERE d.delivery_status = 'delivered'
    GROUP BY DATE_TRUNC('week', o.order_placed_at)
)
SELECT
    week_start,
    delivered_orders,
    avg_delivery_minutes,
    LAG(avg_delivery_minutes) OVER (ORDER BY week_start) AS prev_week_avg_minutes,
    ROUND(avg_delivery_minutes - LAG(avg_delivery_minutes) OVER (ORDER BY week_start), 1) AS change_minutes
FROM weekly
ORDER BY week_start;
