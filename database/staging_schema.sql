-- ============================================================================
-- Staging tables for bulk-loading data_generator/output/*.csv via \copy.
-- UNLOGGED (no WAL) since this is a disposable, one-time load — dropped by
-- load_generated_dataset.sql once the transform-insert into the real tables
-- is done. No constraints here on purpose: the CSVs carry the generator's
-- deliberately-injected data-quality issues (see data_generator/README.md),
-- and the transform step decides what to do with each one explicitly rather
-- than having COPY silently reject rows.
-- ============================================================================

DROP TABLE IF EXISTS staging_locations;
DROP TABLE IF EXISTS staging_customers;
DROP TABLE IF EXISTS staging_riders;
DROP TABLE IF EXISTS staging_orders;
DROP TABLE IF EXISTS staging_order_items;
DROP TABLE IF EXISTS staging_deliveries;
DROP TABLE IF EXISTS staging_order_status_history;
DROP TABLE IF EXISTS staging_event_log;

CREATE UNLOGGED TABLE staging_locations (
    location_id  BIGINT,
    address_line TEXT,
    city         TEXT,
    state        TEXT,
    postal_code  TEXT,
    latitude     NUMERIC,
    longitude    NUMERIC
);

CREATE UNLOGGED TABLE staging_customers (
    customer_id         BIGINT,
    first_name          TEXT,
    last_name           TEXT,
    email               TEXT,
    phone               TEXT,
    signup_date         DATE,
    default_location_id BIGINT
);

CREATE UNLOGGED TABLE staging_riders (
    rider_id     BIGINT,
    first_name   TEXT,
    last_name    TEXT,
    phone        TEXT,
    vehicle_type TEXT,
    city         TEXT,
    rating       NUMERIC,
    is_active    BOOLEAN,
    joined_date  DATE
);

CREATE UNLOGGED TABLE staging_orders (
    order_id             BIGINT,
    customer_id          BIGINT,
    delivery_location_id BIGINT,
    rider_id             BIGINT,
    status               TEXT,
    order_placed_at      TIMESTAMP,
    total_amount         NUMERIC,
    payment_method       TEXT
);

CREATE UNLOGGED TABLE staging_order_items (
    order_item_id BIGINT,
    order_id      BIGINT,
    product_name  TEXT,
    category      TEXT,
    unit_price    NUMERIC,
    quantity      INTEGER,
    line_total    NUMERIC
);

CREATE UNLOGGED TABLE staging_deliveries (
    delivery_id     BIGINT,
    order_id        BIGINT,
    rider_id        BIGINT,
    assigned_at     TIMESTAMP,
    picked_up_at    TIMESTAMP,
    delivered_at    TIMESTAMP,
    delivery_status TEXT,
    distance_km     NUMERIC
);

CREATE UNLOGGED TABLE staging_order_status_history (
    history_id BIGINT,
    order_id   BIGINT,
    status     TEXT,
    changed_at TIMESTAMP
);

CREATE UNLOGGED TABLE staging_event_log (
    event_id        BIGINT,
    order_id        BIGINT,
    event_type      TEXT,
    payload         TEXT,
    event_timestamp TIMESTAMP
);
