# Database Design

PostgreSQL 16, one database (`oda_db`), 9 tables, 6 views, 17 indexes beyond
the primary/unique keys. Schema lives in `database/schema.sql`,
`database/indexes.sql`, `database/views.sql`, `database/seed.sql`
(hand-written sample data), and the one-time bulk-load pair
`database/staging_schema.sql` / `database/load_generated_dataset.sql`
(loads the synthetic dataset from `data_generator/output/*.csv`).

## Entity-relationship overview

```
locations ──┬─────────────────────────┐
            │                         │
            ▼                         ▼
        customers                  orders ──┬──► order_items
            │                        │       │
            │                        │       └──► order_status_history
            │                        ▼
            │                   deliveries ◄── riders
            │
            └── (default_location_id, optional)

event_log            (independent — synthetic-data raw-event landing table)
processed_events      (independent — live Kafka consumer idempotency ledger)
```

## Tables

### `locations`
Any physical delivery address.
| Column | Type | Notes |
|---|---|---|
| `location_id` | `BIGSERIAL PK` | |
| `address_line` | `VARCHAR(255) NOT NULL` | |
| `city` | `VARCHAR(100) NOT NULL` | 6 canonical values in the generated dataset: Austin, Denver, Portland, Chicago, Miami, Seattle |
| `state`, `postal_code` | nullable | |
| `latitude`, `longitude` | `NUMERIC(9,6)`, nullable | used by delivery-service's rider-matching distance calculation |
| `created_at` | `TIMESTAMP NOT NULL DEFAULT now()` | |

### `customers`
| Column | Type | Notes |
|---|---|---|
| `customer_id` | `BIGSERIAL PK` | |
| `first_name`, `last_name` | `NOT NULL` | |
| `email` | `VARCHAR(255) NOT NULL UNIQUE` | |
| `phone` | nullable | |
| `signup_date` | `DATE NOT NULL` | |
| `default_location_id` | `BIGINT REFERENCES locations` | nullable |

### `riders`
| Column | Type | Notes |
|---|---|---|
| `rider_id` | `BIGSERIAL PK` | |
| `first_name`, `last_name`, `phone`, `city` | `NOT NULL` | |
| `vehicle_type` | `VARCHAR(20) NOT NULL CHECK IN ('bike','scooter','car','bicycle')` | |
| `rating` | `NUMERIC(2,1) CHECK (0-5)` | nullable |
| `is_active` | `BOOLEAN NOT NULL DEFAULT TRUE` | |
| `is_available` | `BOOLEAN NOT NULL DEFAULT TRUE` | toggled via `PUT /api/riders/{id}/availability` |
| `current_latitude`, `current_longitude` | `NUMERIC(9,6)`, nullable | last-known ping; falls back to a city centroid when null |
| `joined_date` | `DATE NOT NULL` | |

### `orders`
| Column | Type | Notes |
|---|---|---|
| `order_id` | `BIGSERIAL PK` | |
| `customer_id` | `BIGINT NOT NULL REFERENCES customers` | |
| `delivery_location_id` | `BIGINT NOT NULL REFERENCES locations` | |
| `rider_id` | `BIGINT REFERENCES riders` | nullable until assigned |
| `status` | `VARCHAR(20) NOT NULL DEFAULT 'PLACED' CHECK IN (10 values)` | `PLACED, CONFIRMED, PREPARING, READY_FOR_PICKUP, RIDER_ASSIGNED, PICKED_UP, OUT_FOR_DELIVERY, DELIVERED, CANCELLED, FAILED` |
| `order_placed_at` | `TIMESTAMP NOT NULL` | |
| `total_amount` | `NUMERIC(10,2) NOT NULL CHECK (>= 0)` | computed server-side from `order_items`, never trusted from a client |
| `payment_method` | `VARCHAR(30) NOT NULL CHECK IN ('card','cash','wallet','upi')` | |

### `order_items`
| Column | Type | Notes |
|---|---|---|
| `order_item_id` | `BIGSERIAL PK` | |
| `order_id` | `BIGINT NOT NULL REFERENCES orders ON DELETE CASCADE` | |
| `product_name`, `category` | `NOT NULL` | |
| `unit_price` | `NUMERIC(10,2) NOT NULL CHECK (>= 0)` | |
| `quantity` | `INTEGER NOT NULL CHECK (> 0)` | |
| `line_total` | `NUMERIC(10,2) GENERATED ALWAYS AS (unit_price * quantity) STORED` | computed column |

### `deliveries`
The logistics leg of an order, created once a rider is assigned.
| Column | Type | Notes |
|---|---|---|
| `delivery_id` | `BIGSERIAL PK` | |
| `order_id` | `BIGINT NOT NULL UNIQUE REFERENCES orders ON DELETE CASCADE` | one delivery per order, enforced by `UNIQUE` |
| `rider_id` | `BIGINT NOT NULL REFERENCES riders` | |
| `assigned_at` | `TIMESTAMP NOT NULL` | |
| `picked_up_at`, `delivered_at` | nullable | |
| `delivery_status` | `VARCHAR(20) NOT NULL DEFAULT 'assigned' CHECK IN ('assigned','picked_up','out_for_delivery','delivered','failed')` | lowercase — mirrors `orders.status` granularity, different casing convention (see "Design notes") |
| `distance_km` | `NUMERIC(6,2) CHECK (>= 0)` | nullable |
| `chk_pickup_after_assign` | `CHECK (picked_up_at IS NULL OR picked_up_at >= assigned_at)` | |
| `chk_delivered_after_pickup` | `CHECK (delivered_at IS NULL OR picked_up_at IS NULL OR delivered_at >= picked_up_at)` | |

### `order_status_history`
Append-only audit trail — every status transition an order goes through,
regardless of which service made the change. This is what the `order_funnel`
view and the analytics layer's stage-duration analysis are built from.
| Column | Type | Notes |
|---|---|---|
| `history_id` | `BIGSERIAL PK` | |
| `order_id` | `BIGINT NOT NULL REFERENCES orders ON DELETE CASCADE` | |
| `status` | `VARCHAR(20) NOT NULL CHECK` (same 10-value list as `orders.status`) | |
| `changed_at` | `TIMESTAMP NOT NULL` | |

### `event_log`
A **synthetic-data-only** raw-event landing table populated by
`data_generator/` (simulating what an unprocessed Kafka event stream might
look like, including intentionally-injected duplicate content for the
data-quality layer to detect). **Not written to by the live backend
services** — no Java code in this repository references this table; it
exists purely for the data-quality/analytics layers to work with.
| Column | Type | Notes |
|---|---|---|
| `event_id` | `BIGSERIAL PK` | |
| `order_id` | `BIGINT REFERENCES orders ON DELETE SET NULL` | nullable |
| `event_type` | `VARCHAR(50) NOT NULL` | unconstrained (intentionally loose) |
| `payload` | `JSONB` | |
| `event_timestamp` | `TIMESTAMP NOT NULL` | |

### `processed_events`
The **live** Kafka consumer's idempotency ledger (distinct from `event_log`
above). `tracking-service` inserts one row per successfully-processed
event, keyed by the producer-assigned `event_id` (a UUID, not a DB
surrogate) so a re-delivered event is detected and skipped.
| Column | Type | Notes |
|---|---|---|
| `event_id` | `VARCHAR(64) PK` | producer-assigned UUID from the Kafka JSON envelope |
| `event_type`, `consumer_group` | `NOT NULL` | |
| `order_id` | nullable | |
| `processed_at` | `TIMESTAMP NOT NULL DEFAULT now()` | |

## Indexes (`database/indexes.sql`)

Postgres does not auto-index foreign-key columns, so every FK used in a
join or filter has an explicit index: `locations(city)`,
`customers(default_location_id)`, `riders(city)`, `orders(customer_id)`,
`orders(rider_id)`, `orders(delivery_location_id)`, `orders(status)`,
`orders(order_placed_at)`, `order_items(order_id)`,
`deliveries(rider_id)`, `deliveries(delivery_status)`,
`order_status_history(order_id)`,
`order_status_history(status, changed_at)` (composite, supports the funnel
and stage-duration queries), `event_log(order_id)`,
`event_log(event_type)`, `event_log(event_timestamp)`,
`processed_events(order_id)`.

## Views (`database/views.sql`)

| View | Business question | Shape |
|---|---|---|
| `daily_orders` | When is demand highest? | One row per calendar day: total/delivered/cancelled orders, gross revenue, avg order value |
| `delivery_performance` | What causes late deliveries? | Row-level (not pre-aggregated) per-delivery timing — total/pickup-wait/transit minutes; deliberately has no SLA threshold baked in, since that's a business assumption this project doesn't have a real value for |
| `rider_performance` | Which riders perform best? | Per-rider completed/failed counts, avg transit time, `RANK() OVER (PARTITION BY city ...)` |
| `customer_summary` | What is customer repeat behavior? | Per-customer order count, lifetime spend, first/last order date, `is_repeat_customer` flag |
| `order_funnel` | Where do orders drop off? | One row per lifecycle stage, count of distinct orders that reached it |
| `city_performance` | Which cities perform best/worst? | Per-city volume, cancellation rate, revenue, avg delivery time |

## Design notes

- **`orders.status`** is the current state; **`order_status_history`** is
  the append-only log of every transition — the funnel/stage-duration
  analysis needs the log, not just the current value.
- **Casing inconsistency, disclosed rather than silently fixed:**
  `orders.status`/`order_status_history.status` are uppercase
  (`PLACED`...`FAILED`, matching the Java `OrderStatus` enum), while
  `deliveries.delivery_status` is lowercase (`assigned`...`failed`,
  matching the Java `DeliveryStatus` enum). Both vocabularies were built to
  mirror their respective Java enums exactly rather than a single shared
  casing convention across the schema — a real inconsistency, not a typo,
  and one a schema review would reasonably flag.
- **`event_log` vs. `processed_events`** are two independent tables that
  are easy to confuse by name: `event_log` is synthetic-data-only (never
  written by the live services); `processed_events` is the live Kafka
  idempotency ledger. They were kept separate because `event_log.event_id`
  is a `BIGSERIAL` surrogate while `processed_events.event_id` needed to be
  the producer-assigned UUID string — reusing one table would have meant
  changing its primary-key type.
- **No SLA threshold is stored anywhere in the schema.** `delivery_performance`
  returns raw per-order minutes; any "late delivery" threshold applied in
  `analytics/sql/11_sla_breach_rate.sql` or the Python/dashboard layers is
  an explicitly-labeled assumption (45 minutes), never a schema-level fact.

## Data volume actually loaded

The `oda_pg_data` Docker volume currently holds the full synthetic dataset
generated by `data_generator/` and bulk-loaded via
`database/load_generated_dataset.sql`: 100,000 orders, 50,000 customers,
2,000 riders, 50,000 locations, 91,257 deliveries (1,842 rows excluded at
load time for violating the `chk_delivered_after_pickup`/pickup-order CHECK
constraints — see `data_generator/README.md` and `data_quality/README.md`
for why those rows exist and are excluded on purpose), 254,709 order items,
579,318 order-status-history rows. A small number of additional
orders/riders/locations (well under 0.1% of the total) were created during
later manual API and performance testing — see the root README's "Testing"
section; they do not materially change any of the above counts or any
percentage-based figure elsewhere in this documentation.

`database/seed.sql` (5 customers, 5 riders, 8 orders) is a separate, much
smaller hand-written dataset used only to validate the schema/views during
the database-layer build — it is **not** the dataset currently loaded, and
is overwritten (`TRUNCATE ... RESTART IDENTITY`) if run again.
