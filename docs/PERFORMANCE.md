# Performance

Small, realistic performance checks — not a load-testing or benchmarking
exercise. Every number below is copied directly from an actual run of the
scripts in `tests/performance/` on 2026-09-15, against the containerized
stack (`docker compose up -d`). Nothing here is estimated, extrapolated, or
invented; anything not actually measured says so explicitly.

## Environment (common to all tests below)

- Host OS: Windows 11 Home Single Language 10.0.26200
- Docker Desktop / Engine: 29.2.0, Docker Desktop's Linux VM allocated
  ~3.70 GiB total memory (`docker info`)
- Containers: `postgres:16-alpine`, `apache/kafka:3.7.0` (single-broker
  KRaft mode), `redis:7-alpine`, plus the three Spring Boot services built
  from this repo's Dockerfiles (Java 17, `eclipse-temurin:17-jre-alpine`)
- Database size at time of testing: ~100,000-100,050 orders (grows slightly
  during this document's own test runs, since several of the checks below
  create real orders — exact count noted per test)
- **Important caveat:** this is a single developer workstation also used
  for building/running the rest of this project throughout the same
  session (Maven builds, `docker compose` restarts, other test suites) —
  not a dedicated, quiet benchmarking environment. Where two runs of the
  same test produced different numbers, both are reported rather than the
  more flattering one.

## Test 1: API response time

**Test:** `tests/performance/api_latency.py` — N sequential real HTTP
requests per endpoint via the `requests` library, timed client-side with
`time.perf_counter()` (includes network + full server processing time).

**Configuration:** n=20 per GET endpoint, n=10 for the POST (create) endpoint;
sequential (not concurrent - see Test 3 for concurrency); against
`order-service:8081`, `delivery-service:8082`, `tracking-service:8083`
running in Docker, freshly restarted ~3 minutes before the first run below.

| Endpoint | n | min | median | p90 | max |
|---|---|---|---|---|---|
| `GET /api/orders?page=0&size=20` | 20 | 60.4ms | 125.9ms | 244.7ms | 1067.8ms |
| `GET /api/orders/{id}` | 20 | 11.1ms | 15.1ms | 22.4ms | 108.5ms |
| `GET /api/riders?page=0&size=20` | 20 | 26.3ms | 86.5ms | 259.1ms | 5592.5ms |
| `GET /api/orders/{id}/tracking` | 20 | 21.5ms | 34.0ms | 69.3ms | 4998.1ms |
| `POST /api/orders` (create) | 10 | 62.0ms | 196.7ms | 990.9ms | 14291.8ms |

A second run (~15 minutes later, same containers, after other test suites
and performance scripts had also been running against the same stack in
between) measured noticeably higher and more variable latency:

| Endpoint | n | min | median | p90 | max |
|---|---|---|---|---|---|
| `GET /api/orders?page=0&size=20` | 20 | 101.3ms | 391.3ms | 710.2ms | 6840.9ms |
| `GET /api/orders/{id}` | 20 | 31.6ms | 64.7ms | 150.6ms | 204.8ms |
| `GET /api/riders?page=0&size=20` | 20 | 48.8ms | 101.6ms | 541.5ms | 3498.9ms |
| `GET /api/orders/{id}/tracking` | 20 | 40.3ms | 131.7ms | 349.7ms | 3009.3ms |
| `POST /api/orders` (create) | 10 | 136.7ms | 1407.1ms | 8179.2ms | 10115.1ms |

**Measured result:** typical (median) single-request latency is in the
tens-to-low-hundreds of milliseconds, but both runs show occasional outliers
in the multi-second range on every endpoint, including simple primary-key
lookups. This points to intermittent contention (GC pauses, HikariCP
connection acquisition, or general host load from concurrent activity —
see the environment caveat above) rather than a per-request algorithmic
cost, since the same endpoint's *typical* latency is otherwise low and
`GET /api/orders/{id}` (a primary-key lookup) shows the same outlier pattern
as the heavier endpoints.

**Environment:** as above; second run's higher numbers coincide with this
same session's concurrent-order and Kafka-latency scripts (Tests 3-4 below)
having just run against the same containers.

## Test 2: Database query execution time

**Test:** `tests/performance/db_query_timing.py` — real
`EXPLAIN (ANALYZE, FORMAT TEXT)` against `oda_postgres`, reporting
Postgres's own measured planning/execution time (not client-side timing).

**Configuration:** single run, dataset = 100,013 orders at the time of this
test.

| Query | Planning | Execution |
|---|---|---|
| `SELECT * FROM orders WHERE order_id = 1` (PK lookup) | 10.1ms | 2.6ms |
| `SELECT * FROM orders WHERE status = 'DELIVERED' LIMIT 100` | 9.0ms | 1.8ms |
| Unfiltered 4-table join (`deliveries` ⋈ `orders` ⋈ `locations` ⋈ `riders`, all ~91k delivery rows, no `LIMIT`) | 48.6ms | **8979.0ms** |
| `analytics/sql/01_daily_order_volume.sql` | 3.0ms | 59.3ms |
| `analytics/sql/06_p90_delivery_time.sql` | 2.4ms | 647.8ms |
| `analytics/sql/18_demand_vs_rider_availability.sql` | 5.2ms | 140.6ms |

**Measured result:** indexed primary-key lookups and small filtered/limited
scans complete in single-digit milliseconds. The unfiltered 4-table join
(the same query shape `analytics/scripts/queries.py`'s
`DELIVERY_FACTS_QUERY` uses, pulled deliberately with no `WHERE`/`LIMIT` to
match what that script actually runs) took ~9 seconds — this returns all
~91,257 delivery rows joined across 4 tables, so the cost reflects real row
volume moved, not necessarily a missing index; this was not investigated
further (out of scope for "small realistic performance checks").

**Environment:** as above; single measurement, not repeated.

## Test 3: Concurrent order creation

**Test:** `tests/performance/concurrent_orders.py` — a `ThreadPoolExecutor`
fires N `POST /api/orders` requests at (approximately) the same time and
waits for all to complete.

**Configuration:** 20 concurrent requests, `max_workers=20`, single run,
against `order-service` in Docker.

| Metric | Result |
|---|---|
| Total wall-clock time (20 concurrent requests) | 2729.5ms |
| Successful (HTTP 201) | 20/20 |
| Failed | 0/20 |
| Per-request latency (min / median / max) | 1872.8ms / 2170.3ms / 2666.6ms |
| Effective throughput | 7.3 orders/sec |

**Measured result:** all 20 concurrent order-creation requests succeeded
with no errors, no constraint violations, and no observed data corruption.
Per-request latency under this concurrency (~2s each) is markedly higher
than the single-request POST latency in Test 1 (tens to low hundreds of
ms), consistent with 20 requests contending for the same HikariCP
connection pool and Postgres backend simultaneously.

**Environment:** as above; single run at concurrency=20 only — not repeated
at other concurrency levels, and no sustained/repeated load test was run.

## Test 4: Kafka event-processing latency

**Test:** `tests/performance/kafka_latency.py` — creates a real order via
the REST API, then polls `processed_events` (tracking-service's consumer
idempotency ledger) every 100ms until a row appears for that order's
`ORDER_CREATED` event. Measures the full
produce → broker → consume → DB-write path, not just the Kafka transport.

**Configuration:** 5 sequential orders, 20s timeout per order, against the
full Docker-composed stack.

| Order | Latency |
|---|---|
| 1 | 4290ms |
| 2 | 1046ms |
| 3 | 1309ms |
| 4 | 466ms |
| 5 | 459ms |

**Measured result:** min 459ms, median 1046ms, max 4290ms; 5/5 events
observed within the 20s timeout. The first order's markedly higher latency
(4290ms vs. 459-1309ms for the rest) is consistent with a cold path (no
recent activity on that consumer group/connection) rather than a steady-state
number — not repeated enough times to separate a reliable "warm" figure from
this single cold outlier.

**Environment:** as above.

## Not measured in current environment

- Sustained/repeated load testing (e.g., hundreds of orders/sec over
  minutes) - not attempted; the checks above are single small runs, as
  requested ("small realistic performance checks").
- Kafka producer/consumer throughput under backpressure (multiple
  partitions, multiple consumer instances) - this project runs Kafka as a
  single-broker, mostly single-partition-per-topic setup; a partition/
  consumer-scaling throughput test was not run.
- Redis cache hit-rate/latency under concurrent load - not measured (Test 1
  incidentally exercises the Redis-backed tracking/status-cache reads, but
  no dedicated Redis-only benchmark was run).
- Memory/CPU profiling of any service under load - not measured; `docker
  stats` was used informally during the containerization phase's Redis-outage
  investigation but not as a repeatable, recorded benchmark here.
