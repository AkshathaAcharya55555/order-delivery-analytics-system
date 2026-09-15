-- ============================================================================
-- Transforms staging_* tables (populated by \copy from data_generator/output/
-- *.csv) into the real schema, then drops the staging tables. Run only after
-- staging_schema.sql has been applied AND all 8 CSVs have been \copy'd in.
--
-- This REPLACES whatever is currently in the real tables (TRUNCATE ... CASCADE)
-- — i.e. it swaps database/seed.sql's small hand-written dataset out for the
-- full ~100k-order generated dataset. seed.sql itself is untouched and can
-- still be re-run later to restore the small dataset for quick schema checks.
--
-- Three known, disclosed transforms (see analytics/sql/README.md for the
-- full write-up of why these matter for the analytics layer):
--   1. Status vocabulary: the CSVs use the OLD 7-value lowercase status set
--      (generated before the backend-services phase expanded it to 10-value
--      uppercase). A plain UPPER() maps all 7 old values onto valid values
--      in the new set; RIDER_ASSIGNED/PICKED_UP never appear in this bulk
--      dataset since the generator never modeled them as distinct stages.
--   2. City normalization: data_generator intentionally injected ~2% messy
--      city-name variants into locations.city (case, whitespace, abbreviation,
--      state suffix) to demonstrate a data-quality issue. Every variant still
--      starts with the true city name's first 3 letters (that's how the
--      generator built them), so a prefix match recovers the canonical name.
--      Left un-normalized, city-grouped queries would fragment into spurious
--      extra groups.
--   3. Invalid deliveries excluded: ~1,842 delivery rows were intentionally
--      generated with delivered_at < picked_up_at (a simulated clock-skew
--      bug). These violate deliveries' own chk_delivered_after_pickup CHECK
--      constraint, so they are filtered out here rather than loaded — this
--      dataset is therefore the "clean" subset for delivery-timing analysis,
--      consistent with what a real data-quality gate would do before data
--      reaches an analytics layer. The excluded count is reported at the end
--      of this script so it's never silently lost.
-- ============================================================================

TRUNCATE TABLE event_log, order_status_history, deliveries, order_items,
              orders, riders, customers, locations
    RESTART IDENTITY CASCADE;

-- ----------------------------------------------------------------------------
-- locations (city normalization)
-- ----------------------------------------------------------------------------
INSERT INTO locations (location_id, address_line, city, state, postal_code, latitude, longitude)
SELECT
    location_id,
    address_line,
    CASE
        WHEN UPPER(TRIM(city)) LIKE 'AUS%' THEN 'Austin'
        WHEN UPPER(TRIM(city)) LIKE 'DEN%' THEN 'Denver'
        WHEN UPPER(TRIM(city)) LIKE 'POR%' THEN 'Portland'
        WHEN UPPER(TRIM(city)) LIKE 'CHI%' THEN 'Chicago'
        WHEN UPPER(TRIM(city)) LIKE 'MIA%' THEN 'Miami'
        WHEN UPPER(TRIM(city)) LIKE 'SEA%' THEN 'Seattle'
        ELSE TRIM(city)
    END,
    state, postal_code, latitude, longitude
FROM staging_locations;

SELECT setval('locations_location_id_seq', (SELECT MAX(location_id) FROM locations));

-- ----------------------------------------------------------------------------
-- customers
-- ----------------------------------------------------------------------------
INSERT INTO customers (customer_id, first_name, last_name, email, phone, signup_date, default_location_id)
SELECT customer_id, first_name, last_name, email, phone, signup_date, default_location_id
FROM staging_customers;

SELECT setval('customers_customer_id_seq', (SELECT MAX(customer_id) FROM customers));

-- ----------------------------------------------------------------------------
-- riders (is_available defaults true; no live GPS ping in the bulk dataset)
-- ----------------------------------------------------------------------------
INSERT INTO riders (rider_id, first_name, last_name, phone, vehicle_type, city, rating,
                     is_active, is_available, current_latitude, current_longitude, joined_date)
SELECT rider_id, first_name, last_name, phone, vehicle_type, city, rating,
       is_active, TRUE, NULL, NULL, joined_date
FROM staging_riders;

SELECT setval('riders_rider_id_seq', (SELECT MAX(rider_id) FROM riders));

-- ----------------------------------------------------------------------------
-- orders (status: old lowercase -> new uppercase vocabulary)
-- ----------------------------------------------------------------------------
INSERT INTO orders (order_id, customer_id, delivery_location_id, rider_id, status,
                     order_placed_at, total_amount, payment_method)
SELECT order_id, customer_id, delivery_location_id, rider_id, UPPER(status),
       order_placed_at, total_amount, payment_method
FROM staging_orders;

SELECT setval('orders_order_id_seq', (SELECT MAX(order_id) FROM orders));

-- ----------------------------------------------------------------------------
-- order_items (line_total is DB-generated; never inserted explicitly)
-- ----------------------------------------------------------------------------
INSERT INTO order_items (order_item_id, order_id, product_name, category, unit_price, quantity)
SELECT order_item_id, order_id, product_name, category, unit_price, quantity
FROM staging_order_items;

SELECT setval('order_items_order_item_id_seq', (SELECT MAX(order_item_id) FROM order_items));

-- ----------------------------------------------------------------------------
-- deliveries (excludes rows violating chk_delivered_after_pickup / chk_pickup_after_assign)
-- ----------------------------------------------------------------------------
INSERT INTO deliveries (delivery_id, order_id, rider_id, assigned_at, picked_up_at,
                         delivered_at, delivery_status, distance_km)
SELECT delivery_id, order_id, rider_id, assigned_at, picked_up_at,
       delivered_at, delivery_status, distance_km
FROM staging_deliveries
WHERE (delivered_at IS NULL OR picked_up_at IS NULL OR delivered_at >= picked_up_at)
  AND (picked_up_at IS NULL OR picked_up_at >= assigned_at);

SELECT setval('deliveries_delivery_id_seq', (SELECT MAX(delivery_id) FROM deliveries));

-- ----------------------------------------------------------------------------
-- order_status_history
-- ----------------------------------------------------------------------------
INSERT INTO order_status_history (history_id, order_id, status, changed_at)
SELECT history_id, order_id, UPPER(status), changed_at
FROM staging_order_status_history;

SELECT setval('order_status_history_history_id_seq', (SELECT MAX(history_id) FROM order_status_history));

-- ----------------------------------------------------------------------------
-- event_log (event_id is DB-generated; content duplicates from the generator
-- load as-is, matching how a real raw event stream would arrive)
-- ----------------------------------------------------------------------------
INSERT INTO event_log (order_id, event_type, payload, event_timestamp)
SELECT order_id, event_type, payload::jsonb, event_timestamp
FROM staging_event_log;

-- ----------------------------------------------------------------------------
-- Report what was excluded, then drop staging tables
-- ----------------------------------------------------------------------------
SELECT
    (SELECT count(*) FROM staging_deliveries) AS staged_deliveries,
    (SELECT count(*) FROM deliveries) AS loaded_deliveries,
    (SELECT count(*) FROM staging_deliveries) - (SELECT count(*) FROM deliveries) AS excluded_invalid_deliveries;

DROP TABLE staging_locations;
DROP TABLE staging_customers;
DROP TABLE staging_riders;
DROP TABLE staging_orders;
DROP TABLE staging_order_items;
DROP TABLE staging_deliveries;
DROP TABLE staging_order_status_history;
DROP TABLE staging_event_log;
