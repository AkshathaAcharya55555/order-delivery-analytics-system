---
name: order-delivery-analytics
description: Audits and analyses order and delivery data from food delivery, quick-commerce, courier or logistics operations, from CSV files or any SQL database. It produces a 14-rule data-quality audit and an executive KPI report with SLA breach, p50/p90 delivery times, rider leaderboards, supply vs demand, funnel and retention, plus written recommendations. Use it when the user says "analyse our delivery data", "why are deliveries late", "audit order data quality", "build a delivery KPI dashboard or report", "rider performance", or "design an order and delivery backend with Kafka".
---

# Order & Delivery Analytics

Turns raw order and delivery data, under any naming scheme, into two trustworthy
deliverables:

1. **`dq_report.md`**: a 14-rule data-quality audit with a health score, failure
   counts, sample offending IDs and the fix for each issue.
2. **`kpi_report.md`**: an executive performance report. It opens with
   auto-generated key findings, then covers headline KPIs, a city scorecard,
   trends, a peak-hour heatmap, top and bottom riders, customers, the funnel
   and anomalies.

It also contains a production-grade blueprint for **building** an
event-driven order and delivery backend (see Build mode).

Requirements: Python 3.9+ with `pandas` and `numpy`. For databases, also
`sqlalchemy` plus a driver such as `psycopg2-binary` or `pymysql`. The scripts
only read. They never write to or modify the user's data source.

## Choose the mode

| User intent | Mode |
|---|---|
| Has data (CSV export, Postgres/MySQL/warehouse) and wants insight, a health check or a report | **Analyse** |
| Wants to see what the skill does, or has no data yet | **Demo** |
| Wants to design or build an order, delivery, dispatch or tracking backend | **Build** |

`SKILL_DIR` below means the folder that contains this file.

---

## Analyse mode

### Step 1: Locate the data

Ask only what you cannot discover: where the data is (a folder of CSVs, or a
DB connection in an environment variable) and the **delivery SLA in minutes**.
If the user has no SLA, use 45 and say clearly that it is a placeholder.
Never ask for, echo, or write database passwords into files. Connection
strings must stay in an environment variable (default `DATABASE_URL`).

### Step 2: Profile and draft the mapping

```bash
python "$SKILL_DIR/scripts/profile_source.py" --csv-dir ./exports --out mapping.json
# or
python "$SKILL_DIR/scripts/profile_source.py" --sql --url-env DATABASE_URL --out mapping.json
```

The profiler prints every table's columns, types, null rates and samples. It
then guesses which table is orders, deliveries, riders and so on, maps
columns using a large synonym list (`driver_id` → `rider_id`, `dropoff_at` →
`delivered_at`, and others), and buckets status values into outcomes.

### Step 3: Review the mapping (do not skip)

Open `mapping.json` and check everything listed under **"Needs review"**:

- Each `medium` or `low` confidence column: confirm it against the sample values.
- `status_map`: every raw status must sit in the right bucket. Ask the user
  about any ambiguous value, such as `returned`, `rto` or `partially_delivered`.
- A missing `city`: look for an address, zone or store table and add a `join`.
  For SQL sources, a `{"query": ...}` source also works.
- Set `settings.sla_minutes`. When order totals include tax or fees, add
  `"skip_rules": ["DQ-14"]`.

The full format is in `references/mapping-spec.md`. Read it when editing anything
beyond simple column names.

### Step 4: Run the audit, then the KPIs

```bash
python "$SKILL_DIR/scripts/dq_audit.py"   --mapping mapping.json --out dq_report.md --json dq_report.json
python "$SKILL_DIR/scripts/kpi_report.py" --mapping mapping.json --out kpi_report.md --json kpis.json
```

- `dq_audit.py` exits with 1 when a CRITICAL rule fails. That is a finding, not
  a crash. Use `--fail-on HIGH` to make it a CI gate.
- `kpi_report.py --since 2026-05-01 --until 2026-05-31` restricts the period.
- Exit code 2 means a mapping problem. The message names the missing column
  and lists the available ones. Fix the mapping and re-run.

### Step 5: Interpret and deliver

Read **both** reports, then `references/interpreting-results.md`, and write the
user a summary in this order: verdict, key findings with numbers, data-trust
caveats, ranked recommendations, next analyses.

Rules:
- Quote numbers exactly as the reports give them.
- Data-quality issues come before KPI conclusions when they affect them.
  Delivery times already exclude invalid rows, and the report shows how many.
- Present causes as hypotheses with the check that would confirm them, unless
  the data proves them.
- Point the user to the two `.md` reports (and the JSON files, if they want
  a dashboard or a BI feed).

For in-warehouse or dbt versions of the KPIs, adapt the 20 SQL queries in
`references/sql/` (see its README for the column translation).

---

## Demo mode

```bash
python "$SKILL_DIR/scripts/generate_demo_data.py" --out ./demo_data      # 20k orders, ~3 s
python "$SKILL_DIR/scripts/dq_audit.py"   --mapping ./demo_data/mapping.json --out demo_dq.md
python "$SKILL_DIR/scripts/kpi_report.py" --mapping ./demo_data/mapping.json --out demo_kpi.md
```

This generates a realistic synthetic dataset: six cities, lunch and dinner
peaks, under-supplied cities, a rider skill spread and loyal customers. It
injects known defects and prints how many it injected, so you can show the
audit catching each one exactly. Options: `--orders`, `--days`, `--seed`,
`--no-issues`. The data is synthetic and contains no real people or companies.

---

## Build mode

Read `references/architecture-blueprint.md`. It covers service boundaries, the
order state machine, the event envelope, idempotent consumers, the
transactional outbox, N+1-free rider matching, safe Redis cache-aside, and a
test checklist. Then:

- Start from `assets/schema/schema.sql` (nine tables with integrity CHECKs),
  `indexes.sql` and `views.sql`. Apply them to a **new, empty** database only.
- Start local infrastructure with `assets/docker-compose.infra.yml` (Postgres,
  Kafka in KRaft mode, Redis). It needs `POSTGRES_PASSWORD` set in the
  environment.
- Implement in the user's own language and framework. The patterns are
  stack-agnostic.
- Wire `scripts/dq_audit.py` into CI against the service database so data
  regressions fail the build.

## Guardrails

- Read-only analysis: never run DDL or DML against the user's database while
  analysing.
- Do not paste customer PII (names, emails, phones) into summaries. The
  reports contain only IDs and aggregates.
- If fewer than about 500 orders are in scope, say that percentages and
  percentiles are unstable.
- Do not invent metrics the reports did not compute. Name the missing input
  instead (the reports list these under "Not computed").
