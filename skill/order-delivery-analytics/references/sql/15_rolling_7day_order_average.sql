-- Business Question: What's the smoothed daily order trend, ignoring single-day noise?
-- Expected Output Columns: order_date, total_orders, rolling_7day_avg_orders
-- Business Relevance: A single day's order count is noisy (weekday vs.
-- weekend, a rain event, etc.); a rolling 7-day average is what operations
-- actually watches to tell whether demand is genuinely trending up or down.
-- Technique(s) demonstrated: CTE, window function (AVG OVER with a frame — ROWS BETWEEN)

WITH daily AS (
    SELECT DATE(order_placed_at) AS order_date, COUNT(*) AS total_orders
    FROM orders
    GROUP BY DATE(order_placed_at)
)
SELECT
    order_date,
    total_orders,
    ROUND(AVG(total_orders) OVER (
        ORDER BY order_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 1) AS rolling_7day_avg_orders
FROM daily
ORDER BY order_date;
