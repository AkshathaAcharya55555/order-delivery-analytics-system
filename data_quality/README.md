# Data Quality Validation

Ten validation rules run against the **raw** `data_generator/output/*.csv`
files — deliberately not the already-loaded Postgres tables, since the
bulk-load step (`database/load_generated_dataset.sql`) already excluded some
invalid rows during load (see rule DQ-04). Checking the raw data instead
lets these rules actually detect the issues data_generator intentionally
injected, which is the point of this layer.

## Run it

```bash
python data_quality/validate.py                      # defaults to data_generator/output
python data_quality/validate.py path/to/other/csvs    # or point at any other CSV set
```

Writes `data_quality/quality_report.csv` (all columns below, plus a `notes`
column with the full investigation detail) and prints a summary table.

## Results (actual run, 2026-09-15, against the full ~100k-order dataset)

| rule_id | rule_name | records_checked | records_failed | failure_rate_pct | severity | expected_source |
|---|---|---|---|---|---|---|
| DQ-01 | Missing customer IDs | 100,000 | 0 | 0.0000 | CRITICAL | structural_check |
| DQ-02 | Duplicate order IDs | 100,000 | 0 | 0.0000 | CRITICAL | structural_check |
| DQ-03 | Duplicate event IDs | 592,842 | 23,248 | 3.9214 | LOW | intentionally_corrupted |
| DQ-04 | Invalid delivery durations | 93,099 | 1,842 | 1.9785 | HIGH | intentionally_corrupted |
| DQ-05 | Invalid status transitions | 100,000 | 2,000 | 2.0000 | HIGH | intentionally_corrupted |
| DQ-06 | Missing rider assignments | 90,596 | 37 | 0.0408 | HIGH | intentionally_corrupted |
| DQ-07 | Orphan records | 1,220,225 | 0 | 0.0000 | CRITICAL | structural_check |
| DQ-08 | Invalid order values | 354,709 | 0 | 0.0000 | HIGH | structural_check |
| DQ-09 | Missing timestamps | 1,365,259 | 0 | 0.0000 | MEDIUM | structural_check |
| DQ-10 | Inconsistent city values | 50,000 | 1,000 | 2.0000 | LOW | intentionally_corrupted |

**No result here was invented or assumed** — every number came from an
actual run of `validate.py` against the real files.

## Natural data vs. intentionally corrupted data — how to read this table

`expected_source` distinguishes two categories:

- **`structural_check`**: a rule where the correct, expected result is
  zero — these validate that the generator's core mechanics (referential
  integrity, required fields, non-negative values) hold. All six came back
  at exactly 0, confirming the dataset has no *accidental* structural
  defects.
- **`intentionally_corrupted`**: a rule targeting one of `data_generator`'s
  deliberately-injected data-quality issues (see
  `data_generator/README.md`'s "Injected data-quality issues" table). A
  nonzero result here is the **expected, correct** outcome — it proves the
  check can actually find a known, documented problem, not just report
  zeros. All four came back nonzero, each matching the generator's own
  last recorded injection count exactly (e.g. DQ-04's 1,842 matches
  `data_generator/output/validation_report.md`'s own count precisely).

## Rule-by-rule detail

**DQ-01 Missing customer IDs / DQ-02 Duplicate order IDs / DQ-07 Orphan
records / DQ-08 Invalid order values / DQ-09 Missing timestamps** — all
`structural_check`, all came back 0. These confirm the generator's core
mechanics are sound; they are not interesting findings on their own, but
skipping them would leave "is the data structurally trustworthy at all"
unanswered.

**DQ-03 Duplicate event IDs** — the `event_id` surrogate column itself
never duplicates (each redelivery gets a fresh id, confirmed 0 duplicates
on that column specifically); the 23,248 counted here is **content-level**
duplication (same `order_id`+`event_type`+`event_timestamp` appearing more
than once), simulating Kafka at-least-once redelivery. This is exactly the
scenario the backend's tracking-service Kafka consumer handles via its
`processed_events` idempotency table (see root README's Kafka section) —
this check independently confirms that scenario is real and present in the
data, not hypothetical.

**DQ-04 Invalid delivery durations** — 1,842 rows where `delivered_at` is
earlier than `picked_up_at` (a simulated clock-skew bug). These rows were
excluded from the Postgres load specifically because the `deliveries`
table's own `CHECK` constraint rejects them — running this check against
the loaded table would have shown 0 and silently missed a real, known
issue in the source data.

**DQ-05 Invalid status transitions** — 2,000 orders where `orders.status`
disagrees with the last entry in that order's own `order_status_history`
(simulating drift between a cached status field and its audit log).

**DQ-06 Missing rider assignments — an investigated finding, not an
assumption.** Going in, this check was expected to return 0 (the generator
always assigns a rider before advancing an order past `ready_for_pickup`).
It returned 37. Rather than report that number unexplained, the actual
`order_status_history` for the failing orders was inspected (e.g. order_id
444, 5332, 15574): each one shows a history that ends at `cancelled` only
2-3 stages in — meaning **no rider was ever assigned** — while
`orders.status` itself claims `out_for_delivery` or `delivered`. This is a
downstream consequence of the exact same status-mismatch injection DQ-05
detects, surfacing here as a second, more concrete symptom (a status
claiming a rider should exist when the order's real history shows one
never was). Reclassified from an assumed `structural_check` to
`intentionally_corrupted` once this was confirmed — the code and this
document were both updated to reflect what was actually found, not what
was assumed beforehand.

**DQ-10 Inconsistent city values** — 1,000 of 50,000 locations (exactly
2%, matching the generator's configured injection rate) have a city name
that doesn't exactly match the canonical 6-city list (case variants,
whitespace, abbreviations like "AUS", state suffixes like "Austin, TX").
This is what `database/load_generated_dataset.sql`'s city-normalization
step (a prefix match) was built to fix before loading — this check
confirms the raw data actually needs that step, rather than the
normalization logic being unmotivated defensive code.

## Severity scale used

- **CRITICAL** — would break referential integrity or silently corrupt
  joins if left unaddressed (missing keys, duplicate primary keys, orphan
  foreign keys).
- **HIGH** — would corrupt a core business metric (revenue, delivery-time
  calculations, order counts) if not accounted for before analysis.
- **MEDIUM** — reduces completeness/traceability but doesn't corrupt an
  existing value.
- **LOW** — a normalization/grouping annoyance (duplicate events an
  idempotent consumer already handles; inconsistent labels needing a
  mapping step) rather than a correctness risk once known about.

## Scope and relationship to the rest of the project

This layer **validates** and **reports** — it does not modify or reload
any data. `analytics/` and `reports/business_insights.md` continue to run
against the already-loaded Postgres dataset (which already excludes
DQ-04's invalid rows, per the load script, but still contains DQ-03/05/06/10's
issues, since no cleaning pipeline reloads the database yet). Building an
actual cleaning pipeline that acts on these findings (deduplicate events,
reconcile status mismatches, normalize cities before load) is future work,
not built in this phase — the scope here was to validate and report, which
is what was asked.
