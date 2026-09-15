# API Reference

REST endpoints actually implemented across the three Spring Boot services.
Every endpoint, field, validation rule, and status code below is taken
directly from the controller/DTO source code — nothing is aspirational.
All request/response bodies are JSON.

Base URLs (host-run or Docker Compose — same ports either way):

| Service | Base URL |
|---|---|
| order-service | `http://localhost:8081` |
| delivery-service | `http://localhost:8082` |
| tracking-service | `http://localhost:8083` |

Every service also exposes `GET /actuator/health` (added for container
healthchecks — see `docker-compose.yml`), returning `{"status":"UP"}` when
Postgres/Kafka/Redis are all reachable.

## Error format (shared shape across all three services)

Every non-2xx response uses the same body:

```json
{
  "timestamp": "2026-09-15T11:46:48.079977375",
  "status": 400,
  "error": "Bad Request",
  "message": "Validation failed",
  "path": "/api/orders",
  "details": ["customerId is required", "paymentMethod is required"]
}
```

`details` is `null` for errors that aren't field-validation failures (404s,
409s) — `message` alone describes those.

| Status | Meaning | Example cause |
|---|---|---|
| 400 | Bean-validation failure | Missing/invalid field (see per-endpoint tables below) |
| 404 | Referenced entity not found | Unknown `customerId`, `orderId`, `deliveryLocationId` |
| 409 | Valid request, illegal state transition | Cancelling an already-cancelled order, assigning a rider twice, no rider available in a city |
| 500 | Unexpected error | Caught by a catch-all handler, returns `"Unexpected error: <message>"` |

---

## order-service (`:8081`)

### `POST /api/orders` — create an order

Request body:

```json
{
  "customerId": 1,
  "deliveryLocationId": 1,
  "paymentMethod": "card",
  "items": [
    {"productName": "Burger", "category": "food", "unitPrice": 8.50, "quantity": 2}
  ]
}
```

| Field | Validation |
|---|---|
| `customerId` | required |
| `deliveryLocationId` | required; 404 if no such location |
| `paymentMethod` | required; must be one of `card`, `cash`, `wallet`, `upi` |
| `items` | required, non-empty |
| `items[].productName` | required (non-blank) |
| `items[].category` | required (non-blank) |
| `items[].unitPrice` | required, `>= 0` |
| `items[].quantity` | required, `> 0` |

`customerId` not found → 404. `total_amount` is computed server-side from
line items (`unit_price × quantity`, summed) — never trusted from the
client.

Response `201 Created`:

```json
{
  "orderId": 100036,
  "customerId": 1,
  "deliveryLocationId": 1,
  "riderId": null,
  "status": "PLACED",
  "orderPlacedAt": "2026-09-15T11:24:13.961410179",
  "totalAmount": 20.25,
  "paymentMethod": "card",
  "items": [
    {"orderItemId": 254735, "productName": "Burger", "category": "food", "unitPrice": 8.50, "quantity": 2, "lineTotal": 17.00}
  ]
}
```

### `GET /api/orders/{id}` — fetch one order

Response `200 OK`: same shape as the create response. `404` if not found.

### `GET /api/orders?page=&size=&status=` — list orders

Standard Spring Data `Pageable` query params (`page`, `size`, `sort`), plus
an optional `status` filter (one of the 10 order-status values). Response
is a Spring Data `Page<OrderResponse>` (`content`, `totalElements`,
`totalPages`, etc.).

### `PUT /api/orders/{id}/cancel` — cancel an order

No request body. Legal only from a non-terminal status (anything except
`DELIVERED`/`CANCELLED`/`FAILED`) — `409` otherwise. On success: `orders.status`
→ `CANCELLED`, a `CANCELLED` row appended to `order_status_history`, the
Redis status cache updated, and an `ORDER_CANCELLED` event published.
Response `200 OK`: the updated order.

---

## delivery-service (`:8082`)

### `POST /api/riders` — register a rider

Request body:

```json
{
  "firstName": "Test", "lastName": "Rider", "phone": "555-0000",
  "vehicleType": "bike", "city": "Austin", "rating": 4.5,
  "currentLatitude": 30.2672, "currentLongitude": -97.7431
}
```

| Field | Validation |
|---|---|
| `firstName`, `lastName`, `phone`, `city` | required (non-blank) |
| `vehicleType` | required; one of `bike`, `scooter`, `car`, `bicycle` |
| `rating` | optional; `0.0`-`5.0` if present |
| `currentLatitude`/`currentLongitude` | optional — falls back to a hardcoded per-city centroid when absent |

Response `201 Created`: `{"riderId", "firstName", "lastName", "vehicleType", "city", "rating", "active", "available", "currentLatitude", "currentLongitude"}` (`active`/`available` both default `true`).

### `GET /api/riders?page=&size=&sort=` — list riders

Paginated (`Page<RiderResponse>`).

### `PUT /api/riders/{id}/availability` — toggle availability

Request body: `{"available": false}` (`available` required). Response
`200 OK`: the updated rider.

### `GET /api/riders/{id}/availability` — check availability

Response `200 OK`: `{"riderId": 12, "available": true}`. Cache-aside read
(Redis `rider:available:{id}`, Postgres fallback on miss).

### `POST /api/deliveries/{orderId}/assign` — assign a rider

No request body. Looks up the order's delivery-location city, queries
active+available riders in that city, and picks the lowest-scored candidate
(`distance_km × 1.0 + active_delivery_count × 2.0` — see the root README's
"why this schema"/rider-matching notes and `docs/DATABASE.md`).

| Response | Condition |
|---|---|
| `201 Created` — the new delivery (`deliveryStatus: "ASSIGNED"`) | Success |
| `404` | No such order |
| `409` | Order is already terminal, already has a delivery, or no available rider in that city |

### `PUT /api/deliveries/{orderId}/status` — advance delivery status

Request body: `{"status": "PICKED_UP"}` (one of `ASSIGNED`, `PICKED_UP`,
`OUT_FOR_DELIVERY`, `DELIVERED`, `FAILED`). Legal transitions only:
`ASSIGNED→PICKED_UP→OUT_FOR_DELIVERY→DELIVERED`, with `FAILED` reachable
from `ASSIGNED`/`PICKED_UP`/`OUT_FOR_DELIVERY`. Illegal transition → `409`.
On success, the corresponding order status and Kafka event are also
updated/published (`OUT_FOR_DELIVERY`→`DELIVERY_STARTED`,
`DELIVERED`→`DELIVERY_COMPLETED`, `FAILED`→`DELIVERY_FAILED`).

### `GET /api/deliveries/{orderId}` — fetch delivery by order

Response `200 OK`: `{"deliveryId", "orderId", "riderId", "assignedAt", "pickedUpAt", "deliveredAt", "deliveryStatus", "distanceKm"}`. `404` if no delivery exists for that order.

---

## tracking-service (`:8083`)

### `GET /api/orders/{orderId}/tracking` — current status + full history

Response `200 OK`:

```json
{
  "orderId": 100036,
  "currentStatus": "DELIVERED",
  "history": [
    {"status": "PLACED", "changedAt": "2026-09-15T11:24:13.96141"},
    {"status": "RIDER_ASSIGNED", "changedAt": "2026-09-15T11:37:49.560616"},
    {"status": "PICKED_UP", "changedAt": "2026-09-15T11:41:40.052723"},
    {"status": "OUT_FOR_DELIVERY", "changedAt": "2026-09-15T11:41:51.645416"},
    {"status": "DELIVERED", "changedAt": "2026-09-15T11:42:09.748933"}
  ]
}
```

`currentStatus` is a Redis cache-aside read (`order:status:{orderId}`,
Postgres fallback on miss, repopulating the cache); `history` is always read
from `order_status_history` directly.

### `POST /api/orders/{orderId}/tracking` — record a status transition

Request body: `{"status": "CONFIRMED"}`. This endpoint is **not** part of
the original three-service spec as literally stated — it exists because no
other endpoint reaches the `CONFIRMED`/`PREPARING`/`READY_FOR_PICKUP` stages
(order-service only sets `PLACED`/`CANCELLED`; delivery-service only sets
`RIDER_ASSIGNED` onward), and "store the complete status history" requires
somewhere to append those middle stages. Validated against the same legal-
transition table as every other status change; illegal transition → `409`.
Response `201 Created`: `{"status": "CONFIRMED", "changedAt": "..."}`.

---

## Example: full order lifecycle via curl

```bash
# 1. Create an order
curl -X POST http://localhost:8081/api/orders -H "Content-Type: application/json" \
  -d '{"customerId":1,"deliveryLocationId":1,"paymentMethod":"card","items":[{"productName":"Burger","category":"food","unitPrice":8.50,"quantity":2}]}'

# 2. Advance through the pre-pickup stages (tracking-service)
curl -X POST http://localhost:8083/api/orders/100036/tracking -H "Content-Type: application/json" -d '{"status":"CONFIRMED"}'
curl -X POST http://localhost:8083/api/orders/100036/tracking -H "Content-Type: application/json" -d '{"status":"PREPARING"}'
curl -X POST http://localhost:8083/api/orders/100036/tracking -H "Content-Type: application/json" -d '{"status":"READY_FOR_PICKUP"}'

# 3. Assign a rider (delivery-service)
curl -X POST http://localhost:8082/api/deliveries/100036/assign

# 4. Advance the delivery
curl -X PUT http://localhost:8082/api/deliveries/100036/status -H "Content-Type: application/json" -d '{"status":"PICKED_UP"}'
curl -X PUT http://localhost:8082/api/deliveries/100036/status -H "Content-Type: application/json" -d '{"status":"OUT_FOR_DELIVERY"}'
curl -X PUT http://localhost:8082/api/deliveries/100036/status -H "Content-Type: application/json" -d '{"status":"DELIVERED"}'

# 5. Read the full history
curl http://localhost:8083/api/orders/100036/tracking
```

This exact sequence was run against the live, containerized system — see
the root README's "Testing" section for the full record (real order IDs,
real timestamps, real Postgres/Redis state after each step).

## What this API does not have

No authentication/authorization (any caller can call any endpoint — a
deliberate scope decision for a portfolio project, not an oversight), no
rate limiting, no API gateway/versioning scheme, no OpenAPI/Swagger UI
generated (this document is the reference instead), and no pagination
cursor beyond Spring Data's offset-based `Pageable`.
