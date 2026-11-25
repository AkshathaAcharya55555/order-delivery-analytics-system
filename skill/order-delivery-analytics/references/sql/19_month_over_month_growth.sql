-- Business Question: Is the business growing month over month?
-- Expected Output Columns: order_month, total_orders, gross_revenue, prev_month_revenue, revenue_growth_pct
-- Business Relevance: The standard headline growth metric for any leadership
-- review — raw revenue alone doesn't tell you the trend, the period-over-period
-- comparison does.
-- Note: the generated dataset spans a fixed 90-day window (~3 calendar
-- months), so this will show only 2-3 rows — real, not fabricated to look
-- more impressive than the underlying data supports.
-- Technique(s) demonstrated: CTE, GROUP BY, CASE WHEN, window function (LAG),
-- date/time function (DATE_TRUNC)

WITH monthly AS (
    SELECT
        DATE_TRUNC('month', order_placed_at)::date AS order_month,
        COUNT(*) AS total_orders,
        ROUND(SUM(CASE WHEN status <> 'CANCELLED' THEN total_amount ELSE 0 END), 2) AS gross_revenue
    FROM orders
    GROUP BY DATE_TRUNC('month', order_placed_at)
)
SELECT
    order_month,
    total_orders,
    gross_revenue,
    LAG(gross_revenue) OVER (ORDER BY order_month) AS prev_month_revenue,
    ROUND(
        100.0 * (gross_revenue - LAG(gross_revenue) OVER (ORDER BY order_month))
        / NULLIF(LAG(gross_revenue) OVER (ORDER BY order_month), 0), 2
    ) AS revenue_growth_pct
FROM monthly
ORDER BY order_month;
