-- ============================================================================
-- Indexes beyond what PRIMARY KEY / UNIQUE constraints already create.
-- Postgres does NOT auto-index foreign key columns, so those are added
-- explicitly here for the join and filter patterns the analytics layer uses.
-- Run after schema.sql.
-- ============================================================================

-- locations
CREATE INDEX idx_locations_city ON locations(city);

-- customers
CREATE INDEX idx_customers_default_location_id ON customers(default_location_id);

-- riders
CREATE INDEX idx_riders_city ON riders(city);

-- orders: filtered/joined constantly by these columns in KPI queries
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_rider_id ON orders(rider_id);
CREATE INDEX idx_orders_delivery_location_id ON orders(delivery_location_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_order_placed_at ON orders(order_placed_at);

-- order_items
CREATE INDEX idx_order_items_order_id ON order_items(order_id);

-- deliveries
CREATE INDEX idx_deliveries_rider_id ON deliveries(rider_id);
CREATE INDEX idx_deliveries_delivery_status ON deliveries(delivery_status);

-- order_status_history: (status, changed_at) supports funnel + time-in-stage queries
CREATE INDEX idx_order_status_history_order_id ON order_status_history(order_id);
CREATE INDEX idx_order_status_history_status_changed_at
    ON order_status_history(status, changed_at);

-- event_log
CREATE INDEX idx_event_log_order_id ON event_log(order_id);
CREATE INDEX idx_event_log_event_type ON event_log(event_type);
CREATE INDEX idx_event_log_event_timestamp ON event_log(event_timestamp);

-- processed_events (Kafka consumer idempotency ledger)
CREATE INDEX idx_processed_events_order_id ON processed_events(order_id);
