-- Business Question: Who are our 10 best-performing riders by completed deliveries?
-- Expected Output Columns: rider_id, rider_name, city, completed_deliveries, avg_transit_minutes, rank_overall
-- Business Relevance: Identifies riders worth retaining/rewarding and gives a
-- performance benchmark other riders can be measured against.
-- Technique(s) demonstrated: CTE, LEFT JOIN, GROUP BY, window function (RANK)

WITH rider_stats AS (
    SELECT
        r.rider_id,
        r.first_name || ' ' || r.last_name AS rider_name,
        r.city,
        COUNT(d.delivery_id) FILTER (WHERE d.delivery_status = 'delivered') AS completed_deliveries,
        ROUND(AVG(EXTRACT(EPOCH FROM (d.delivered_at - d.picked_up_at)) / 60.0)
              FILTER (WHERE d.delivery_status = 'delivered'), 1) AS avg_transit_minutes
    FROM riders r
    LEFT JOIN deliveries d ON d.rider_id = r.rider_id
    GROUP BY r.rider_id, r.first_name, r.last_name, r.city
)
SELECT
    rider_id, rider_name, city, completed_deliveries, avg_transit_minutes,
    RANK() OVER (ORDER BY completed_deliveries DESC) AS rank_overall
FROM rider_stats
ORDER BY completed_deliveries DESC
LIMIT 10;
