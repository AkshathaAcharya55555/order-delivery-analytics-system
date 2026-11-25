-- Business Question: How do our cities rank against each other on volume and revenue?
-- Expected Output Columns: city, total_orders, gross_revenue, revenue_rank, volume_rank
-- Business Relevance: A single ranked view lets leadership immediately see
-- whether the same cities lead on both volume and revenue, or whether a
-- lower-volume city is actually punching above its weight on revenue per order.
-- Technique(s) demonstrated: CTE, JOIN, GROUP BY, CASE WHEN, window function (RANK, two independent rankings)

WITH city_stats AS (
    SELECT
        l.city,
        COUNT(*) AS total_orders,
        ROUND(SUM(CASE WHEN o.status <> 'CANCELLED' THEN o.total_amount ELSE 0 END), 2) AS gross_revenue
    FROM orders o
    JOIN locations l ON l.location_id = o.delivery_location_id
    GROUP BY l.city
)
SELECT
    city,
    total_orders,
    gross_revenue,
    RANK() OVER (ORDER BY gross_revenue DESC) AS revenue_rank,
    RANK() OVER (ORDER BY total_orders DESC) AS volume_rank
FROM city_stats
ORDER BY revenue_rank;
