-- Business Question: How long does a delivery take from order to doorstep, by city?
-- Expected Output Columns: city, delivered_count, avg_delivery_minutes
-- Business Relevance: Delivery time is a core customer-experience metric and
-- varies by market density/distance — averaging across all cities would hide
-- which specific markets need more riders or better restaurant-side prep times.
-- Technique(s) demonstrated: JOIN (multiple tables), GROUP BY, date/time function (EXTRACT EPOCH)

SELECT
    l.city,
    COUNT(*) AS delivered_count,
    ROUND(AVG(EXTRACT(EPOCH FROM (d.delivered_at - o.order_placed_at)) / 60.0), 1) AS avg_delivery_minutes
FROM deliveries d
JOIN orders o ON o.order_id = d.order_id
JOIN locations l ON l.location_id = o.delivery_location_id
WHERE d.delivery_status = 'delivered'
GROUP BY l.city
ORDER BY avg_delivery_minutes;
