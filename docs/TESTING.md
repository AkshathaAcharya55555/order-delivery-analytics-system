# Testing

Full inventory of automated tests in this repository, what they cover, how
to run them, and the results of the most recent complete run. This document
only reports tests that were actually written and actually executed — see
"Results" below for the real, current pass/fail counts.

## Test organization

```
order-service/src/test/java/...       # JUnit 5 (Mockito unit tests + @SpringBootTest integration tests)
delivery-service/src/test/java/...    # same pattern
tracking-service/src/test/java/...    # same pattern
tests/                                # Python (pytest) — cross-cutting, language-agnostic layers
├── conftest.py                       # shared Postgres connection fixture
├── db_constraints/test_constraints.py
├── data_quality/test_validate_rules.py
├── analytics_sql/test_sql_queries.py
└── performance/                      # NOT pytest — standalone measurement scripts (see docs/PERFORMANCE.md)
```

Java tests exercise the three backend services; the `tests/` Python suite
covers the database schema itself, the `data_quality/validate.py` rules, and
the `analytics/sql/*.sql` query files — none of which had any test coverage
before this phase.

## Coverage against each requested area

| Area | Where | Notes |
|---|---|---|
| Order creation | `order-service` `OrderControllerIntegrationTest`, `OrderServiceTest` | Round-trip create+fetch, total computed from items, PLACED history row written |
| Order validation | `order-service` `OrderValidationTest` (new) | Invalid payment method, negative/zero quantity, negative unit price, blank product name/category, missing required fields, nonexistent customer/location — each asserted against the actual Bean Validation message |
| Cancellation | `order-service` `OrderControllerIntegrationTest`, `OrderServiceTest` | Legal cancel from PLACED; cancelling an already-cancelled order returns 409; cancelling a DELIVERED order rejected |
| Rider assignment | `delivery-service` `DeliveryServiceTest`, `RiderMatcherTest`, `RiderDeliveryIntegrationTest` | Successful match, already-has-delivery conflict, terminal-order conflict, no-candidates-in-city conflict, full HTTP round trip |
| Delivery status | `delivery-service` `DeliveryServiceTest`, `RiderDeliveryIntegrationTest` | Legal transition updates delivery + order; illegal transition (ASSIGNED→DELIVERED) rejected |
| Kafka event processing | `order-service`/`delivery-service`/`tracking-service` `*KafkaRedisIntegrationTest` | Raw `KafkaConsumer` (not `@KafkaListener`) observes the actual wire event: envelope schema, partition key = order_id, Redis write-through |
| Duplicate event handling | `tracking-service` `TrackingKafkaRedisIntegrationTest.consumingRiderAssignedEvent_updatesCache_andIsIdempotentOnDuplicateDelivery` | Same event sent twice on the real topic; asserts exactly one `processed_events` row |
| Invalid status transitions | `tracking-service` `TrackingServiceTest`, `delivery-service` `DeliveryServiceTest` | Illegal jump (PLACED→PREPARING), terminal-order rejection, full 8-stage legal chain |
| Database constraints | `tests/db_constraints/test_constraints.py` (new) | 19 tests: every CHECK/NOT NULL/FK/UNIQUE constraint in `database/schema.sql` attempted directly via raw SQL, independent of application code |
| Data-quality rules | `tests/data_quality/test_validate_rules.py` (new) | 24 tests: each of `data_quality/validate.py`'s 10 rule functions tested against a hand-built clean baseline (0 failures) and a deliberately corrupted variant (rule must detect it) |
| Analytical SQL | `tests/analytics_sql/test_sql_queries.py` (new) | 21 tests: all 20 `analytics/sql/*.sql` files executed against the live, fully-loaded database — must run without error and return ≥1 row |

## Running the tests

```bash
# Java (from each service directory)
cd order-service && mvn test
cd delivery-service && mvn test
cd tracking-service && mvn test

# Python (from repo root)
pip install -r tests/requirements.txt
python -m pytest tests/ -v
```

The Java integration tests and the `tests/db_constraints` /
`tests/analytics_sql` Python tests all connect to the real, already-running
`oda_postgres` (and `oda_kafka` / `oda_redis` for the Kafka/Redis
integration tests) — see the root README's "Running the database layer" /
"Running the backend services" sections. `tests/analytics_sql` additionally
requires the full generated dataset to be loaded (it skips with a clear
reason if fewer than 1,000 orders are present).

## Results (actual run, 2026-09-15)

All commands below were actually executed; every number is from that run.

| Suite | Tests | Failures | Notes |
|---|---|---|---|
| order-service (`mvn test`) | 23 | 0 | `OrderControllerIntegrationTest` (6), `OrderValidationTest` (9, new), `KafkaRedisIntegrationTest` (3), `OrderServiceTest` (5) |
| delivery-service (`mvn test`) | 23 | 0 | `RiderAvailabilityCacheFallbackTest` (2), `RiderDeliveryIntegrationTest` (4, 2 fixed - see below), `DeliveryKafkaRedisIntegrationTest` (4), `DeliveryServiceTest` (7), `RiderMatcherTest` (6) |
| tracking-service (`mvn test`) | 12 | 0 | `TrackingControllerIntegrationTest` (4), `TrackingKafkaRedisIntegrationTest` (3), `TrackingServiceTest` (5) |
| `tests/` (`pytest`) | 64 | 0 | `db_constraints` (19), `data_quality` (24), `analytics_sql` (21) |
| **Total** | **122** | **0** | |

All 122 tests pass. The Java suites were run with the containerized
`order-service`/`delivery-service`/`tracking-service` **stopped** (only
`oda_postgres`/`oda_kafka`/`oda_redis` running) — see "A real flaky-test
finding" below for why that matters.

## Two pre-existing tests fixed (not just re-run)

`delivery-service`'s `RiderDeliveryIntegrationTest` had two tests failing
before this phase, both for the same root cause: they were written when the
database held only `database/seed.sql`'s 5 sample rows, and now also holds
the full synthetic dataset (2,000 riders across all 6 canonical cities,
loaded during the analytics phase) that both tests' assumptions no longer
hold against:

- `assignDelivery_noRiderInCity_returns409` asserted no rider exists in
  "Seattle" — but Seattle is one of the 6 canonical cities and now has 313
  real riders. **Fix:** use a made-up city ("Nowhereville") guaranteed to
  have zero riders, rather than a real city that happens to have been empty
  when the test was first written.
- `createRider_thenListRiders_includesIt` asserted a freshly-created rider
  (id in the 2000s, since 2,000 rows are already loaded) appears on
  `page=0&size=500` of the default-sorted rider list — no longer true once
  total rows exceed 500. **Fix:** request `sort=riderId,desc` (Spring Data's
  `Pageable` binds this automatically, no controller change needed) so the
  newest rider is deterministically on page 0 regardless of total row count.

Both were verified by re-running the class in isolation (pass) and as part
of the full suite (pass) — see Results above.

## A real flaky-test finding: Kafka test isolation vs. the running Docker stack

While first running the full suite with the containerized
order/delivery/tracking-service **also** running (`docker compose up -d`
from the containerization phase), `order-service`'s `KafkaRedisIntegrationTest`
failed intermittently (2/3 tests failed on one run, 1/3 on a re-run) with
`Expecting actual not to be null` — the test's raw `KafkaConsumer` didn't
observe the expected event within its 15-second polling deadline, and
individual test elapsed times (30-110s) far exceeded that deadline, meaning
the `consumer.poll(500ms)` calls themselves were taking far longer than
500ms per call.

**Root cause, confirmed by isolation:** stopping the three containerized
app services (leaving `oda_kafka`/`oda_postgres`/`oda_redis` running) and
re-running the exact same test class made all 3 tests pass reliably in
40.1s, both in isolation and as part of the full suite (see Results table).
The single-broker KRaft Kafka container has three live consumer groups
(one per containerized service) permanently connected in addition to
whatever ad-hoc test consumer/producer clients `mvn test` spins up on the
host — enough concurrent load on a single-broker container to push real
poll/coordinator-discovery latency past the test's fixed timeouts.

**This is an environment/test-isolation limitation, not a code defect** in
either the tests or the Kafka producer/consumer code itself (the same
assertions pass reliably once broker load is reduced). Documented here
rather than silently worked around by, e.g., loosening the test's timeout
to hide the contention — a real reader should know that running `mvn test`
concurrently with the full `docker compose up` stack is not currently a
supported/reliable combination for the Kafka-integration test classes.

## A second real finding: IPv6 loopback flakiness through Docker Desktop

A later full re-run of `tests/` (after the containerized services had been
restarted and several performance scripts had also run against the same
stack) produced 26 errors/failures, all `psycopg2.OperationalError:
connection to server at "localhost" (::1), port 5432 failed: server closed
the connection unexpectedly`. This is the same intermittent IPv6-loopback
issue already found and worked around with `curl --max-time`/explicit
`127.0.0.1` during the containerization/end-to-end testing phase: on this
Windows/Docker Desktop setup, `localhost` sometimes resolves to `::1`
first, and Docker Desktop's port-forwarding proxy has been observed to
intermittently reset connections made over that specific path. It is not
a database, application, or test-logic defect — the same queries succeed
reliably once the connection is forced over IPv4.

**Fix:** changed the default `ODA_DB_HOST` in `tests/conftest.py` and
`tests/performance/{db_query_timing,kafka_latency}.py` from `"localhost"`
to `"127.0.0.1"` (`tests/performance/api_latency.py` and
`concurrent_orders.py` already used `127.0.0.1` for the HTTP calls and were
unaffected). **Verified** by running `python -m pytest tests/` three
consecutive times after the fix: 64/64 passed every time (86.9s, 67.4s,
107.1s) with zero connection errors.

## Not tested / out of scope for this phase

- No load/stress testing (see `docs/PERFORMANCE.md` for the small,
  explicitly-scoped performance checks that were run instead).
- No UI/browser testing of the Streamlit dashboard beyond what the earlier
  dashboard phase already did with `streamlit.testing.v1.AppTest`.
- No mutation testing or code-coverage percentage tooling was introduced.
- The two known, previously-disclosed backend issues (the rider-matching
  N+1 query pattern; Lettuce's slow failover latency when Redis is
  unavailable) are not re-tested here — they were already found and
  documented during the containerization/end-to-end testing phase and nothing
  in this phase's scope ("create or improve tests", "run the suite") calls
  for fixing them.

## Final status by component

| Component | Status | Basis |
|---|---|---|
| Order creation | **PASS** | `OrderControllerIntegrationTest`, `OrderServiceTest` — 0 failures |
| Order validation | **PASS** | `OrderValidationTest` (new, 9 tests) — 0 failures |
| Cancellation | **PASS** | `OrderControllerIntegrationTest`, `OrderServiceTest` — 0 failures |
| Rider assignment | **PASS** | `DeliveryServiceTest`, `RiderMatcherTest`, `RiderDeliveryIntegrationTest` (2 pre-existing tests fixed this phase) — 0 failures |
| Delivery status transitions | **PASS** | `DeliveryServiceTest`, `RiderDeliveryIntegrationTest` — 0 failures |
| Kafka event processing | **PASS** | `*KafkaRedisIntegrationTest` (all 3 services) — 0 failures when run without broker contention (see flaky-test finding) |
| Duplicate event handling | **PASS** | `TrackingKafkaRedisIntegrationTest` idempotency test — 0 failures |
| Invalid status transitions | **PASS** | `TrackingServiceTest`, `DeliveryServiceTest` — 0 failures |
| Database constraints | **PASS** | `tests/db_constraints/` (new, 19 tests) — 0 failures |
| Data-quality rules | **PASS** | `tests/data_quality/` (new, 24 tests) — 0 failures |
| Analytical SQL (20 queries) | **PASS** | `tests/analytics_sql/` (new, 21 tests) — 0 failures |
| API response time | **PASS (measured, no pass/fail threshold applies)** | See `docs/PERFORMANCE.md` Test 1 — real numbers recorded, not evaluated against an invented target |
| Database query execution time | **PASS (measured)** | See `docs/PERFORMANCE.md` Test 2 |
| Concurrent order creation | **PASS (measured)** | See `docs/PERFORMANCE.md` Test 3 — 20/20 succeeded |
| Kafka processing latency | **PASS (measured)** | See `docs/PERFORMANCE.md` Test 4 — 5/5 observed |
| Dashboard (Streamlit) | **NOT TESTED IN THIS PHASE** | Out of the areas listed for this phase; last validated in the dashboard-build phase via `streamlit.testing.v1.AppTest` (all 6 pages, 0 exceptions) |
| Sustained load / stress testing | **NOT TESTED** | Explicitly out of scope ("small realistic performance checks") |
| Redis-unavailable / unavailable-rider / invalid-order-data edge cases | **NOT TESTED IN THIS PHASE** | Already covered manually via curl during the containerization/end-to-end testing phase (all passed there); not re-run as automated tests in this phase |
