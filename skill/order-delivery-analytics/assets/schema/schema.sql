-- ============================================================================
-- Order & Delivery Analytics System — Core Schema
-- Normalized relational model for a simulated food-delivery / logistics business.
-- Intended for a NEW, EMPTY database (no DROP statements on purpose).
-- Run order matters because of foreign key dependencies:
--   locations -> customers -> riders -> orders -> order_items
--            -> deliveries -> order_status_history -> event_log
-- ============================================================================


-- ----------------------------------------------------------------------------
-- locations: any physical delivery address (customer address, in this model)
-- ----------------------------------------------------------------------------
CREATE TABLE locations (
    location_id     BIGSERIAL PRIMARY KEY,
    address_line    VARCHAR(255) NOT NULL,
    city            VARCHAR(100) NOT NULL,
    state           VARCHAR(100),
    postal_code     VARCHAR(20),
    latitude        NUMERIC(9,6),
    longitude       NUMERIC(9,6),
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- customers
-- ----------------------------------------------------------------------------
CREATE TABLE customers (
    customer_id          BIGSERIAL PRIMARY KEY,
    first_name           VARCHAR(50) NOT NULL,
    last_name            VARCHAR(50) NOT NULL,
    email                VARCHAR(255) NOT NULL UNIQUE,
    phone                VARCHAR(20),
    signup_date           DATE NOT NULL,
    default_location_id  BIGINT REFERENCES locations(location_id),
    created_at           TIMESTAMP NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- riders
-- ----------------------------------------------------------------------------
CREATE TABLE riders (
    rider_id        BIGSERIAL PRIMARY KEY,
    first_name      VARCHAR(50) NOT NULL,
    last_name       VARCHAR(50) NOT NULL,
    phone           VARCHAR(20) NOT NULL,
    vehicle_type    VARCHAR(20) NOT NULL
                    CHECK (vehicle_type IN ('bike','scooter','car','bicycle')),
    city            VARCHAR(100) NOT NULL,
    rating          NUMERIC(2,1) CHECK (rating >= 0 AND rating <= 5),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    -- is_available / current_* added for the delivery-service's rider-matching
    -- algorithm: is_available is toggled via PUT /api/riders/{id}/availability;
    -- current_latitude/longitude is an optional last-known-position ping used
    -- as an approximate distance signal (falls back to the rider's home city
    -- centroid when null — riders aren't required to have sent a ping yet).
    is_available    BOOLEAN NOT NULL DEFAULT TRUE,
    current_latitude  NUMERIC(9,6),
    current_longitude NUMERIC(9,6),
    joined_date     DATE NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- orders
-- ----------------------------------------------------------------------------
CREATE TABLE orders (
    order_id             BIGSERIAL PRIMARY KEY,
    customer_id          BIGINT NOT NULL REFERENCES customers(customer_id),
    delivery_location_id BIGINT NOT NULL REFERENCES locations(location_id),
    rider_id             BIGINT REFERENCES riders(rider_id),
    -- Status vocabulary matches the tracking-service's 10-stage lifecycle
    -- exactly (uppercase, same list as order_status_history.status below) so
    -- there is a single shared vocabulary across services, not a per-service
    -- translation layer.
    status               VARCHAR(20) NOT NULL DEFAULT 'PLACED'
                         CHECK (status IN ('PLACED','CONFIRMED','PREPARING',
                                            'READY_FOR_PICKUP','RIDER_ASSIGNED',
                                            'PICKED_UP','OUT_FOR_DELIVERY',
                                            'DELIVERED','CANCELLED','FAILED')),
    order_placed_at      TIMESTAMP NOT NULL,
    total_amount         NUMERIC(10,2) NOT NULL CHECK (total_amount >= 0),
    payment_method       VARCHAR(30) NOT NULL
                         CHECK (payment_method IN ('card','cash','wallet','upi')),
    created_at           TIMESTAMP NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- order_items
-- ----------------------------------------------------------------------------
CREATE TABLE order_items (
    order_item_id   BIGSERIAL PRIMARY KEY,
    order_id        BIGINT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_name    VARCHAR(150) NOT NULL,
    category        VARCHAR(50) NOT NULL,
    unit_price      NUMERIC(10,2) NOT NULL CHECK (unit_price >= 0),
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    line_total      NUMERIC(10,2) GENERATED ALWAYS AS (unit_price * quantity) STORED,
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- deliveries: the logistics leg of an order, once a rider is assigned
-- ----------------------------------------------------------------------------
CREATE TABLE deliveries (
    delivery_id      BIGSERIAL PRIMARY KEY,
    order_id         BIGINT NOT NULL UNIQUE REFERENCES orders(order_id) ON DELETE CASCADE,
    rider_id         BIGINT NOT NULL REFERENCES riders(rider_id),
    assigned_at      TIMESTAMP NOT NULL,
    picked_up_at     TIMESTAMP,
    delivered_at     TIMESTAMP,
    -- mirrors the order-level granularity exactly (including out_for_delivery
    -- as its own stage) so delivery-service never has to map between two
    -- different vocabularies for the same real-world event.
    delivery_status  VARCHAR(20) NOT NULL DEFAULT 'assigned'
                     CHECK (delivery_status IN ('assigned','picked_up','out_for_delivery','delivered','failed')),
    distance_km      NUMERIC(6,2) CHECK (distance_km >= 0),
    created_at       TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT chk_pickup_after_assign
        CHECK (picked_up_at IS NULL OR picked_up_at >= assigned_at),
    CONSTRAINT chk_delivered_after_pickup
        CHECK (delivered_at IS NULL OR picked_up_at IS NULL OR delivered_at >= picked_up_at)
);

-- ----------------------------------------------------------------------------
-- order_status_history: append-only audit trail of order lifecycle transitions
-- (this is what the "order funnel" and stage-duration analysis are built from)
-- ----------------------------------------------------------------------------
CREATE TABLE order_status_history (
    history_id      BIGSERIAL PRIMARY KEY,
    order_id        BIGINT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    status          VARCHAR(20) NOT NULL
                    CHECK (status IN ('PLACED','CONFIRMED','PREPARING',
                                       'READY_FOR_PICKUP','RIDER_ASSIGNED',
                                       'PICKED_UP','OUT_FOR_DELIVERY',
                                       'DELIVERED','CANCELLED','FAILED')),
    changed_at      TIMESTAMP NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- event_log: raw landing table for incoming events (future Kafka consumer
-- target). order_id is nullable and event_type is unconstrained on purpose —
-- this table is expected to hold messy/raw data that data_quality/ cleans
-- into orders / order_status_history / deliveries.
-- ----------------------------------------------------------------------------
CREATE TABLE event_log (
    event_id         BIGSERIAL PRIMARY KEY,
    order_id         BIGINT REFERENCES orders(order_id) ON DELETE SET NULL,
    event_type       VARCHAR(50) NOT NULL,
    payload          JSONB,
    event_timestamp  TIMESTAMP NOT NULL,
    ingested_at      TIMESTAMP NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- processed_events: idempotency ledger for the live Kafka consumer(s) added
-- in the Kafka/Redis phase. Distinct from event_log above (which is the
-- data_generator's synthetic raw-event landing table, unrelated to this) —
-- event_id here is the producer-assigned UUID carried in the Kafka JSON
-- event envelope, not a DB-generated surrogate, since the whole point is
-- deduplicating on the id the producer already assigned once.
-- ----------------------------------------------------------------------------
CREATE TABLE processed_events (
    event_id        VARCHAR(64) PRIMARY KEY,
    event_type      VARCHAR(50) NOT NULL,
    order_id        BIGINT,
    consumer_group  VARCHAR(100) NOT NULL,
    processed_at    TIMESTAMP NOT NULL DEFAULT now()
);
