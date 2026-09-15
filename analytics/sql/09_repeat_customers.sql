-- Business Question: What share of our customers have ordered more than once?
-- Expected Output Columns: repeat_customers, total_ordering_customers, repeat_customer_rate_pct
-- Business Relevance: Repeat-purchase rate is a core retention/loyalty metric —
-- it's far cheaper to keep an existing customer ordering than to acquire a new one.
-- Technique(s) demonstrated: CTE, window function (ROW_NUMBER), scalar subqueries, CASE WHEN

WITH customer_orders AS (
    SELECT
        customer_id,
        order_id,
        order_placed_at,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_placed_at) AS order_seq
    FROM orders
    WHERE status <> 'CANCELLED'    -- a cancelled order shouldn't count as a "purchase"
)
SELECT
    (SELECT COUNT(DISTINCT customer_id) FROM customer_orders WHERE order_seq >= 2) AS repeat_customers,
    (SELECT COUNT(DISTINCT customer_id) FROM customer_orders) AS total_ordering_customers,
    ROUND(
        100.0 * (SELECT COUNT(DISTINCT customer_id) FROM customer_orders WHERE order_seq >= 2)
        / NULLIF((SELECT COUNT(DISTINCT customer_id) FROM customer_orders), 0), 2
    ) AS repeat_customer_rate_pct;
