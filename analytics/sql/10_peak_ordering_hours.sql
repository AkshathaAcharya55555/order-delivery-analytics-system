-- Business Question: What time of day does demand peak?
-- Expected Output Columns: hour_of_day, total_orders
-- Business Relevance: Directly drives rider and restaurant-partner staffing
-- schedules — under-staffing during the actual peak hours is what causes late
-- deliveries and cancellations in the first place.
-- Technique(s) demonstrated: GROUP BY, date/time function (EXTRACT HOUR)

SELECT
    EXTRACT(HOUR FROM order_placed_at) AS hour_of_day,
    COUNT(*) AS total_orders
FROM orders
GROUP BY EXTRACT(HOUR FROM order_placed_at)
ORDER BY total_orders DESC;
