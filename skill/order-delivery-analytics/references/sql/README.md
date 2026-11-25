# SQL KPI pack (PostgreSQL)

Twenty standalone, commented queries. Each states the business question,
the output columns and why it matters. They are written against the reference
schema in `assets/schema/schema.sql`. For a different schema, rename the
tables and columns using the user's `mapping.json`:

| reference | canonical (mapping.json) |
|---|---|
| `orders.order_placed_at` | `orders.placed_at` |
| `orders.delivery_location_id` → `locations.city` | `orders.city` |
| `deliveries.delivered_at / picked_up_at / assigned_at` | same |
| `deliveries.delivery_status = 'delivered'` | outcome `delivered` in `status_map` |
| `order_status_history.status / changed_at` | `status_history.status / changed_at` |

Use these when the user wants the logic **inside their warehouse**, such as a
dbt model, a BI tool or a scheduled query, rather than a one-off Python
report. Every query is read-only (SELECT only).

| # | file | question |
|---|---|---|
| 01 | daily_order_volume | Orders per day |
| 02 | daily_revenue | Revenue per day |
| 03 | cancellation_rate_by_city | Where are orders cancelled most? |
| 04 | avg_delivery_time_by_city | Average delivery time by city |
| 05 | median_delivery_time | p50 delivery time (`PERCENTILE_CONT`) |
| 06 | p90_delivery_time | Tail delivery time |
| 07 | top_10_riders | Best riders by volume and speed |
| 08 | bottom_performing_riders | Coaching candidates |
| 09 | repeat_customers | Retention |
| 10 | peak_ordering_hours | Demand by hour |
| 11 | sla_breach_rate | SLA misses by city (45 min placeholder; parameterise it) |
| 12 | rider_utilization | Deliveries per active rider-day |
| 13 | customer_order_frequency | Order-count distribution |
| 14 | city_ranking | Composite city ranking (window functions) |
| 15 | rolling_7day_order_average | Smoothed demand trend |
| 16 | order_funnel | Stage-to-stage conversion from status history |
| 17 | abnormally_long_deliveries | Outliers vs city median |
| 18 | demand_vs_rider_availability | Supply/demand balance |
| 19 | month_over_month_growth | MoM growth (`LAG`) |
| 20 | delivery_performance_trend | Weekly delivery-time trend |
