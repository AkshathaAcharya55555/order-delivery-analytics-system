# Interpreting results: from numbers to recommendations

Use this file when writing the executive summary. Each pattern gives what to
check, the likely causes, and what to recommend. Never present a cause as fact
unless the data confirms it. Say "consistent with" and name the check that
would confirm it.

## 0. Trust the data first

Before interpreting any KPI, read `dq_report.md`:

- **Any CRITICAL failure** (missing keys, duplicate orders, orphans): stop and
  report it first. The KPIs are unreliable until it is fixed.
- **DQ-04 / DQ-12** (bad timestamps) bias delivery times. The KPI report already
  excludes those rows and prints how many. Say so whenever you quote a delivery time.
- **DQ-05 / DQ-06** (status drift) distort the outcome mix. Quote the drift rate
  next to the cancellation rate.
- **DQ-10** (spelling variants) is fixed automatically in KPIs (`normalize_city`).
  Still recommend fixing it at the source.
- **DQ-13** (unmapped statuses): add them to `status_map` and re-run. Do not
  interpret outcome rates while `unknown` is above 0.5%.
- A partial first or last month makes month-over-month growth meaningless.
  Compare full months only, or use `--since/--until`.

## 1. Delivery speed and SLA

| Pattern | Likely causes | Check | Recommend |
|---|---|---|---|
| High p90 but normal p50 | A long tail: a few zones, peak hours or slow riders | Anomaly table; breach by hour (re-run with `--since/--until` on peak days) | Fix the tail, not the average. Use zone-level SLAs and surge staffing |
| One city breaches far more than the others | Under-supply, geography, restaurant prep time | City `orders_per_rider` vs breach %; `last_mile_p50` vs total | If last-mile is normal but the total is high, the delay is **before pickup** (kitchen or assignment). If last-mile is high, it is supply or distance |
| Breach worsens week over week | Demand growing faster than the rider pool | Weekly table vs daily volume trend | Hiring plan, or incentives for peak shifts |
| p50 close to the SLA (within 10%) | The SLA is set at the median | Distribution | Either the target is unrealistic or operations are; set the SLA at p80–p90 of a healthy city |

Decompose total time as placed → assigned → picked up → delivered, using the
timestamps available. The stage that grew is where the action is.

## 2. Supply and demand

- `orders_per_rider` far above the average for a city points to under-supply.
  Confirm it correlates with that city's SLA breach before recommending
  hiring. High load with a normal SLA may mean efficient riders, not a shortage.
- Peak-hour concentration: if the top three hours carry more than 25% of
  orders, recommend shift-based staffing over flat staffing.
- Riders who are idle off-peak while orders breach at peak is a scheduling
  problem, not a headcount problem.

## 3. Cancellations and failures

- Early cancellations (before PREPARING) are usually customer-driven: price,
  ETA shown or payment. Late ones (after PREPARING) are operational and expensive,
  because the food is already made.
- Use the funnel to place drop-off between stages. A gap at RIDER_ASSIGNED
  means no rider was found. A gap at PICKED_UP points to restaurant or rider no-shows.
- Failed deliveries above about 1% call for address-quality and
  customer-reachability checks.

## 4. Riders

- Leaderboard score = 60% on-time rank + 40% throughput rank. Riders with fewer
  than `min_rider_deliveries` deliveries are excluded, to avoid small-sample noise.
- Bottom riders concentrated in one city means the problem is the city, not the
  riders. Compare each rider to their own city's median before recommending coaching.
- Never recommend disciplinary action from this data alone. Recommend review.

## 5. Customers

- Repeat rate below 30% (food delivery) means acquisition is leaking. Above 60%
  means a loyal base, so protect it from SLA regressions.
- When the top 10% of customers place more than 35% of orders, that cohort is
  sensitive to churn. Recommend tracking their SLA experience separately.

## 6. Writing the summary

Structure:
1. **One-line verdict**, e.g. "Volume is up 16% but Miami's SLA is failing and
   driving most of the breaches."
2. **Three to five findings**, each with the number, its comparison point and
   why it matters.
3. **Data-trust caveats**: any DQ issue that affects these numbers.
4. **Recommendations**, each tied to a finding, ranked by impact and effort.
5. **Next analyses**: what you would check with more data or time.

Keep the numbers exactly as the scripts produced them. Do not round 26.9% to
"about a quarter" in one place and "27%" in another.
