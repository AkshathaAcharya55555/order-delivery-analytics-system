-- Business Question: Where in the order lifecycle do orders drop off, and how
-- long does an order spend in each stage on average?
-- Expected Output Columns: (Part A) status, orders_reached_stage;
--                          (Part B) status, transitions, avg_minutes_in_stage
-- Business Relevance: Part A shows the classic conversion funnel (how many
-- orders make it from placed -> delivered vs. drop out to cancelled) — the
-- single clearest view of where the operational process leaks orders. Part B
-- pinpoints WHICH stage is slow (e.g. kitchen prep vs. rider transit), which
-- is the actionable next question once the funnel shows a bottleneck exists.
-- Technique(s) demonstrated: GROUP BY, CASE WHEN (custom ORDER BY), CTE,
-- window functions LAG and LEAD

-- Part A: funnel — how many distinct orders reached each stage
SELECT
    status,
    COUNT(DISTINCT order_id) AS orders_reached_stage
FROM order_status_history
GROUP BY status
ORDER BY CASE status
    WHEN 'PLACED' THEN 1
    WHEN 'CONFIRMED' THEN 2
    WHEN 'PREPARING' THEN 3
    WHEN 'READY_FOR_PICKUP' THEN 4
    WHEN 'RIDER_ASSIGNED' THEN 5
    WHEN 'PICKED_UP' THEN 6
    WHEN 'OUT_FOR_DELIVERY' THEN 7
    WHEN 'DELIVERED' THEN 8
    WHEN 'CANCELLED' THEN 9
    WHEN 'FAILED' THEN 10
END;

-- Part B: average time spent in each stage, using LEAD to find the timestamp
-- the order left that stage (and LAG available for the symmetric "what stage
-- did we come from" question, shown for completeness)
WITH stage_transitions AS (
    SELECT
        order_id,
        status,
        changed_at,
        LAG(status) OVER (PARTITION BY order_id ORDER BY changed_at) AS previous_status,
        LEAD(changed_at) OVER (PARTITION BY order_id ORDER BY changed_at) AS next_changed_at
    FROM order_status_history
)
SELECT
    status,
    COUNT(*) AS transitions,
    ROUND(AVG(EXTRACT(EPOCH FROM (next_changed_at - changed_at)) / 60.0)::numeric, 2) AS avg_minutes_in_stage
FROM stage_transitions
WHERE next_changed_at IS NOT NULL
GROUP BY status
ORDER BY CASE status
    WHEN 'PLACED' THEN 1
    WHEN 'CONFIRMED' THEN 2
    WHEN 'PREPARING' THEN 3
    WHEN 'READY_FOR_PICKUP' THEN 4
    WHEN 'OUT_FOR_DELIVERY' THEN 5
    ELSE 6
END;
