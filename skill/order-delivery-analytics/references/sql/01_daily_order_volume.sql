-- Business Question: How many orders come in each day, and is volume trending up or down?
-- Expected Output Columns: order_date, total_orders
-- Business Relevance: The most basic operational signal — staffing, restaurant
-- capacity, and rider scheduling all start from "how many orders are we handling per day."
-- Technique(s) demonstrated: GROUP BY, date/time function (DATE())

SELECT
    DATE(order_placed_at) AS order_date,
    COUNT(*) AS total_orders
FROM orders
GROUP BY DATE(order_placed_at)
ORDER BY order_date;
