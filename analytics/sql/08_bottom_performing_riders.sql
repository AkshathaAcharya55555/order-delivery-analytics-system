-- Business Question: Which riders have a failed-delivery rate meaningfully worse than average?
-- Expected Output Columns: rider_id, rider_name, city, total_assigned, failed_deliveries, failure_rate_pct
-- Business Relevance: Flags riders who may need coaching, retraining, or
-- performance review — an operational quality-control signal, not a punitive
-- list; riders with too few deliveries to judge fairly are excluded.
-- Technique(s) demonstrated: CTE, LEFT JOIN, GROUP BY, HAVING, correlated subquery in WHERE

WITH rider_stats AS (
    SELECT
        r.rider_id,
        r.first_name || ' ' || r.last_name AS rider_name,
        r.city,
        COUNT(d.delivery_id) AS total_assigned,
        COUNT(d.delivery_id) FILTER (WHERE d.delivery_status = 'failed') AS failed_deliveries,
        ROUND(100.0 * COUNT(d.delivery_id) FILTER (WHERE d.delivery_status = 'failed')
              / NULLIF(COUNT(d.delivery_id), 0), 2) AS failure_rate_pct
    FROM riders r
    LEFT JOIN deliveries d ON d.rider_id = r.rider_id
    GROUP BY r.rider_id, r.first_name, r.last_name, r.city
    HAVING COUNT(d.delivery_id) >= 10   -- enough sample size to judge fairly
)
SELECT *
FROM rider_stats
WHERE failure_rate_pct > (SELECT AVG(failure_rate_pct) FROM rider_stats)
ORDER BY failure_rate_pct DESC
LIMIT 10;
