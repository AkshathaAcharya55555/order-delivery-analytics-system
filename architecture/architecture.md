# Architecture

This document describes the actual, as-built architecture of the Scalable
Order & Delivery Analytics System — an independent portfolio project, not a
production system and not a deployment of any real company's infrastructure.
Every component described here exists in this repository and was actually
built and run; nothing below is aspirational.

## System diagram

```
                         ┌─────────────────────────────────────────┐
                         │              Client / curl               │
                         └───────────────┬───────────────────────────┘
                                          │ REST (JSON)
              ┌───────────────────────────┼───────────────────────────┐
              │                           │                           │
              ▼                           ▼                           ▼
     ┌─────────────────┐        ┌──────────────────┐        ┌────────────────────┐
     │  order-service   │        │ delivery-service  │        │  tracking-service   │
     │  :8081           │        │ :8082             │        │  :8083              │
     │  Spring Boot     │        │ Spring Boot       │        │  Spring Boot        │
     └───┬─────────┬────┘        └────┬─────────┬────┘        └────┬─────────┬─────┘
         │         │                  │         │                  │         │
         │ writes  │ produces         │ writes  │ produces         │ writes  │ produces
         ▼         ▼                  ▼         ▼                  ▼ (all)   ▼
   ┌───────────┐ ┌──────────────────────────────────────────────┐ ┌───────────┐
   │           │ │                  Kafka (KRaft)                │ │           │
   │           │ │  order-created, order-cancelled, rider-assigned,│ │           │
   │           │ │  delivery-started, delivery-completed,          │ │           │
   │           │ │  delivery-failed, status-changed                │ │           │
   │           │ └───────────────────────┬──────────────────────────┘ │           │
   │ PostgreSQL│                         │ consumed by                │  Redis    │
   │  oda_db   │◄────────────────────────┘  tracking-service          │  (cache-  │
   │           │  (idempotent via processed_events)                   │  aside)   │
   └─────┬─────┘                                                      └─────┬─────┘
         │                                                                  │
         │ direct read (SQLAlchemy / psycopg2)                              │
         ▼                                                                  │
   ┌───────────────────────────────┐      ┌──────────────────────────┐      │
   │ analytics/sql/  (20 queries)   │      │ analytics/scripts + notebook │  │
   │ database/views.sql (6 views)   │      │ (pandas/NumPy/matplotlib)   │  │
   └───────────────┬───────────────┘      └─────────────┬────────────┘      │
                   │                                     │                   │
                   └───────────────┬─────────────────────┘                   │
                                   ▼                                         │
                         ┌───────────────────┐                               │
                         │  dashboard/        │◄──────────────────────────────┘
                         │  Streamlit (:8501) │   (order/rider caches read directly
                         └───────────────────┘    by delivery/tracking-service, not
                                                    by the dashboard)

   ┌───────────────────────────┐        ┌──────────────────────────────┐
   │ data_generator/            │        │ data_quality/validate.py       │
   │ synthetic dataset producer │───────▶│ validates the raw CSVs before  │
   │ (CSV output)                │        │ they're loaded into Postgres   │
   └───────────────┬───────────┘        └──────────────────────────────┘
                   │ bulk-loaded via
                   │ database/staging_schema.sql +
                   │ load_generated_dataset.sql
                   ▼
              PostgreSQL oda_db
```

## Components

| Component | What it is | Runs as |
|---|---|---|
| `order-service` | REST API: create/list/fetch/cancel orders | Spring Boot JAR, container, or `mvn spring-boot:run` |
| `delivery-service` | REST API: riders, rider-matching, delivery status | Spring Boot JAR, container, or `mvn spring-boot:run` |
| `tracking-service` | REST API: full order status history + Kafka consumer | Spring Boot JAR, container, or `mvn spring-boot:run` |
| PostgreSQL (`oda_db`) | Single shared relational database, source of truth for all state | Docker container (`postgres:16-alpine`) |
| Kafka | Event bus between the three services (single broker, KRaft mode, no ZooKeeper) | Docker container (`apache/kafka:3.7.0`) |
| Redis | Cache-aside layer for order status and rider availability | Docker container (`redis:7-alpine`) |
| `data_generator/` | Standalone Python script producing a synthetic CSV dataset | Run once, offline, output loaded into Postgres separately |
| `data_quality/` | Standalone Python validation script against the raw CSVs | Run on demand (`python data_quality/validate.py`) |
| `analytics/sql/` | 20 standalone `.sql` files | Run via `psql` or any SQL client against `oda_db` |
| `analytics/scripts/`, `analytics/notebooks/` | Python (pandas/NumPy/matplotlib) analysis of the same database | Run via `python analytics/scripts/run_eda.py` or the Jupyter notebook |
| `dashboard/` | Streamlit web app reading live from `oda_db` | Run via `streamlit run dashboard/app.py` or its own container |

## Why this shape

**Shared database, not per-service databases.** All three backend services
connect directly to the same `oda_db` Postgres instance and map JPA entities
onto the same tables (each service only *writes* to the tables/columns its
own endpoints own). This is a deliberate simplification for a project at
this scale, not an oversight — true microservices would give each service
its own database and communicate exclusively over the network (REST/Kafka),
which would need an API composition or CQRS-style read layer for anything
that spans services (like the tracking history this project's dashboard and
analytics layer read directly from Postgres). That is documented here as a
scope decision, not hidden.

**Kafka connects the three services for cross-service side effects only.**
Every service still writes its own core state (the order/delivery rows,
`order_status_history`) synchronously in its own transaction — Kafka is not
used to replicate that data a second time. The only consumer,
`tracking-service`, uses the events purely to keep the shared Redis
order-status cache coherent when some *other* service changes an order's
status. This keeps "who owns writing `order_status_history`" single and
unambiguous (order-service and delivery-service write it directly; Kafka
consumption never does).

**Redis is cache-aside on top of Postgres, never the source of truth.**
Both caches (`order:status:{id}`, `rider:available:{id}`) are read-through
on miss and write-through on change, with a TTL as a safety net. Every read
path falls back to Postgres and every write path swallows a Redis failure —
the system runs (just slower) with Redis down. This was tested directly
(see the root README's Redis section and `docs/TESTING.md`), not assumed.

**Analytics and the dashboard read Postgres directly — no separate
data-warehouse or ETL layer.** At this project's scale, a live OLTP-style
read from the same database is enough; a real production system with
concurrent write load might separate an analytical replica or warehouse,
which this project does not attempt or claim to need.

**No API gateway, no service discovery, no message-schema registry.** Each
service is reached directly by port; Kafka event schemas are a hand-written
JSON envelope duplicated as a small record/class in each service, not a
shared library or Avro/Protobuf schema registry. These are reasonable
production concerns this project intentionally does not implement, since
doing so would not change what the project is meant to demonstrate (SQL,
data modeling, Python analytics, data quality, and event-driven basics).

## Data flow: one full order lifecycle

1. `POST /api/orders` (order-service) → row inserted into `orders` +
   `order_items`, a `PLACED` row appended to `order_status_history`, the
   Redis `order:status:{id}` key write-through set, and an `ORDER_CREATED`
   event published to the `order-created` Kafka topic.
2. `tracking-service` consumes `ORDER_CREATED` (idempotently — see below)
   and does **not** re-write `order_status_history` (order-service already
   did); it only reacts to events for consistency of anything it alone
   owns.
3. `POST /api/orders/{id}/tracking` (tracking-service, one or more calls)
   advances the order through `CONFIRMED` → `PREPARING` →
   `READY_FOR_PICKUP`, each call validated against a hardcoded legal-
   transition table, each appending to `order_status_history` and
   publishing `STATUS_CHANGED`.
4. `POST /api/deliveries/{orderId}/assign` (delivery-service) queries
   Postgres for available riders in the order's city, scores them with a
   deterministic weighted formula (distance + current workload), inserts a
   `deliveries` row, updates `orders.status` to `RIDER_ASSIGNED`, and
   publishes `RIDER_ASSIGNED`.
5. `PUT /api/deliveries/{orderId}/status` (delivery-service, one or more
   calls) advances the delivery through `PICKED_UP` → `OUT_FOR_DELIVERY` →
   `DELIVERED` (or `FAILED`), each transition validated, each publishing
   the corresponding event (`DELIVERY_STARTED` / `DELIVERY_COMPLETED` /
   `DELIVERY_FAILED`).
6. At any point, `GET /api/orders/{orderId}/tracking` (tracking-service)
   returns the current status (Redis cache-aside, Postgres fallback) and
   the full `order_status_history` timeline.
7. `analytics/sql/`, `analytics/scripts/`, and `dashboard/` all read the
   same `orders` / `order_items` / `deliveries` / `order_status_history`
   tables directly — no separate copy of the data.

This exact flow (order → Kafka → rider assignment → delivery → tracking →
analytics → dashboard), plus cancellation, invalid-transition, duplicate-
Kafka-event, unavailable-rider, Redis-outage, and invalid-input edge cases,
was run against the real, containerized stack — see the root README's
"Testing" section and `docs/TESTING.md` for what was actually verified.

## Deployment model actually used

This project runs **locally**, via Docker Compose, on a single developer
machine. `docker-compose.yml` defines all seven containers (Postgres,
Kafka, Redis, the three Spring Boot services, and the dashboard) with
health-checked startup ordering. **No cloud deployment (AWS or otherwise)
has been performed** — see the root README's "Limitations" and "Future
improvements" sections for what a cloud deployment would involve and why it
was not attempted here.
