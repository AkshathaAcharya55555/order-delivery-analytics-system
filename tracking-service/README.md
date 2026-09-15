# Tracking Service

Spring Boot 3.3.4 / Java 17 / Maven. Read/write access to order tracking
status and its full history. Shares the `oda_db` PostgreSQL database with
order-service and delivery-service (see root README for why).

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/orders/{orderId}/tracking` | Current status + full ordered status history |
| POST | `/api/orders/{orderId}/tracking` | Record a new status transition (validated) — **see note below** |

Tracked statuses: `PLACED, CONFIRMED, PREPARING, READY_FOR_PICKUP,
RIDER_ASSIGNED, PICKED_UP, OUT_FOR_DELIVERY, DELIVERED, CANCELLED, FAILED`.

## Note on the POST endpoint (an interpretive addition)

The original task only specified the GET endpoint, plus the requirements
"store complete status history" and "validate invalid status transitions."
Taken literally, order-service only ever writes `PLACED`/`CANCELLED`, and
delivery-service only writes `RIDER_ASSIGNED` through `DELIVERED`/`FAILED` —
**no endpoint anywhere reaches `CONFIRMED`, `PREPARING`, or
`READY_FOR_PICKUP`**. Since those requirements are meaningless without a
write path, this service adds `POST /api/orders/{orderId}/tracking` as the
authority for the full transition matrix, filling that gap. This is a
judgment call, not something explicitly requested — flagged here rather than
assumed silently.

## Transition matrix (`OrderStatus.canTransitionTo`)

```
PLACED -> CONFIRMED, CANCELLED
CONFIRMED -> PREPARING, CANCELLED
PREPARING -> READY_FOR_PICKUP, CANCELLED
READY_FOR_PICKUP -> RIDER_ASSIGNED, CANCELLED
RIDER_ASSIGNED -> PICKED_UP, CANCELLED, FAILED
PICKED_UP -> OUT_FOR_DELIVERY, FAILED
OUT_FOR_DELIVERY -> DELIVERED, FAILED
DELIVERED / CANCELLED / FAILED -> (terminal, no further transitions)
```

This same matrix is duplicated in order-service and delivery-service (each
validates only the narrow subset of transitions its own endpoints trigger)
since the three services are independent deployables with no shared library
in this project.

## Kafka / Redis

- Produces `STATUS_CHANGED` on every `POST .../tracking` transition.
- **Consumes** the other six topics (`order-created`, `order-cancelled`,
  `rider-assigned`, `delivery-started`, `delivery-completed`,
  `delivery-failed`) in consumer group `tracking-service-group` — the only
  consumer in this project. Each event is checked against the
  `processed_events` table (`event_id` as the idempotency key, atomic
  `INSERT ... ON CONFLICT DO NOTHING`) before its side effect (a Redis cache
  write) runs, so a duplicate/redelivered event is a safe no-op.
- `OrderStatusCache` (Redis, `order:status:{orderId}`, 10 min TTL):
  cache-aside read on `GET .../tracking`, write-through on this service's own
  `POST .../tracking` and from the Kafka consumer.
- Full topic/producer/consumer/ordering documentation and the Redis
  rationale are in the root README — this section only covers what's
  specific to this service.

## Run

Requires `oda_postgres`, `oda_kafka`, and `oda_redis` running
(`docker compose up -d` from the repo root) with `database/schema.sql` applied.

```bash
mvn spring-boot:run   # starts on :8083
```

## Test

```bash
mvn test
```

12 tests: `TrackingServiceTest` (5, Mockito — legal/illegal transitions,
terminal-state rejection, and a check that the full 8-step happy path is
entirely legal per the matrix), `TrackingControllerIntegrationTest` (4,
`@SpringBootTest` + MockMvc against the real Postgres instance,
`@Transactional` rollback), `TrackingKafkaRedisIntegrationTest` (3 — a real
producer/consumer round trip for `STATUS_CHANGED`, a Redis cache-miss
fallback check, and the duplicate-event idempotency test described above).

**Last actual run:** `BUILD SUCCESS`, 12/12 tests passing (verified — see
project-level task report). The idempotency test's consumer log for that
run recorded: `Duplicate event <id> (RIDER_ASSIGNED) for order 28 skipped`.
