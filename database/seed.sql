-- ============================================================================
-- Small, hand-written sample dataset for validating schema.sql / indexes.sql
-- / views.sql. This is NOT the synthetic dataset used for the analytics
-- phase (that will come from data_generator/ later, with much larger,
-- programmatically generated volume). This file exists purely to prove the
-- schema is correct and the views return sensible results.
--
-- Safe to re-run: truncates all tables and resets identities first.
-- ============================================================================

TRUNCATE TABLE event_log, order_status_history, deliveries, order_items,
              orders, riders, customers, locations
    RESTART IDENTITY CASCADE;

-- ----------------------------------------------------------------------------
-- locations (1-5)
-- ----------------------------------------------------------------------------
INSERT INTO locations (address_line, city, state, postal_code, latitude, longitude) VALUES
('100 Congress Ave', 'Austin',   'TX', '78701', 30.267200, -97.743100),
('250 East 6th St',  'Austin',   'TX', '78701', 30.267500, -97.739000),
('1600 Larimer St',  'Denver',   'CO', '80202', 39.749800, -104.999500),
('900 16th St',      'Denver',   'CO', '80202', 39.746600, -104.998900),
('500 SW Broadway',  'Portland', 'OR', '97205', 45.520500, -122.679500);

-- ----------------------------------------------------------------------------
-- customers (1-5)
-- ----------------------------------------------------------------------------
INSERT INTO customers (first_name, last_name, email, phone, signup_date, default_location_id) VALUES
('Alice', 'Johnson', 'alice.johnson@example.com', '512-555-0101', '2025-01-15', 1),
('Bob',   'Smith',   'bob.smith@example.com',     '512-555-0102', '2025-02-02', 2),
('Carla', 'Diaz',    'carla.diaz@example.com',    '720-555-0103', '2025-01-28', 3),
('David', 'Lee',     'david.lee@example.com',     '720-555-0104', '2025-03-10', 4),
('Emma',  'Wilson',  'emma.wilson@example.com',   '503-555-0105', '2025-02-20', 5);

-- ----------------------------------------------------------------------------
-- riders (1-5)
-- ----------------------------------------------------------------------------
INSERT INTO riders (first_name, last_name, phone, vehicle_type, city, rating, is_active, joined_date) VALUES
('Frank', 'Miller', '512-555-0201', 'bike',    'Austin',   4.6, TRUE, '2024-11-01'),
('Grace', 'Kim',    '512-555-0202', 'scooter', 'Austin',   4.8, TRUE, '2024-10-15'),
('Hassan','Ali',    '720-555-0203', 'car',     'Denver',   4.2, TRUE, '2024-12-01'),
('Irene', 'Chen',   '720-555-0204', 'bike',    'Denver',   4.9, TRUE, '2025-01-05'),
('Jack',  'Brown',  '503-555-0205', 'scooter', 'Portland', 4.0, TRUE, '2024-09-20');

-- ----------------------------------------------------------------------------
-- orders (1-8)
-- ----------------------------------------------------------------------------
INSERT INTO orders (customer_id, delivery_location_id, rider_id, status, order_placed_at, total_amount, payment_method) VALUES
(1, 1, 1, 'DELIVERED',        '2025-06-01 08:00:00', 23.50, 'card'),
(2, 2, 2, 'DELIVERED',        '2025-06-01 12:10:00', 18.50, 'upi'),
(3, 3, 3, 'DELIVERED',        '2025-06-02 18:00:00', 17.00, 'cash'),
(4, 4, 4, 'DELIVERED',        '2025-06-03 09:30:00', 11.50, 'card'),
(5, 5, NULL, 'CANCELLED',     '2025-06-03 14:00:00',  9.00, 'wallet'),
(1, 1, 2, 'DELIVERED',        '2025-06-05 19:00:00', 17.00, 'card'),
(2, 2, 2, 'OUT_FOR_DELIVERY', '2025-06-10 20:00:00', 13.00, 'upi'),
(5, 5, 5, 'DELIVERED',        '2025-06-06 11:00:00', 12.00, 'cash');

-- ----------------------------------------------------------------------------
-- order_items
-- ----------------------------------------------------------------------------
INSERT INTO order_items (order_id, product_name, category, unit_price, quantity) VALUES
-- order 1
(1, 'Cheeseburger', 'main',    8.50, 2),
(1, 'Fries',        'side',    4.00, 1),
(1, 'Soda',         'drink',   2.50, 1),
-- order 2
(2, 'Pizza Slice',  'main',   12.00, 1),
(2, 'Chicken Wings','side',    6.50, 1),
-- order 3
(3, 'Taco Plate',   'main',   10.00, 1),
(3, 'Churros',      'dessert', 3.50, 2),
-- order 4
(4, 'Bagel',        'main',    3.00, 2),
(4, 'Coffee',       'drink',   2.75, 2),
-- order 5 (cancelled)
(5, 'Garden Salad', 'main',    9.00, 1),
-- order 6
(6, 'Pizza Slice',  'main',   12.00, 1),
(6, 'Soda',         'drink',   2.50, 2),
-- order 7 (in progress)
(7, 'Chicken Wings','side',    6.50, 2),
-- order 8
(8, 'Sandwich',     'main',    7.50, 1),
(8, 'Chips',        'side',    2.00, 1),
(8, 'Soda',         'drink',   2.50, 1);

-- ----------------------------------------------------------------------------
-- deliveries (only for orders that reached at least 'READY_FOR_PICKUP').
-- delivery_status is a separate, narrower enum scoped to this table only
-- (assigned/picked_up/delivered/failed) — it was NOT changed to uppercase.
-- ----------------------------------------------------------------------------
INSERT INTO deliveries (order_id, rider_id, assigned_at, picked_up_at, delivered_at, delivery_status, distance_km) VALUES
(1, 1, '2025-06-01 08:22:00', '2025-06-01 08:26:00', '2025-06-01 08:50:00', 'delivered', 3.2),
(2, 2, '2025-06-01 12:31:00', '2025-06-01 12:34:00', '2025-06-01 12:55:00', 'delivered', 2.1),
(3, 3, '2025-06-02 18:26:00', '2025-06-02 18:29:00', '2025-06-02 19:05:00', 'delivered', 5.4),
(4, 4, '2025-06-03 09:46:00', '2025-06-03 09:49:00', '2025-06-03 10:05:00', 'delivered', 1.8),
(6, 2, '2025-06-05 19:21:00', '2025-06-05 19:24:00', '2025-06-05 19:50:00', 'delivered', 2.9),
(7, 2, '2025-06-10 20:21:00', '2025-06-10 20:24:00', NULL,                  'picked_up', 2.1),
(8, 5, '2025-06-06 11:19:00', '2025-06-06 11:21:00', '2025-06-06 11:55:00', 'delivered', 4.0);

-- ----------------------------------------------------------------------------
-- order_status_history (full lifecycle trace per order)
-- ----------------------------------------------------------------------------
INSERT INTO order_status_history (order_id, status, changed_at) VALUES
-- order 1
(1, 'PLACED',            '2025-06-01 08:00:00'),
(1, 'CONFIRMED',         '2025-06-01 08:03:00'),
(1, 'PREPARING',         '2025-06-01 08:05:00'),
(1, 'READY_FOR_PICKUP',  '2025-06-01 08:20:00'),
(1, 'OUT_FOR_DELIVERY',  '2025-06-01 08:25:00'),
(1, 'DELIVERED',         '2025-06-01 08:50:00'),
-- order 2
(2, 'PLACED',            '2025-06-01 12:10:00'),
(2, 'CONFIRMED',         '2025-06-01 12:12:00'),
(2, 'PREPARING',         '2025-06-01 12:15:00'),
(2, 'READY_FOR_PICKUP',  '2025-06-01 12:30:00'),
(2, 'OUT_FOR_DELIVERY',  '2025-06-01 12:33:00'),
(2, 'DELIVERED',         '2025-06-01 12:55:00'),
-- order 3
(3, 'PLACED',            '2025-06-02 18:00:00'),
(3, 'CONFIRMED',         '2025-06-02 18:04:00'),
(3, 'PREPARING',         '2025-06-02 18:06:00'),
(3, 'READY_FOR_PICKUP',  '2025-06-02 18:25:00'),
(3, 'OUT_FOR_DELIVERY',  '2025-06-02 18:28:00'),
(3, 'DELIVERED',         '2025-06-02 19:05:00'),
-- order 4
(4, 'PLACED',            '2025-06-03 09:30:00'),
(4, 'CONFIRMED',         '2025-06-03 09:32:00'),
(4, 'PREPARING',         '2025-06-03 09:34:00'),
(4, 'READY_FOR_PICKUP',  '2025-06-03 09:45:00'),
(4, 'OUT_FOR_DELIVERY',  '2025-06-03 09:48:00'),
(4, 'DELIVERED',         '2025-06-03 10:05:00'),
-- order 5 (cancelled early)
(5, 'PLACED',            '2025-06-03 14:00:00'),
(5, 'CONFIRMED',         '2025-06-03 14:02:00'),
(5, 'CANCELLED',         '2025-06-03 14:10:00'),
-- order 6
(6, 'PLACED',            '2025-06-05 19:00:00'),
(6, 'CONFIRMED',         '2025-06-05 19:03:00'),
(6, 'PREPARING',         '2025-06-05 19:05:00'),
(6, 'READY_FOR_PICKUP',  '2025-06-05 19:20:00'),
(6, 'OUT_FOR_DELIVERY',  '2025-06-05 19:23:00'),
(6, 'DELIVERED',         '2025-06-05 19:50:00'),
-- order 7 (still in progress as of seed time)
(7, 'PLACED',            '2025-06-10 20:00:00'),
(7, 'CONFIRMED',         '2025-06-10 20:02:00'),
(7, 'PREPARING',         '2025-06-10 20:04:00'),
(7, 'READY_FOR_PICKUP',  '2025-06-10 20:20:00'),
(7, 'OUT_FOR_DELIVERY',  '2025-06-10 20:23:00'),
-- order 8
(8, 'PLACED',            '2025-06-06 11:00:00'),
(8, 'CONFIRMED',         '2025-06-06 11:03:00'),
(8, 'PREPARING',         '2025-06-06 11:05:00'),
(8, 'READY_FOR_PICKUP',  '2025-06-06 11:18:00'),
(8, 'OUT_FOR_DELIVERY',  '2025-06-06 11:20:00'),
(8, 'DELIVERED',         '2025-06-06 11:55:00');

-- ----------------------------------------------------------------------------
-- event_log: raw event stream landing table.
-- Rows 1-8 mirror clean "order_placed" events. Rows 9-10 are deliberately
-- messy (a duplicate event and one with no resolvable order_id) to reflect
-- the kind of raw data the future Kafka consumer will actually produce and
-- that the data_quality pipeline (a later phase) is meant to catch.
-- ----------------------------------------------------------------------------
INSERT INTO event_log (order_id, event_type, payload, event_timestamp) VALUES
(1, 'order_placed', '{"source": "mobile_app", "order_id": 1}'::jsonb, '2025-06-01 08:00:00'),
(2, 'order_placed', '{"source": "web", "order_id": 2}'::jsonb,        '2025-06-01 12:10:00'),
(3, 'order_placed', '{"source": "mobile_app", "order_id": 3}'::jsonb, '2025-06-02 18:00:00'),
(4, 'order_placed', '{"source": "web", "order_id": 4}'::jsonb,        '2025-06-03 09:30:00'),
(5, 'order_placed', '{"source": "mobile_app", "order_id": 5}'::jsonb, '2025-06-03 14:00:00'),
(5, 'order_cancelled', '{"reason": "customer_requested", "order_id": 5}'::jsonb, '2025-06-03 14:10:00'),
(6, 'order_placed', '{"source": "mobile_app", "order_id": 6}'::jsonb, '2025-06-05 19:00:00'),
(8, 'order_placed', '{"source": "web", "order_id": 8}'::jsonb,        '2025-06-06 11:00:00'),
-- duplicate event (same order/type/timestamp sent twice — e.g. Kafka at-least-once delivery)
(1, 'order_placed', '{"source": "mobile_app", "order_id": 1}'::jsonb, '2025-06-01 08:00:00'),
-- malformed event: no resolvable order_id (upstream producer bug)
(NULL, 'order_placed', '{"source": "mobile_app", "order_id": null}'::jsonb, '2025-06-07 10:00:00');
