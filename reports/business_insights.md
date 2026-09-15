# Business Insights

Findings from the full generated dataset (100,000 orders, 90-day window,
6 cities, 2,000 riders, 50,000 customers — synthetic data, not a real
company's data; see root README). Every number below was produced by an
actual run of `analytics/scripts/run_eda.py` and/or `analytics/sql/`
against the live database on 2026-09-15 — nothing here is estimated or
invented. Charts referenced are in `analytics/charts/`.

## 1. Order volume and outcomes

- **100,000 total orders** over the 90-day window.
- **90,296 completed (90.30%)**, **8,044 cancelled (8.04%)**, **1,660 still
  in progress (1.66%)** — the in-progress orders are ones placed in the
  final hours of the dataset's snapshot window, not a processing backlog.
- Daily volume oscillates on a **clear weekly cycle** (Friday/Saturday
  peaks around 1,300-1,430 orders/day vs. a ~940-990/day weekday baseline)
  rather than trending up or down across the 90 days — see
  `analytics/charts/order_trend.png`.

**Recommendation:** with a flat 90-day trend, any near-term capacity
planning should be built around the *weekly cycle*, not a growth
projection — this dataset shows no evidence of organic growth to plan
around.

## 2. Revenue

- **Average order value: $26.16** (median: $23.50) — stable within a
  narrow ~$24-28 band on every single day of the window. Day-to-day revenue
  swings are driven almost entirely by order *volume*, not basket size.

## 3. Delivery performance

- **Average delivery time: 49.33 minutes** (order placed → delivered),
  **median: 48.48 minutes**, **P90: 67.07 minutes**.
- The distribution is right-skewed (skewness 0.28) — a longer tail of slow
  deliveries rather than a symmetric spread — see
  `analytics/charts/delivery_time_histogram.png`.
- Delivery time is close to uniform across cities (medians 48.3-48.7 min,
  P90s 66.8-67.2 min per `analytics/sql/README.md` queries 5-6) — this
  dataset shows **no single city with a distinctly worse delivery-speed
  problem**.

**On the 59.35% "late delivery rate":** this analysis used an **illustrative
45-minute SLA threshold**, since no real, business-approved SLA exists for
this project. That assumed threshold sits *below* the actual median
delivery time (48.48 min) — meaning most of this "breach rate" is an
artifact of the assumed number being unrealistically tight, not a
discovered operational failure. **This should not be read as "we miss our
SLA 59% of the time"** — it should be read as "if a 45-minute SLA were ever
adopted, it would need supporting operational changes, because the current
median delivery time already exceeds it." A real SLA conversation needs a
business-approved threshold before this rate means anything.

## 4. Rider performance

- Riders in **Miami and Portland** carry the highest completed-delivery
  counts individually (top 10 riders by volume are all based in one of
  these two cities — `analytics/sql/README.md` query 7) — consistent with
  finding #6 below (these two cities are relatively understaffed, so each
  rider there handles more volume).
- Rider-level utilization (deliveries per day active) could not be reliably
  computed at the individual level from this dataset: rider `joined_date`
  was generated independently of delivery activity, so a handful of riders
  show a `joined_date` right at the dataset's snapshot date despite having
  completed many deliveries earlier in the window — producing a
  meaningless "70+ deliveries per day" for those specific rows. **This is a
  known synthetic-data limitation, disclosed rather than presented as a
  real utilization insight** — a production dataset would derive "active
  since" from a rider's first delivery, not their signup date.

## 5. Customer behavior

- **61.66% of ordering customers (21,804 of 35,363) placed more than one
  order** in the window.
- Order frequency follows a long-tail distribution: 13,559 customers
  ordered exactly once, dropping off sharply from there (8,752 twice, 5,219
  three times, …), with a small number of high-frequency customers (one
  placed 59 orders) — see `analytics/charts/customer_frequency.png`.
- **Caveat:** this repeat-purchase rate is a direct, expected consequence
  of the synthetic data generator's deliberately skewed (lognormal)
  purchase-propensity design (documented in `data_generator/config.py`), not
  a discovered fact about real customer loyalty. It demonstrates the
  *query/metric is correct*, not that a real business retains 62% of
  customers.

## 6. City performance

| City | Orders | Cancellation rate | Completion rate |
|---|---|---|---|
| Austin | 21,878 | 8.12% | 90.27% |
| Chicago | 19,928 | 7.76% | 90.44% |
| Denver | 18,025 | 8.42% | 90.03% |
| Miami | 16,377 | 7.89% | 90.43% |
| Portland | 12,065 | 7.88% | 90.36% |
| Seattle | 11,727 | 8.19% | 90.25% |

- Cancellation and completion rates are **tight across every city**
  (cancellation: 7.76%-8.42%) — this dataset shows no city with a distinct
  cancellation problem.
- **Rider supply is not proportional to order volume**: Miami (82.7
  orders per active rider) and Portland (79.4) are markedly more
  rider-constrained than Austin (42.1) or Seattle (40.4) —
  `analytics/sql/README.md` query 18. This is a genuine, actionable finding
  (though it is also, transparently, a designed characteristic of the
  synthetic data generator — see below).

## 7. Operational bottlenecks

- Demand peaks sharply at **dinner (18-20h, ~8,300-10,500 orders/hour
  across the 90 days) and lunch (12-13h, ~8,200-8,900)** —
  `analytics/charts/peak_hours.png`.
- Within the order lifecycle, the two slowest stages are **kitchen
  preparation (~13.9 min average)** and **rider transit
  (~26.3 min average)** — `analytics/sql/README.md` query 16. Rider transit
  alone accounts for over half of total delivery time.
- Combining these two findings: the **highest-risk operational window is
  dinner service in Miami and Portland specifically** — the two cities
  already shown to be rider-constrained (finding #6), during the two hours
  each day when demand and rider transit time both peak simultaneously.

**Recommendation:** if this were a real operations decision, the evidence
here points to **prioritizing rider hiring in Miami and Portland ahead of
the other four cities**, and to **investigating kitchen-prep time
specifically** (not just rider availability) as a second lever, since it is
the second-largest contributor to total delivery time after transit.

## Important caveats on every finding above

1. **This is synthetic data**, generated to have realistic *shape* (demand
   curves, skewed purchase behavior, city-based rider imbalance) by design —
   several "findings" above (repeat-customer rate, Miami/Portland rider
   shortage) are confirmations that the generator and the analysis both
   behaved as designed, not organic discoveries about a real business.
2. **No SLA in this project is real** — the 45-minute threshold used for
   "late delivery rate" is explicitly illustrative.
3. **Data-quality issues exist in the raw generated data** (duplicates,
   missing values, invalid timestamps/transitions, inconsistent city
   names) — see `data_quality/README.md` for what was actually checked and
   found. The dataset loaded into Postgres and analyzed above already had
   the invalid-timestamp deliveries excluded during load (documented in
   `database/load_generated_dataset.sql`); duplicate order-item/event rows
   and skipped-history-stage rows were **not** removed, since no
   `data_quality`-driven cleaning pipeline reloads the database yet — a
   disclosed limitation, not a hidden one.
