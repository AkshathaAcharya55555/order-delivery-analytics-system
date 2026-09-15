-- Business Question: Which cities have the worst order-cancellation problem?
-- Expected Output Columns: city, total_orders, cancelled_orders, cancellation_rate_pct
-- Business Relevance: A high cancellation rate in one city points to a local
-- operational problem (restaurant reliability, rider shortage, app issues in
-- that market) that a single company-wide average would hide.
-- Technique(s) demonstrated: JOIN, GROUP BY, CASE WHEN, HAVING

SELECT
    l.city,
    COUNT(*) AS total_orders,
    SUM(CASE WHEN o.status = 'CANCELLED' THEN 1 ELSE 0 END) AS cancelled_orders,
    ROUND(100.0 * SUM(CASE WHEN o.status = 'CANCELLED' THEN 1 ELSE 0 END) / COUNT(*), 2) AS cancellation_rate_pct
FROM orders o
JOIN locations l ON l.location_id = o.delivery_location_id
GROUP BY l.city
HAVING COUNT(*) >= 50          -- exclude cities with too little volume to be statistically meaningful
ORDER BY cancellation_rate_pct DESC;
