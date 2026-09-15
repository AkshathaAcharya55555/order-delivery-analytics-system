# Analytics

This project has three analytics layers, all reading the same PostgreSQL
database: 20 standalone SQL queries (`analytics/sql/`), a Python/pandas
layer (`analytics/scripts/`, `analytics/notebooks/`), and 10 automated
data-quality checks (`data_quality/`). This document summarizes what each
one covers and how they relate; full detail lives in each layer's own
README (`analytics/sql/README.md`, `analytics/README.md`,
`data_quality/README.md`), which this document links to rather than
duplicates in full.

## SQL analytics layer (`analytics/sql/`)

20 queries, each answering one specific business question, executed
against the full loaded dataset (see `docs/DATABASE.md` for exact row
counts).

| # | Business question |
|---|---|
| 1 | How many orders come in each day, and is volume trending up or down? |
| 2 | How much revenue are we actually collecting each day (excluding cancelled orders)? |
| 3 | Which cities have the worst order-cancellation problem? |
| 4 | How long does a delivery take from order to doorstep, by city? |
| 5 | What's the "typical" delivery time customers experience (median, not mean)? |
| 6 | How slow is delivery for the worst 10% of orders in each city? |
| 7 | Who are our 10 best-performing riders by completed deliveries? |
| 8 | Which riders have a failed-delivery rate meaningfully worse than average? |
| 9 | What share of our customers have ordered more than once? |
| 10 | What time of day does demand peak? |
| 11 | How often do we miss a delivery-time SLA, and does it vary by city? |
| 12 | How intensively is each rider actually being used, relative to how long they've been on the platform? |
| 13 | What does the distribution of "orders per customer" look like? |
| 14 | How do our cities rank against each other on volume and revenue? |
| 15 | What's the smoothed daily order trend, ignoring single-day noise? |
| 16 | Where in the order lifecycle do orders drop off, and how long does an order spend in each stage on average? |
| 17 | Which specific deliveries were statistical outliers, and who was involved? |
| 18 | Do we have enough riders in each city relative to order volume? |
| 19 | Is the business growing month over month? |
| 20 | Is delivery speed improving or getting worse week over week? |

Full SQL, expected output columns, and business relevance for each are in
[`analytics/sql/README.md`](../analytics/sql/README.md).

### SQL techniques demonstrated

| Technique | Used in queries |
|---|---|
| JOIN | 3, 4, 5, 6, 11, 14, 17, 18, 20 |
| LEFT JOIN | 7, 8, 12, 18 |
| GROUP BY | nearly all |
| HAVING | 3, 8 |
| CASE WHEN | 2, 3, 8, 9, 11, 14, 16, 19 |
| CTE (`WITH`) | 7, 8, 9, 12, 13, 14, 15, 16, 17, 18, 19, 20 |
| Subquery | 8 (correlated), 9 (scalar), 17 (cross join to scalar) |
| Window function | 7, 9, 14, 15, 16, 19, 20 |
| RANK | 7, 14 |
| ROW_NUMBER | 9 |
| LAG / LEAD | 16, 19, 20 |
| Date/time functions | 1, 2, 4, 5, 6, 10, 11, 12, 15, 19, 20 |
| PERCENTILE_CONT | 5, 6, 17 |

All 20 files are also covered by an automated regression test
(`tests/analytics_sql/test_sql_queries.py`) that executes each one against
the live database and asserts it runs without error and returns at least
one row — see `docs/TESTING.md`.

## Python analytics layer (`analytics/scripts/`, `analytics/notebooks/`)

pandas/NumPy/matplotlib/SQLAlchemy analysis of the same database, organized
as reusable modules (`db.py`, `queries.py`, `metrics.py`, `charts.py`) plus
`run_eda.py` as the single source of truth for every printed number, and an
executed Jupyter notebook (`eda_analysis.ipynb`) that narrates the same
analysis with inline charts.

### Why SQL in one layer and pandas in another

Every query in `analytics/scripts/queries.py` either joins across tables or
does a `GROUP BY` that collapses row count by 100-1000x before pandas ever
sees the result (e.g., 91,257 delivery rows join down to 2,000 rider rows
via SQL). Row-level data (the full `orders` and delivery-facts tables) is
pulled into pandas specifically because *several different* metrics reuse
the same pull (completion rate, cancellation rate, average order value,
order trend, delivery percentiles, histogram, skewness) — one round trip
serving many derived calculations, rather than a separate SQL query per
metric. Percentiles specifically are computed with `np.percentile()` rather
than another `PERCENTILE_CONT` query, since the same in-memory Series also
feeds the histogram and skewness check.

### Metrics calculated (exact formulas in `analytics/scripts/metrics.py`)

- **Order volume**: total, completed, cancelled, in-progress counts and
  rates (`completed / total`, etc.)
- **Order value**: mean and median `total_amount` (non-cancelled orders only)
- **Delivery time**: mean, median, P90 (via `np.percentile`), and a late-
  delivery rate against an explicitly-labeled *assumed* (not measured)
  45-minute SLA
- **Rider utilization**: completed deliveries ÷ days active, where "days
  active" uses the dataset's own latest order date as "today" (this is
  historical synthetic data — the real current date would make every rider
  look almost idle)
- **Repeat-customer rate**: share of ordering customers with ≥2 non-cancelled orders
- **City performance**: per-city totals, cancellation rate, completion rate

### Validation performed

`run_eda.py` was executed against the live database; the notebook was
executed end-to-end via `nbconvert` (confirmed zero error cells across all
28 cells). Every pandas/NumPy result was cross-checked against the
equivalent pure-SQL query in `analytics/sql/` and agreed within rounding.
Full detail in [`analytics/README.md`](../analytics/README.md).

## Data-quality validation (`data_quality/`)

10 rules (`data_quality/validate.py`) run against the **raw**
`data_generator/output/*.csv` files (not the already-loaded Postgres
tables, since the bulk-load step already excludes some invalid rows —
checking the loaded table would falsely report "0 problems" for that
specific issue).

| Rule | Checks | Result classification |
|---|---|---|
| DQ-01 | Missing customer IDs | structural (expect 0) |
| DQ-02 | Duplicate order IDs | structural (expect 0) |
| DQ-03 | Duplicate event IDs (content-level, simulating Kafka redelivery) | intentionally corrupted |
| DQ-04 | Invalid delivery durations (delivered before pickup, pickup before assignment) | intentionally corrupted |
| DQ-05 | `orders.status` disagreeing with its own history's last entry | intentionally corrupted |
| DQ-06 | Missing rider assignments where status implies one exists | intentionally corrupted (investigated, traced to DQ-05's root cause) |
| DQ-07 | Orphan records across 6 FK relationships | structural (expect 0) |
| DQ-08 | Invalid order/item values (≤0 amounts, negative prices, non-positive quantities) | structural (expect 0) |
| DQ-09 | Missing required timestamps | structural (expect 0) |
| DQ-10 | Inconsistent city-name values | intentionally corrupted |

Each rule reports `records_checked`, `records_failed`, `failure_rate_pct`,
`severity`, and `expected_source` (whether a nonzero result is a genuine
bug or the expected detection of a deliberately-injected test issue). Full
results table, the DQ-06 root-cause investigation, and the severity-scale
rationale are in [`data_quality/README.md`](../data_quality/README.md).
All 10 rule functions additionally have unit tests
(`tests/data_quality/test_validate_rules.py`, 24 tests) against hand-built
clean/dirty DataFrames, independent of the full CSV run.

## Business insights (`reports/business_insights.md`)

The findings write-up for a non-technical reader, sourced only from actual
runs of the SQL and Python layers above. Headline figures from that run
(dataset: 100,000 orders, 90-day window, 6 cities, 2,000 riders, 50,000
customers):

- 90.30% completed, 8.04% cancelled, 1.66% still in progress
- Clear weekly demand cycle (Friday/Saturday peaks vs. a lower weekday
  baseline), not a growth or decline trend across the 90-day window
- Average order value $26.16 (median $23.50), stable day to day
- Average delivery time 49.33 minutes (median 48.48, P90 67.07)
- 61.66% repeat-customer rate (customers with 2+ non-cancelled orders)
- Cancellation/completion rates are tight across all 6 cities (no city with
  a distinct cancellation problem)
- Rider supply is not proportional to demand: Miami and Portland have
  markedly more orders per active rider than Austin or Seattle
- Demand peaks at dinner (18-20h) and lunch (12-13h); of the order
  lifecycle stages, rider transit and kitchen prep are the two slowest

**Every one of these figures carries an explicit caveat in the source
report** that a reader should not skip: this is synthetic data with
deliberately-designed shape (several "findings" — the repeat-customer rate,
the Miami/Portland rider shortage — are confirmations that the generator
and the analysis behaved as designed, not organic discoveries about a real
business), the 45-minute SLA is an illustrative assumption (not a real,
approved business target — and it sits below the actual median delivery
time, which is most of why the resulting "breach rate" looks high), and the
loaded dataset still contains a small number (well under 0.1%) of orders
created during later manual/automated testing, not part of the original
analytics run. None of this is hidden — see `reports/business_insights.md`'s
own "Important caveats on every finding above" section.

## Dashboard (`dashboard/`)

A six-page Streamlit app (Executive Overview, Order Trends, Delivery
Performance, Rider Performance, Customer Analytics, Data Quality) that
computes every KPI and chart live from the database using the same
`analytics/scripts/metrics.py` formulas (imported directly, not
reimplemented) — so its numbers match the business-insights figures above
exactly when its date/city/status filters aren't narrowing the data. Full
detail in [`dashboard/README.md`](../dashboard/README.md).
