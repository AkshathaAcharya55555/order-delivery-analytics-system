# Order Service

Spring Boot 3.3.4 / Java 17 / Maven. Owns order creation, retrieval, listing,
and cancellation. Connects directly to the shared `oda_db` PostgreSQL
database (see root `docker-compose.yml`) — this project uses one shared
database across all three services rather than per-service databases, a
deliberate simplification documented in the root README.

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/orders` | Create an order (validates customer/location exist, computes `totalAmount` from items, writes the initial `PLACED` row to `order_status_history`) |
| GET | `/api/orders/{id}` | Fetch one order with its items |
| GET | `/api/orders?status=&page=&size=` | Paginated list, optional status filter |
| PUT | `/api/orders/{id}/cancel` | Cancel an order (409 if already in a terminal state — `DELIVERED`, `CANCELLED`, `FAILED`) |

## Kafka / Redis

- Publishes `ORDER_CREATED` (on create) and `ORDER_CANCELLED` (on cancel) to
  Kafka — fire-and-forget, logged on failure, never fails the request.
- Write-through updates the shared `order:status:{orderId}` Redis cache
  (10 min TTL) that tracking-service reads from, for the two transitions
  this service owns.
- Full topic/consumer/ordering documentation is in the root README, not
  duplicated here.

## Run

Requires `oda_postgres`, `oda_kafka`, and `oda_redis` running
(`docker compose up -d` from the repo root) with `database/schema.sql` applied.

```bash
mvn spring-boot:run   # starts on :8081
```

## Test

```bash
mvn test
```

23 tests: 5 unit tests (Mockito, no DB) covering total calculation and
status-transition validation; 6 integration tests (`@SpringBootTest` +
MockMvc, `@Transactional` auto-rollback) against the real Postgres instance
using customers/locations seeded by `database/seed.sql`; 9 further
validation-focused integration tests (`OrderValidationTest` — invalid
payment method, negative/zero quantity, negative price, blank fields,
nonexistent customer/location, added in the dedicated testing phase); 3
Kafka/Redis integration tests using a raw `KafkaConsumer` to observe the
actual wire format (not trusting this service's own producer code) plus
direct `StringRedisTemplate` assertions on the cache.

**Last actual run:** `BUILD SUCCESS`, 23/23 tests passing — see
`docs/TESTING.md` for the full, current project-wide test results (this
number can drift as tests are added; `docs/TESTING.md` is kept current).

## Notes

- `orders.status` uses the 10-value uppercase enum shared with
  tracking-service (`PLACED, CONFIRMED, PREPARING, READY_FOR_PICKUP,
  RIDER_ASSIGNED, PICKED_UP, OUT_FOR_DELIVERY, DELIVERED, CANCELLED, FAILED`).
  This service only ever writes `PLACED` (on creation) and `CANCELLED` (on
  cancel) — the remaining transitions belong to delivery-service and
  tracking-service.
- `hibernate.ddl-auto=validate`: this service does not own or generate the
  schema (that's `database/schema.sql`); it fails fast on startup if its
  entity mappings don't match the real table structure.
