-- Business Question: What's the "typical" delivery time customers experience (median, not mean)?
-- Expected Output Columns: city, median_delivery_minutes
-- Business Relevance: Average delivery time is easily skewed by a handful of
-- very slow outlier deliveries; the median is a more honest picture of what a
-- typical customer actually experiences, and is the right metric to advertise.
-- Technique(s) demonstrated: JOIN, GROUP BY, PostgreSQL percentile function (PERCENTILE_CONT)

SELECT
    l.city,
    ROUND(
        PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY EXTRACT(EPOCH FROM (d.delivered_at - o.order_placed_at)) / 60.0
        )::numeric, 1
    ) AS median_delivery_minutes
FROM deliveries d
JOIN orders o ON o.order_id = d.order_id
JOIN locations l ON l.location_id = o.delivery_location_id
WHERE d.delivery_status = 'delivered'
GROUP BY l.city
ORDER BY median_delivery_minutes;
