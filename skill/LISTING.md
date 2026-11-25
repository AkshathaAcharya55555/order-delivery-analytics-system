# Agensi listing copy: order-delivery-analytics

Paste these fields into the Agensi creator dashboard. Upload:
`skill/dist/order-delivery-analytics.zip`. Rebuild it first with
`python skill/build_zip.py`.

---

## Title
Order & Delivery Analytics: Data-Quality Audit + Ops KPI Report

## Price
**$15 one-time.** Agensi's own pricing guides put comprehensive skills with
scripts and reference files at $12–25.

## Short description (card blurb)
Point your agent at any order and delivery data, CSV or SQL, and get a
14-rule data-quality audit plus an executive KPI report: SLA breach, p50/p90
delivery times, rider leaderboards, supply vs demand and written
recommendations. It works with your column names, not ours.

## Full description

**Why are our deliveries late, and can we trust the numbers?**
This skill answers both in about five minutes, on your own data.

Your agent profiles your tables (CSV exports, Postgres, MySQL, SQLite,
Snowflake or anything SQLAlchemy can read). It auto-maps your columns to a
canonical order/delivery model (`driver_id` → rider, `dropoff_at` →
delivered, `completed` → delivered outcome) and produces two reports:

**1. Data-quality audit (`dq_report.md`)**: 14 rules, with a health score,
failure counts, sample offending IDs and a concrete fix for each:
- Duplicate and missing keys, orphan records across six relationships
- Delivery timestamps out of order (clock skew), implausible durations
- Order status that disagrees with its own status history (lost events)
- Delivered orders with no rider, unmapped status values
- City/zone spelling variants (`AUSTIN`, `Austin, TX`, `Aus.`)
- Duplicate events from at-least-once delivery (Kafka, SQS, webhooks)
- Order totals that don't match their line items
- Exit codes make it usable as a CI gate (`--fail-on HIGH`)

**2. Executive KPI report (`kpi_report.md` + JSON)**: it opens with
auto-written key findings, then covers:
- GMV, AOV, delivered/cancelled/failed mix
- p50/p90/p99 delivery time, SLA breach by city and by week, last-mile time
- City scorecard with orders per active rider (spots under-supplied cities)
- Hour-of-day demand and a day × hour heatmap
- Top and bottom riders (on-time and throughput score, minimum-sample protected)
- Repeat rate, order-frequency distribution, top-10% customer share
- Stage-by-stage order funnel, abnormally long deliveries

Then your agent reads a bundled **interpretation playbook** and writes the
summary: verdict, findings, data-trust caveats and ranked recommendations.
For example: "Miami breaches the 45-min SLA on 58% of deliveries vs 10% in
Denver, and it is one of the two cities carrying the most orders per rider.
Add peak-hour riders there first."

**Also included**
- **Demo mode**: generates a realistic 20k-order dataset with known injected
  defects, so you can watch the audit catch each one exactly.
- **20 commented PostgreSQL KPI queries** for dbt, BI tools or scheduled jobs.
- **Build mode blueprint** for event-driven order/delivery backends: state
  machine, event envelope, idempotent Kafka consumers, transactional outbox,
  N+1-free rider matching, Redis cache-aside with safe timeouts, a nine-table
  schema with integrity constraints, and a Postgres + Kafka + Redis
  docker-compose file.

**Safe by design**: read-only against your data, no network calls, no
credentials in files (the DB URL comes from an environment variable), and
reports contain IDs and aggregates only, with no customer PII.

**Who it's for**: ops and analytics people at food delivery, quick commerce,
courier, 3PL and dark-store businesses. Also data engineers building order
pipelines, and developers building a delivery app who want the backend
patterns right the first time.

**Requirements**: Python 3.9+, pandas and numpy. For databases, also
sqlalchemy plus your driver.

**Works with**: Claude Code, Codex, Cursor and any agent that supports SKILL.md.

## Tags
data-analytics, data-quality, logistics, delivery, sql, postgres, kpi, reporting, python, kafka

## Category
Data & Analytics

## Trigger phrases (already in the SKILL.md description)
"analyse our delivery data" · "why are deliveries late" · "audit order data quality" ·
"build a delivery KPI report" · "rider performance" · "design an order and delivery backend with Kafka"

---

## Promotion checklist (after approval)
- [ ] Post a 30–60 s screen recording: demo data → audit → report → agent summary.
- [ ] Link the listing from the GitHub repo README.
- [ ] Write a short post on how one city's SLA breach turned out to be a
      pre-pickup problem, using demo-mode numbers, with a link to the listing.
- [ ] Reply to reviews; ship fixes as versioned updates (each update is reviewed again).
