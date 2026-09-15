"""
SQL used for DB-side aggregation/joins. The rule of thumb followed
throughout this analytics layer: use SQL wherever it reduces row count
(GROUP BY collapsing 100k+ rows down to dozens/thousands) or expresses a
join naturally; pull row-level data into pandas only where the *shape* of
the further analysis (percentiles across a raw distribution, histograms,
combining several already-small tables) is what pandas is actually better
at than another round of SQL would be. See analytics/README.md for the
worked-through "why SQL here, why pandas there" explanation this project's
interview-prep goals ask for directly.
"""

import pandas as pd
from sqlalchemy.engine import Engine

ORDERS_QUERY = """
SELECT
    order_id, customer_id, delivery_location_id, rider_id,
    status, order_placed_at, total_amount, payment_method
FROM orders
"""

DELIVERY_FACTS_QUERY = """
-- One JOIN across deliveries/orders/locations/riders, done in SQL rather
-- than as three separate pandas merges, specifically because the row count
-- (91k) and the join keys are exactly what a database is for.
SELECT
    d.order_id,
    d.rider_id,
    r.city AS rider_city,
    l.city AS delivery_city,
    o.order_placed_at,
    d.assigned_at,
    d.picked_up_at,
    d.delivered_at,
    d.delivery_status,
    d.distance_km
FROM deliveries d
JOIN orders o ON o.order_id = d.order_id
JOIN locations l ON l.location_id = o.delivery_location_id
JOIN riders r ON r.rider_id = d.rider_id
"""

DAILY_ORDER_COUNTS_QUERY = """
-- DB-side aggregation: collapses 100,000 order rows down to 90 daily rows
-- before anything ever reaches pandas.
SELECT DATE(order_placed_at) AS order_date, COUNT(*) AS total_orders
FROM orders
GROUP BY DATE(order_placed_at)
ORDER BY order_date
"""

CITY_SUMMARY_QUERY = """
SELECT
    l.city,
    COUNT(*) AS total_orders,
    SUM(CASE WHEN o.status = 'CANCELLED' THEN 1 ELSE 0 END) AS cancelled_orders,
    SUM(CASE WHEN o.status = 'DELIVERED' THEN 1 ELSE 0 END) AS delivered_orders,
    ROUND(SUM(CASE WHEN o.status <> 'CANCELLED' THEN o.total_amount ELSE 0 END), 2) AS gross_revenue
FROM orders o
JOIN locations l ON l.location_id = o.delivery_location_id
GROUP BY l.city
"""

RIDER_DELIVERY_COUNTS_QUERY = """
-- Collapses 91k delivery rows down to one row per rider (2,000) before
-- rider-level utilization math happens in pandas.
SELECT
    r.rider_id,
    r.city,
    r.joined_date,
    COUNT(d.delivery_id) FILTER (WHERE d.delivery_status = 'delivered') AS completed_deliveries,
    COUNT(d.delivery_id) FILTER (WHERE d.delivery_status = 'failed') AS failed_deliveries
FROM riders r
LEFT JOIN deliveries d ON d.rider_id = r.rider_id
GROUP BY r.rider_id, r.city, r.joined_date
"""

CUSTOMER_ORDER_COUNTS_QUERY = """
SELECT customer_id, COUNT(*) AS order_count
FROM orders
WHERE status <> 'CANCELLED'
GROUP BY customer_id
"""


def fetch_orders(engine: Engine) -> pd.DataFrame:
    return pd.read_sql(ORDERS_QUERY, engine, parse_dates=["order_placed_at"])


def fetch_delivery_facts(engine: Engine) -> pd.DataFrame:
    return pd.read_sql(
        DELIVERY_FACTS_QUERY, engine,
        parse_dates=["order_placed_at", "assigned_at", "picked_up_at", "delivered_at"]
    )


def fetch_daily_order_counts(engine: Engine) -> pd.DataFrame:
    return pd.read_sql(DAILY_ORDER_COUNTS_QUERY, engine, parse_dates=["order_date"])


def fetch_city_summary(engine: Engine) -> pd.DataFrame:
    return pd.read_sql(CITY_SUMMARY_QUERY, engine)


def fetch_rider_delivery_counts(engine: Engine) -> pd.DataFrame:
    return pd.read_sql(RIDER_DELIVERY_COUNTS_QUERY, engine, parse_dates=["joined_date"])


def fetch_customer_order_counts(engine: Engine) -> pd.DataFrame:
    return pd.read_sql(CUSTOMER_ORDER_COUNTS_QUERY, engine)
