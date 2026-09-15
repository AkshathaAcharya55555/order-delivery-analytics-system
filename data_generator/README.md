# Synthetic Data Generator

Generates a reproducible synthetic dataset for the Order & Delivery
Analytics System: `locations`, `customers`, `riders`, `orders`,
`order_items`, `deliveries`, `order_status_history`, `event_log` — matching
`database/schema.sql`.

## Run

```bash
cd data_generator
python generate_data.py
```

Output CSVs are written to `data_generator/output/` (git-ignored — regenerate
rather than commit; a full default run produces ~112MB across 8 files).

## Configuration

All scale/behavior parameters are CLI flags on top of `config.GeneratorConfig`:

| Flag | Default | Meaning |
|---|---|---|
| `--number-of-customers` | 50,000 | customer / location count (1 location per customer) |
| `--number-of-orders` | 100,000 | order count |
| `--number-of-riders` | 2,000 | rider count |
| `--number-of-days` | 90 | length of the order-generation window, ending at a fixed `end_date` (2025-06-30) |
| `--random-seed` | 42 | seed for `numpy.random.default_rng` — same seed always produces the same dataset |
| `--cities` | all 6 configured cities | comma-separated subset, e.g. `--cities Austin,Denver` |
| `--output-dir` | `output` | where CSVs are written |
| `--no-quality-issues` | off | disable the 5 data-quality issue injections below |
| `--quality-issue-rate` | 0.02 | base injection rate per issue type |

## Design decisions (read before treating any number as "real")

- **1 location per customer.** Real systems support multiple saved
  addresses; this generator doesn't, to keep the model simple.
  `default_location_id == customer_id` by construction.
- **Demand pattern, cancellation rates, stage durations, rider-city
  distribution, and city order-volume weights are all configured
  assumptions** (see `config.py`), chosen to make the dataset behave
  realistically — not measured facts about any real business.
- **Riders are intentionally distributed across cities differently than
  order volume** (`RIDER_CITY_WEIGHTS` vs city order weights in `config.py`),
  so a later "is rider supply sufficient?" analysis has a real signal to find.
- **A window of the most recent orders (last 6 hours before `end_date`) is
  left in-progress** rather than resolved, simulating a live operational
  snapshot rather than a fully closed-out history.
- **`order_status_history` is the source-of-truth lifecycle log; `orders.status`
  is a separate, sometimes-corrupted field** (see below) — this mirrors a
  real system where a service's cached status field can drift from its own
  audit log.

## Injected data-quality issues

Enabled by default (`--no-quality-issues` turns them off). Each is a
distinct, realistic failure mode, applied independently:

| Issue | Where | What it simulates |
|---|---|---|
| Duplicate rows | `order_items`, `event_log` | an item scanned twice / an at-least-once event delivery replay |
| Missing values | `customers.phone`, `riders.rating`, `locations.postal_code` | incomplete data entry |
| Invalid timestamps | `deliveries.delivered_at` set before `picked_up_at` | clock-sync / late-arriving-event bug |
| Invalid status transitions | `orders.status` mismatched vs. its own history; a middle stage dropped from `order_status_history` | service/log replication drift; a lost status-change event |
| Inconsistent city names | `locations.city` (case, whitespace, abbreviation, state-suffix variants) | free-text entry inconsistency |

## Validate

```bash
python validate_data.py output
```

Re-reads the CSVs from disk (does not trust the generator's own run summary)
and checks: row counts, surrogate-key uniqueness, foreign-key integrity,
timestamp consistency, and status consistency. Writes
`output/validation_report.md`. Some violations are *expected* — they're the
issues deliberately injected above — and are labeled as such in the report.

## Last actual run (50,000 customers / 100,000 orders / 2,000 riders / seed 42)

Row counts produced: 50,000 locations, 50,000 customers, 2,000 riders,
100,000 orders, 254,709 order_items, 93,099 deliveries, 579,318
order_status_history rows, 592,842 event_log rows. Generation took ~33
seconds; validation took ~75 seconds. Full detail in
`output/validation_report.md` after running the commands above — that file
is regenerated each run and is not committed to git.
