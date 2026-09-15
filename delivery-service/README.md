# Delivery / Rider Service

Spring Boot 3.3.4 / Java 17 / Maven. Owns riders, rider availability, and
delivery assignment/status. Shares the `oda_db` PostgreSQL database with
order-service and tracking-service (see root README for why).

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/riders` | Register a rider (optional `currentLatitude`/`currentLongitude`) |
| GET | `/api/riders?page=&size=` | Paginated rider list |
| PUT | `/api/riders/{id}/availability` | Toggle a rider's `is_available` flag |
| POST | `/api/deliveries/{orderId}/assign` | Run the rider-matching algorithm and assign the best rider |
| PUT | `/api/deliveries/{orderId}/status` | Advance delivery status (`ASSIGNED → PICKED_UP → OUT_FOR_DELIVERY → DELIVERED`, or `→ FAILED`) |
| GET | `/api/deliveries/{orderId}` | Fetch the delivery record for an order |
| GET | `/api/riders/{id}/availability` | Cache-aside read of a rider's availability (Redis, Postgres fallback) |

## Rider-matching algorithm (`RiderMatcher`, no ML)

1. **Filter**: candidates must be `is_active`, `is_available`, and in the
   order's delivery city (hard filter — this project doesn't model
   cross-city delivery).
2. **Score** each candidate: `score = 1.0 × approxDistanceKm + 2.0 × activeDeliveryCount`
   (lower wins). Both weights are declared constants in `RiderMatcher`,
   deliberately simple and adjustable — not fitted to any data.
3. **Distance** is approximate: it uses the rider's last-known
   `current_latitude`/`current_longitude` if the rider has sent one (set at
   registration or never updated after — there's no live GPS feed in this
   project), otherwise falls back to the rider's home-city centroid
   (hardcoded coordinates for the 6 cities used across this project).
4. **Workload** is the rider's current count of deliveries in
   `ASSIGNED`/`PICKED_UP`/`OUT_FOR_DELIVERY`.
5. If no candidate exists in-city, the endpoint returns `409 Conflict` — it
   never fabricates an assignment.

## Kafka / Redis

- Publishes `RIDER_ASSIGNED` (on assign), `DELIVERY_STARTED`
  (→`OUT_FOR_DELIVERY`), `DELIVERY_COMPLETED` (→`DELIVERED`), and
  `DELIVERY_FAILED` (→`FAILED`) to Kafka.
- `RiderAvailabilityCache` (Redis, 60s TTL): write-through on rider creation
  and `PUT .../availability`; cache-aside read on `GET .../availability`.
  Deliberately **not** used by the matching algorithm itself — see the notes
  below and the root README's Redis section for why.
- Full topic/consumer/ordering and Redis rationale documentation is in the
  root README.

## Run

Requires `oda_postgres`, `oda_kafka`, and `oda_redis` running
(`docker compose up -d` from the repo root) with `database/schema.sql` applied.

```bash
mvn spring-boot:run   # starts on :8082
```

## Test

```bash
mvn test
```

23 tests: `RiderMatcherTest` (6, pure logic — distance vs. workload
trade-offs, haversine sanity check against a known Austin→Denver distance),
`DeliveryServiceTest` (7, Mockito — assignment preconditions, illegal
transition rejection), `RiderDeliveryIntegrationTest` (4, `@SpringBootTest` +
MockMvc against the real Postgres instance, `@Transactional` rollback),
`DeliveryKafkaRedisIntegrationTest` (4, real Kafka consumer + Redis
assertions), `RiderAvailabilityCacheFallbackTest` (2, a real
`StringRedisTemplate` pointed at an unreachable port — genuine connection
failures, proving the fallback-to-Postgres path actually engages).

**Last actual run:** `BUILD SUCCESS`, 23/23 tests passing (verified — see
project-level task report).

## Notes

- `deliveries.delivery_status` was expanded from 4 to 5 values
  (`assigned, picked_up, out_for_delivery, delivered, failed`, stored
  lowercase — see `DeliveryStatusConverter`) specifically to match the
  order-level tracking granularity 1:1 and avoid an awkward mapping layer.
  This was a schema change made during this phase; see root README.
- `riders.is_available`, `riders.current_latitude`, `riders.current_longitude`
  were added in this phase for this service's own use.
- Known simplification: `assignRider` only requires the order to be
  non-terminal and not already assigned — not strictly gated on
  `READY_FOR_PICKUP` — so the endpoint is directly testable without first
  driving an order through tracking-service's intermediate transitions.
