-- Business Question: How intensively is each rider actually being used, relative to how long they've been on the platform?
-- Expected Output Columns: rider_id, rider_name, days_active, completed_deliveries, deliveries_per_day
-- Business Relevance: Low utilization for a long-tenured rider suggests
-- under-scheduling or an area with too many riders for the demand; very high
-- utilization can flag burnout risk or an under-staffed area propping itself
-- up on a few riders.
--
-- Uses the dataset's own latest order date as "today" (a fixed snapshot,
-- since this is historical synthetic data, not a live feed) rather than the
-- real current date, which would make every rider look barely utilized.
-- Technique(s) demonstrated: CTE, LEFT JOIN, GROUP BY, subquery, date/time function

WITH snapshot AS (
    SELECT MAX(order_placed_at)::date AS as_of_date FROM orders
),
rider_activity AS (
    SELECT
        r.rider_id,
        r.first_name || ' ' || r.last_name AS rider_name,
        GREATEST((SELECT as_of_date FROM snapshot) - r.joined_date, 1) AS days_active,
        COUNT(d.delivery_id) FILTER (WHERE d.delivery_status = 'delivered') AS completed_deliveries
    FROM riders r
    LEFT JOIN deliveries d ON d.rider_id = r.rider_id
    GROUP BY r.rider_id, r.first_name, r.last_name, r.joined_date
)
SELECT
    rider_id, rider_name, days_active, completed_deliveries,
    ROUND(completed_deliveries::NUMERIC / days_active, 3) AS deliveries_per_day
FROM rider_activity
ORDER BY deliveries_per_day DESC
LIMIT 20;
