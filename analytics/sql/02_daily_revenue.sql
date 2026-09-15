-- Business Question: How much revenue are we actually collecting each day (excluding cancelled orders)?
-- Expected Output Columns: order_date, total_orders, gross_revenue, avg_order_value
-- Business Relevance: Revenue is the metric leadership actually cares about;
-- cancelled orders must be excluded or the number overstates real income.
-- Technique(s) demonstrated: GROUP BY, CASE WHEN, date/time function (DATE())

SELECT
    DATE(order_placed_at) AS order_date,
    COUNT(*) AS total_orders,
    ROUND(SUM(CASE WHEN status <> 'CANCELLED' THEN total_amount ELSE 0 END), 2) AS gross_revenue,
    ROUND(AVG(CASE WHEN status <> 'CANCELLED' THEN total_amount END), 2) AS avg_order_value
FROM orders
GROUP BY DATE(order_placed_at)
ORDER BY order_date;
