-- Business Question: What does the distribution of "orders per customer" look like?
-- Expected Output Columns: order_count, number_of_customers
-- Business Relevance: Underpins customer segmentation (one-time vs. occasional
-- vs. loyal customers) — a marketing team would target each segment very
-- differently (win-back vs. loyalty rewards).
-- Technique(s) demonstrated: CTE, GROUP BY, subquery

WITH customer_order_counts AS (
    SELECT customer_id, COUNT(*) AS order_count
    FROM orders
    WHERE status <> 'CANCELLED'
    GROUP BY customer_id
)
SELECT
    order_count,
    COUNT(*) AS number_of_customers
FROM customer_order_counts
GROUP BY order_count
ORDER BY order_count;
