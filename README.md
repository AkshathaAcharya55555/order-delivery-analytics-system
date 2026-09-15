# Scalable Order & Delivery Analytics System

**An independent portfolio project.** This is not a copy or re-implementation
of any specific company's proprietary system, it has never been deployed to
any cloud provider, and it has never run at production scale or against
real users or real business data. Every number in this README and in
`docs/` is either a fact about the schema/code or the literal output of an
actual run — nothing is estimated, projected, or invented. Where something
was not tested or measured, this document says so explicitly rather than
omitting it.

## Table of contents

1. [Project overview](#1-project-overview)
2. [Business problem](#2-business-problem)
3. [Architecture](#3-architecture)
4. [Tech stack](#4-tech-stack)
5. [Data flow](#5-data-flow)
6. [Database design](#6-database-design)
7. [Kafka](#7-kafka)
8. [Redis](#8-redis)
9. [SQL analytics](#9-sql-analytics)
10. [Python analytics](#10-python-analytics)
11. [Data quality](#11-data-quality)
12. [Dashboard](#12-dashboard)
13. [Business insights](#13-business-insights)
14. [Setup](#14-setup)
15. [Testing](#15-testing)
16. [Limitations](#16-limitations)
17. [Future improvements](#17-future-improvements)

---

## 1. Project overview

A simulated food-delivery / logistics platform, built end to end to
demonstrate the skills an Associate Data Analyst role expects: relational
database design, SQL analysis, Python/pandas analysis, data-quality
validation, and dashboard/BI work — sitting on top of a real (if
intentionally simple) event-driven backend rather than a static CSV, so the
analytics layers have a genuine, if synthetic, operational system to
analyze.

**What actually exists:** a 9-table normalized PostgreSQL schema; three
independent Spring Boot REST services (order, delivery, tracking)
integrated over Kafka with Redis caching; a configurable synthetic data
generator; 10 automated data-quality checks; 20 SQL analytics queries; a
Python/pandas EDA layer with an executed notebook; a 6-page Streamlit
dashboard; Docker Compose containerization of the whole stack; and 122
automated tests plus recorded (not estimated) performance measurements.
Full repository structure:

```
order-delivery-analytics-system/
├── README.md, .gitignore, .dockerignore, .env.example
├── docker-compose.yml        # Postgres + Kafka (KRaft) + Redis + all 3 services + dashboard
├── architecture/             # architecture.md — system diagram and design rationale
├── order-service/            # REST API: orders, validation, cancellation + Dockerfile
├── delivery-service/         # REST API: riders, rider-matching, delivery status + Dockerfile
├── tracking-service/         # REST API: status history, transition validation + Dockerfile
├── database/                 # schema, indexes, views, seed data, bulk-load scripts
├── data_generator/           # synthetic dataset generator + validation
├── analytics/
│   ├── sql/                  # 20 analytical queries + README
│   ├── notebooks/            # executed EDA notebook
│   ├── scripts/               # db/queries/metrics/charts modules + run_eda.py
│   └── charts/                # PNG output of the last real run
├── data_quality/             # 10 validation rules + README
├── dashboard/                # Streamlit app (6 pages) + Dockerfile
├── reports/                  # business_insights.md
├── tests/                    # pytest (db constraints, data quality, SQL, performance)
└── docs/                     # API.md, DATABASE.md, ANALYTICS.md, TESTING.md,
                               # PERFORMANCE.md, INTERVIEW_GUIDE.md, RESUME_ALIGNMENT.md
```

## 2. Business problem

A food-delivery business needs to answer operational and strategic
questions from its own data: Is demand growing or just cyclical? Where are
deliveries slow, and why? Do we have enough riders where the orders
actually are? Which customers come back? Is the raw data itself trustworthy
enough to answer any of that? This project builds a (simulated) system that
can answer all of those questions — generating a realistic dataset with
realistic imperfections, then building the database, the pipeline, and the
analysis on top of it, the same way an analyst would inherit a real
system rather than a clean textbook dataset.

## 3. Architecture

Full diagram, component list, and design rationale are in
[`architecture/architecture.md`](architecture/architecture.md). Summary:
three Spring Boot services share one PostgreSQL database directly (a
documented scope simplification, not textbook microservices), communicate
side effects to each other over Kafka, and cache two specific hot-read
values in Redis with a tested Postgres fallback. The database is also read
directly — no separate copy — by the SQL analytics layer, the Python
analytics layer, and the dashboard. Everything runs locally via Docker
Compose; **no component has been deployed to any cloud provider.**

## 4. Tech stack

| Layer | Technology |
|---|---|
| Database | PostgreSQL 16 |
| Backend services | Java 17, Spring Boot 3.3.4, Maven |
| Messaging | Apache Kafka 3.7.0 (single broker, KRaft mode — no ZooKeeper) |
| Caching | Redis 7 |
| Data generation / analytics | Python 3, pandas, NumPy, matplotlib, SQLAlchemy, psycopg2 |
| Dashboard | Streamlit + Altair |
| Testing | JUnit 5 + Mockito (Java), pytest (Python) |
| Containerization | Docker, Docker Compose |

## 5. Data flow

One full order lifecycle, exactly as implemented (see
`architecture/architecture.md` for the full walkthrough and
`docs/API.md` for every endpoint):

```
POST /api/orders (order-service)
  -> orders + order_items rows, PLACED row in order_status_history,
     Redis order:status cache write-through, ORDER_CREATED published

POST /api/orders/{id}/tracking (tracking-service, repeated)
  -> CONFIRMED -> PREPARING -> READY_FOR_PICKUP, each appended to
     order_status_history, each publishing STATUS_CHANGED

POST /api/deliveries/{orderId}/assign (delivery-service)
  -> queries Postgres for available riders in the order's city, scores them,
     inserts a deliveries row, orders.status -> RIDER_ASSIGNED,
     RIDER_ASSIGNED published

PUT /api/deliveries/{orderId}/status (delivery-service, repeated)
  -> PICKED_UP -> OUT_FOR_DELIVERY -> DELIVERED, each publishing the
     matching event (DELIVERY_STARTED / DELIVERY_COMPLETED)

GET /api/orders/{orderId}/tracking (tracking-service, any time)
  -> current status (Redis cache-aside) + full order_status_history timeline
```

`analytics/sql/`, `analytics/scripts/`, and `dashboard/` all read the same
`orders`/`order_items`/`deliveries`/`order_status_history` tables directly
afterward — there is no ETL step between the transactional tables and the
analytics layer beyond the one-time synthetic-dataset bulk load described
in Section 6.

## 6. Database design

Full table-by-table reference (every column, constraint, and index) is in
[`docs/DATABASE.md`](docs/DATABASE.md). Summary: 9 tables (`locations`,
`customers`, `riders`, `orders`, `order_items`, `deliveries`,
`order_status_history`, `event_log`, `processed_events`), 6 analytical
views, 17 indexes beyond the primary/unique keys. Key design decisions:

- **`order_status_history`** is an append-only log kept separate from
  `orders.status`, specifically so funnel and stage-duration analysis have
  a full timeline to work from, not just a current value.
- **`event_log`** (synthetic-data-only, never written by the live backend)
  and **`processed_events`** (the live Kafka idempotency ledger) are two
  separate tables that are easy to confuse by name — kept apart because
  their `event_id` columns are different types (a DB surrogate vs. a
  producer-assigned UUID).
- **A disclosed inconsistency**: `orders.status` is uppercase, mirroring the
  order-service Java enum; `deliveries.delivery_status` is lowercase,
  mirroring its own enum. Documented rather than silently normalized.

**Data currently loaded**: the full synthetic dataset from `data_generator/`
— 100,000 orders, 50,000 customers, 2,000 riders, 50,000 locations, 91,257
deliveries (1,842 excluded at load time for violating a CHECK constraint —
see `docs/DATABASE.md`), 254,709 order items, 579,318 order-status-history
rows — loaded via `database/staging_schema.sql` + `load_generated_dataset.sql`.
A small number of additional rows (well under 0.1% of the total) exist from
later manual/automated API testing; see Section 15.

## 7. Kafka

Full topic/producer/consumer map, the JSON event envelope, ordering
considerations, and what was and wasn't tested are documented in
`architecture/architecture.md` and inline in each service's code
(`KafkaTopics.java`). Summary:

- **7 topics, one per event type**: `order-created`, `order-cancelled`,
  `rider-assigned`, `delivery-started`, `delivery-completed`,
  `delivery-failed`, `status-changed`.
- **Producers**: order-service (2 topics), delivery-service (4 topics),
  tracking-service (1 topic). **Consumer**: only tracking-service, which
  subscribes to the 6 topics it doesn't itself produce, purely to keep the
  Redis order-status cache coherent when another service changes an
  order's status — it never re-writes `order_status_history`, since the
  service that made the change already wrote that synchronously.
- **Idempotency**: every consumed event is checked against a
  `processed_events` table (`INSERT ... ON CONFLICT (event_id) DO NOTHING`)
  before any side effect runs. **Actually tested**: the same event
  replayed twice against the real running system produced exactly one
  `processed_events` row and a logged `Duplicate event ... skipped` message
  — see `docs/TESTING.md`.
- **Partition key = `order_id`**, so all events for one order stay ordered
  relative to each other even on a single-partition topic.
- **Known limitation**: publish happens as a step after the database
  commit, not inside the same transaction (no outbox pattern) — a crash in
  that narrow window would lose the event even though the DB change stands.
  Not fixed here; see Section 16.

## 8. Redis

Two cache-aside caches, Postgres always the fallback and source of truth:

| Cache | Key | TTL | Purpose |
|---|---|---|---|
| Order status | `order:status:{orderId}` | 10 min | Read by tracking-service's status endpoint |
| Rider availability | `rider:available:{riderId}` | 60 sec | Read by delivery-service's availability endpoint |

Every read/write path wraps the Redis call in try/catch — a read failure
falls through to Postgres, a write failure is logged and swallowed, so no
request ever fails because Redis is down. **Actually tested** two ways: a
unit test pointing a real Redis client at a port nothing listens on, and —
during the Docker end-to-end testing phase — physically stopping the
`oda_redis` container mid-test. The fallback returned the **correct** data
both times; it also took **noticeably longer** (the request stalled well
past a minute in one case) because Redis's client-side reconnect/timeout
behavior isn't tuned for fast failover. That's a real, disclosed limitation
— see Section 16, not a claim that Redis-down performance is fine.
Deliberately **not** cached: the rider-matching query itself, since it
needs true current state at the moment of matching. Full detail in
`architecture/architecture.md`.

## 9. SQL analytics

20 standalone queries in `analytics/sql/`, each answering one specific
business question (daily volume/revenue, cancellation rates by city,
delivery-time median/P90, rider leaderboard and utilization, repeat-
customer rate, peak hours, order funnel, month-over-month growth, and
more), demonstrating JOINs, CTEs, window functions (`RANK`, `LAG`, `LEAD`),
`PERCENTILE_CONT`, and correlated subqueries. All 20 are covered by an
automated test that runs each against the live database and asserts it
executes and returns rows. Full list of business questions, the SQL-
technique cross-reference, and links to the underlying query files are in
[`docs/ANALYTICS.md`](docs/ANALYTICS.md) and
[`analytics/sql/README.md`](analytics/sql/README.md).

## 10. Python analytics

pandas/NumPy/matplotlib/SQLAlchemy analysis of the same database
(`analytics/scripts/`), plus an **executed** Jupyter notebook
(`analytics/notebooks/eda_analysis.ipynb`, 28 cells, confirmed zero error
cells) that narrates the same analysis with inline charts. Covers order
trends, delivery-time distribution (mean/median/P90/skewness), rider
utilization, customer repeat behavior, city performance, and operational
bottlenecks. Every pandas/NumPy result was cross-checked against the
equivalent SQL query and agreed within rounding. Full metric formulas and
the "why SQL here, pandas there" reasoning are in
[`docs/ANALYTICS.md`](docs/ANALYTICS.md) and
[`analytics/README.md`](analytics/README.md).

## 11. Data quality

10 automated rules (`data_quality/validate.py`) run against the **raw**
generated CSVs — missing required fields, duplicate records, invalid value
ranges, orphaned foreign keys, status/history mismatches, and inconsistent
city-name formatting — each labeled as an expected-zero structural check or
an expected-nonzero check against a deliberately injected test issue, with
severity ratings and a documented distinction between the two. One result
came back unexpectedly nonzero; rather than report it unexplained, specific
records were traced back through their own history and the real root cause
(a downstream effect of a different, already-known injected issue) was
identified and written up. All 10 rule functions also have unit tests (24
tests) against hand-built clean/dirty fixtures, independent of the full CSV
run. Full results table and the investigation are in
[`docs/ANALYTICS.md`](docs/ANALYTICS.md) and
[`data_quality/README.md`](data_quality/README.md).

## 12. Dashboard

A 6-page Streamlit app (Executive Overview, Order Trends, Delivery
Performance, Rider Performance, Customer Analytics, Data Quality) with
sidebar date/city/order-status filters. Every KPI and chart is computed
live from PostgreSQL (the Data Quality page reads
`data_quality/quality_report.csv`) using the same metric formulas as the
Python analytics layer, imported directly rather than reimplemented — so
its numbers match the business-insights figures below exactly when filters
aren't narrowing the data. Tested end to end with Streamlit's `AppTest`
framework (all 6 pages, zero exceptions) and by exercising the filters
interactively. Full detail in [`dashboard/README.md`](dashboard/README.md).

## 13. Business insights

Findings from an actual run of the SQL and Python analytics layers against
the full loaded dataset (100,000 orders, 90-day window, 6 cities, 2,000
riders, 50,000 customers):

- 90.30% completed, 8.04% cancelled, 1.66% still in progress
- A clear weekly demand cycle (Friday/Saturday peaks vs. a lower weekday
  baseline) — no growth or decline trend across the 90-day window
- Average order value $26.16 (median $23.50)
- Average delivery time 49.33 minutes (median 48.48, P90 67.07)
- 61.66% repeat-customer rate
- Tight cancellation/completion rates across all 6 cities, but rider supply
  is not proportional to demand — Miami and Portland have markedly more
  orders per active rider than Austin or Seattle
- Demand peaks at dinner (18-20h) and lunch (12-13h); rider transit and
  kitchen prep are the two slowest lifecycle stages

**Every figure above carries an explicit caveat in the source report**:
this is synthetic data with a deliberately designed shape (the repeat-
customer rate and the Miami/Portland rider gap are confirmations that the
generator and analysis behaved as designed, not organic discoveries about a
real business), the 45-minute "SLA" used for a late-delivery rate is an
illustrative assumption with no real business approval behind it (and sits
below the actual median delivery time, which is most of why the resulting
rate looks high), and the dataset has since gained a small number of
non-representative test orders (see Section 15). Full write-up with every
caveat in [`reports/business_insights.md`](reports/business_insights.md).

## 14. Setup

**Requirements**: Docker (for Postgres/Kafka/Redis, and optionally the
services and dashboard too); Python 3 with `pandas`, `numpy`, `matplotlib`,
`sqlalchemy`, `psycopg2-binary`, `streamlit` if running those outside
Docker; Java 17+ and Maven if running the services outside Docker (each
includes a Maven Wrapper).

**Fastest path — the whole system in one command:**
```bash
cp .env.example .env   # optional — same values are the compose file's defaults
docker compose up -d --build
```
Builds and starts all 7 containers (Postgres, Kafka, Redis, all 3 services,
dashboard) with health-checked startup ordering. Ports: 8081/8082/8083 for
the services, 8501 for the dashboard, 5432/9092/6379 for the infra — same
whether run in Docker or directly on the host. On a brand-new Postgres
volume, schema/indexes/views/seed data are applied automatically; the full
100k-order dataset load is the separate step below. **Cold-start note**: an
unoptimized Spring Boot image can take 100-200+ seconds to become healthy
under host load — this was measured directly (see `docs/PERFORMANCE.md`),
not assumed, and the healthcheck timing is set accordingly.

**Running components individually:**
```bash
# Database only
docker compose up -d
docker exec -i oda_postgres psql -U oda_user -d oda_db < database/schema.sql
docker exec -i oda_postgres psql -U oda_user -d oda_db < database/indexes.sql
docker exec -i oda_postgres psql -U oda_user -d oda_db < database/views.sql

# Synthetic data generator
cd data_generator && python generate_data.py && python validate_data.py output

# Load the full generated dataset into Postgres
docker exec -i oda_postgres psql -U oda_user -d oda_db < database/staging_schema.sql
# then \copy each data_generator/output/*.csv into its staging table (see analytics/sql/README.md)
docker exec -i oda_postgres psql -U oda_user -d oda_db < database/load_generated_dataset.sql

# Backend services on the host instead of Docker
cd order-service && mvn spring-boot:run      # :8081
cd delivery-service && mvn spring-boot:run   # :8082
cd tracking-service && mvn spring-boot:run   # :8083

# Python analytics
pip install pandas numpy matplotlib sqlalchemy psycopg2-binary
python analytics/scripts/run_eda.py

# Data-quality validation
python data_quality/validate.py

# Dashboard
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

Full REST API reference (every endpoint, request/response body, and
validation rule): [`docs/API.md`](docs/API.md).

## 15. Testing

122 automated tests, 0 failures on the most recent full run: 23 tests in
order-service, 23 in delivery-service, 12 in tracking-service (all JUnit 5
via `mvn test`), and 64 in `tests/` (pytest — 19 database-constraint tests,
24 data-quality-rule tests, 21 SQL-query tests). The full end-to-end order
→ Kafka → rider assignment → delivery → tracking → analytics → dashboard
flow was also run manually against the live containerized system, along
with cancellation, invalid-status-transition, duplicate-Kafka-event,
unavailable-rider, Redis-outage, and invalid-order-data edge cases.

Two real, investigated findings came out of this testing (not fabricated,
both root-caused and either fixed or documented):
- Two pre-existing tests were failing because they assumed a near-empty
  database; the shared database now also holds the full synthetic dataset.
  Both were fixed (documented in `docs/TESTING.md`), not silently ignored.
- Running `mvn test` while the full Docker Compose stack is also connected
  to the same Kafka broker causes intermittent test timeouts — traced to
  broker contention, confirmed by isolation, documented as an environment
  limitation rather than a code defect.

Real, recorded (not estimated) performance measurements — API response
time, database query execution time, 20 concurrent order creations, and
Kafka event-processing latency — are in
[`docs/PERFORMANCE.md`](docs/PERFORMANCE.md), each with its exact
configuration and environment. Full test inventory, coverage mapping, and
results: [`docs/TESTING.md`](docs/TESTING.md).

## 16. Limitations

Stated directly, not softened:

- **Not production scale.** ~100,000 orders in a single Postgres instance
  is enough to make the analytics layer meaningful, not enough to prove
  anything about real production load.
- **Not deployed anywhere.** Runs locally via Docker Compose only. No AWS,
  no other cloud provider, no CI/CD pipeline.
- **No authentication/authorization** on any REST endpoint.
- **Shared database across services**, not per-service data ownership —
  documented in Section 3/Section 6 as a scope decision.
- **No transactional outbox** for Kafka publishing — a narrow crash window
  between a DB commit and its event publish would lose that event.
- **Rider-matching has an N+1 query pattern**: it issues one database
  query per candidate rider to compute current workload. Invisible with a
  handful of candidates; with 313 real riders in one city, a single
  assignment call took several minutes in the containerized environment
  during testing. Found and documented, not fixed.
- **Redis-outage fallback is correct but slow**: verified to return the
  right data with Redis down, but the client's reconnect/timeout behavior
  is not tuned for fast failover — one measured case stalled well over a
  minute. Found and documented, not fixed.
- **The 45-minute delivery SLA used in analytics is illustrative**, not a
  real, approved business target — no such target exists for this project.
- **The loaded dataset has a small amount of test-created data mixed in**
  (well under 0.1% of total rows) from manual/automated API and
  performance testing after the original analytics run — see Section 15.
- **No load/stress testing** — the performance checks in
  `docs/PERFORMANCE.md` are small, single-run measurements, not a
  benchmark suite.

## 17. Future improvements

Concrete, scoped to what this project's own findings actually point to
(not a generic wishlist):

- Fix the rider-matching N+1 query by computing all candidates' current
  workload in one batched query instead of one query per candidate.
- Add an explicit, short command timeout to the Redis client so an outage
  degrades to the Postgres fallback quickly rather than eventually.
- Add a transactional outbox table for Kafka publishing so a DB commit and
  its event publish either both happen or neither does.
- Split each service onto its own database (true per-service data
  ownership) instead of the current shared-database simplification.
- Add authentication/authorization to the REST APIs.
- Regenerate the synthetic dataset without the small amount of test-order
  contamination described in Section 16, or add a `source` column to
  distinguish generated from manually-created rows.
- A real (not hypothetical) cloud deployment — see `docs/INTERVIEW_GUIDE.md`'s
  "How would you deploy to AWS?" answer for the specific, unimplemented
  plan (RDS, MSK, ElastiCache, ECS Fargate) this would follow.
- Multi-partition Kafka topics and multiple broker replicas, and read
  replicas for the analytics/dashboard query load, if this were ever to
  run at real scale.

---

## Further reading

- [`architecture/architecture.md`](architecture/architecture.md) — full system diagram and design rationale
- [`docs/API.md`](docs/API.md) — complete REST API reference
- [`docs/DATABASE.md`](docs/DATABASE.md) — every table, column, constraint, and index
- [`docs/ANALYTICS.md`](docs/ANALYTICS.md) — SQL + Python analytics + data quality, consolidated
- [`docs/TESTING.md`](docs/TESTING.md) — full test inventory and results
- [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) — every performance measurement actually taken
- [`docs/INTERVIEW_GUIDE.md`](docs/INTERVIEW_GUIDE.md) — prepared interview answers grounded in this project
- [`docs/RESUME_ALIGNMENT.md`](docs/RESUME_ALIGNMENT.md) — resume bullets for an Associate Data Analyst role
