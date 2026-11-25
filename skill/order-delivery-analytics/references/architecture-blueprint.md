# Blueprint: event-driven order & delivery backend

Use this in **Build mode**, when the user wants to create or extend an order
and delivery system rather than analyse one. It distils a working reference
implementation: three Spring Boot services on Kafka, Postgres and Redis,
covered by about 120 automated tests. The patterns are language-agnostic.
Adapt them to the user's stack. Do not force Java.

## 1. Services and ownership

| Service | Owns (writes) | Produces | Consumes |
|---|---|---|---|
| order | orders, order_items, status history for its own transitions | `order-created`, `order-cancelled` | — |
| delivery | deliveries, rider availability | `rider-assigned`, `delivery-started`, `delivery-completed`, `delivery-failed` | — (or `order-created` for auto-dispatch) |
| tracking | read models and caches | `status-changed` | all of the above |

Rule: **the service that changes state writes the history row synchronously,
in the same DB transaction**. Consumers only update read models and caches.
They never re-write history, or a redelivered event would produce double
history rows.

## 2. Order lifecycle (single shared vocabulary)

```
PLACED → CONFIRMED → PREPARING → READY_FOR_PICKUP → RIDER_ASSIGNED
       → PICKED_UP → OUT_FOR_DELIVERY → DELIVERED
any pre-pickup state → CANCELLED        PICKED_UP/OUT_FOR_DELIVERY → FAILED
```

- Enforce allowed transitions in one place (an enum with an
  `allowedNext()` table). Reject invalid ones with 409 Conflict, never silently.
- Use the same uppercase vocabulary in the DB CHECK constraint, the API, the
  events and the analytics. Translation layers between services are where
  status drift (DQ-05) comes from.

## 3. Event envelope

```json
{
  "eventId": "uuid-v4 assigned once by the producer",
  "eventType": "DELIVERY_COMPLETED",
  "orderId": 1234,
  "occurredAt": "2026-06-30T19:42:11Z",
  "sourceService": "delivery-service",
  "payload": { "...": "event-specific" }
}
```

- **Partition key = orderId**, so every event for an order stays in order.
- Use one topic per event type when there are few types. That gives simple
  ACLs and per-type retention.
- `occurredAt` comes from the server clock, never from a rider's device. Device
  clocks cause DQ-04 (delivered before pickup).

## 4. Idempotent consumers (at-least-once delivery)

```sql
CREATE TABLE processed_events (
  event_id       VARCHAR(64) PRIMARY KEY,
  event_type     VARCHAR(50) NOT NULL,
  order_id       BIGINT,
  consumer_group VARCHAR(100) NOT NULL,
  processed_at   TIMESTAMP NOT NULL DEFAULT now()
);
-- inside the consumer's transaction, BEFORE side effects:
INSERT INTO processed_events (event_id, event_type, order_id, consumer_group)
VALUES (:id, :type, :order, :group)
ON CONFLICT (event_id) DO NOTHING;      -- 0 rows inserted → duplicate → skip
```

Test it by replaying the same event twice and asserting exactly one row and
one side effect.

## 5. Transactional outbox (do this from day one)

Publishing to Kafka *after* the DB commit loses the event if the process
crashes between the two steps. Instead, write the event into an `outbox`
table in the same transaction. A relay (a poller, or Debezium CDC) then
publishes it and marks it sent.

```sql
CREATE TABLE outbox (
  id BIGSERIAL PRIMARY KEY, event_id VARCHAR(64) UNIQUE NOT NULL,
  topic VARCHAR(100) NOT NULL, partition_key VARCHAR(100) NOT NULL,
  payload JSONB NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT now(),
  published_at TIMESTAMP
);
CREATE INDEX outbox_unpublished ON outbox (id) WHERE published_at IS NULL;
```

## 6. Rider matching without N+1

The naive loop of "for each candidate rider, count their active deliveries"
issues one query per rider. In the reference build that took minutes for a
city with 300+ riders. Batch it instead:

```sql
SELECT r.rider_id, r.current_latitude, r.current_longitude,
       COUNT(d.delivery_id) FILTER (WHERE d.delivery_status IN ('assigned','picked_up','out_for_delivery')) AS active
FROM riders r
LEFT JOIN deliveries d ON d.rider_id = r.rider_id
WHERE r.city = :city AND r.is_active AND r.is_available
GROUP BY r.rider_id
HAVING COUNT(d.delivery_id) FILTER (WHERE d.delivery_status IN ('assigned','picked_up','out_for_delivery')) < :max_load
ORDER BY active, /* then distance */ r.rider_id
LIMIT 20;
```

Score the short list in code using distance, load and rating. Lock the chosen
rider with `SELECT ... FOR UPDATE SKIP LOCKED` so concurrent assignments cannot
double-book.

## 7. Redis cache-aside, done safely

- Keys such as `order:status:{id}` (TTL 10 min) and `rider:available:{id}` (TTL 60 s).
  Postgres stays the source of truth.
- Wrap every Redis call: on a read failure fall through to the DB, and on a
  write failure log and continue.
- **Set short client timeouts** (connect about 200 ms, command about 250 ms) and
  turn off long reconnect back-off. Default client settings caused outage
  fallbacks that stalled for more than 60 s in the reference build.
- Do not cache the matching query. It needs current state.

## 8. Schema essentials

`assets/schema/schema.sql` is a ready nine-table model with CHECK constraints
for status vocabularies, non-negative money and timestamp ordering
(`picked_up_at >= assigned_at`, `delivered_at >= picked_up_at`).
`assets/schema/indexes.sql` and `assets/schema/views.sql` add the analytical
indexes and six business views. Apply them to a **new** database only.

## 9. Test checklist (minimum)

- Every allowed transition succeeds and every disallowed one returns 409.
- Cancelling after pickup is rejected.
- Duplicate events produce exactly one processed row (§4).
- Assignment with no available rider returns a clear 409/422, not a 500.
- Redis down still returns correct data within the timeout (§7).
- Concurrent assignment of N orders never double-books a rider at max load.
- Run `scripts/dq_audit.py` against the service DB in CI with `--fail-on HIGH`.

## 10. Local stack

`assets/docker-compose.infra.yml` starts Postgres 16, Kafka 3.7 in KRaft mode
and Redis 7, with health checks, and applies the schema on first start.
Containers reach Kafka at `kafka:19092`; host apps use `localhost:9092`.
