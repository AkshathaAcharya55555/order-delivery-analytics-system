"""
Cached data access for the dashboard.

Reuses analytics/scripts/db.py (connection) and analytics/scripts/metrics.py
(metric formulas) as the single source of truth for both the database
credentials and how each KPI is calculated - the dashboard does not
re-implement either. Only the SQL queries here are new, and only because the
dashboard needs city/status columns attached to every row so the sidebar
filters (date, city, order status) can be applied in pandas after one cached
load, instead of re-querying Postgres on every filter change.
"""

import os
import sys

import pandas as pd
import streamlit as st

_SCRIPTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "analytics", "scripts")
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import db as analytics_db  # noqa: E402  (path inserted above)
import metrics as analytics_metrics  # noqa: E402,F401  (re-exported below)

metrics = analytics_metrics  # re-export so pages do `from lib.data import metrics`

ORDERS_QUERY = """
SELECT
    o.order_id, o.customer_id, o.rider_id, o.status,
    o.order_placed_at, o.total_amount, o.payment_method,
    l.city
FROM orders o
JOIN locations l ON l.location_id = o.delivery_location_id
"""

DELIVERY_FACTS_QUERY = """
SELECT
    d.order_id,
    d.rider_id,
    r.city AS rider_city,
    l.city AS city,
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

STATUS_HISTORY_QUERY = """
SELECT order_id, status, changed_at
FROM order_status_history
"""

RIDERS_QUERY = """
SELECT rider_id, city, joined_date, rating, vehicle_type
FROM riders
"""


@st.cache_resource
def get_engine():
    return analytics_db.get_engine()


@st.cache_data(ttl=600)
def load_orders() -> pd.DataFrame:
    return pd.read_sql(ORDERS_QUERY, get_engine(), parse_dates=["order_placed_at"])


@st.cache_data(ttl=600)
def load_delivery_facts() -> pd.DataFrame:
    return pd.read_sql(
        DELIVERY_FACTS_QUERY,
        get_engine(),
        parse_dates=["order_placed_at", "assigned_at", "picked_up_at", "delivered_at"],
    )


@st.cache_data(ttl=600)
def load_status_history() -> pd.DataFrame:
    return pd.read_sql(STATUS_HISTORY_QUERY, get_engine(), parse_dates=["changed_at"])


@st.cache_data(ttl=600)
def load_riders() -> pd.DataFrame:
    return pd.read_sql(RIDERS_QUERY, get_engine(), parse_dates=["joined_date"])


@st.cache_data(ttl=600)
def load_quality_report() -> pd.DataFrame:
    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "data_quality", "quality_report.csv")
    )
    return pd.read_csv(path)


# ---------------------------------------------------------------------------
# Pure-pandas derivations from an already-filtered orders/delivery_facts
# DataFrame. Kept here (not in the pages) so every page composes the same
# aggregation logic instead of each re-deriving it slightly differently.
# Column names match what analytics/scripts/metrics.py expects, so its
# functions can be called directly on the output - no metric formula is
# re-implemented here, only the row-selection changes with the filters.
# ---------------------------------------------------------------------------


def daily_stats(orders: pd.DataFrame) -> pd.DataFrame:
    df = orders.copy()
    df["order_date"] = df["order_placed_at"].dt.floor("D")
    df["non_cancelled_amount"] = df["total_amount"].where(df["status"] != "CANCELLED", 0.0)
    df["is_cancelled"] = (df["status"] == "CANCELLED").astype(int)
    daily = df.groupby("order_date").agg(
        total_orders=("order_id", "count"),
        cancelled_orders=("is_cancelled", "sum"),
        revenue=("non_cancelled_amount", "sum"),
    ).reset_index()
    daily["cancellation_rate_pct"] = (100 * daily["cancelled_orders"] / daily["total_orders"]).round(2)
    return daily


def city_summary(orders: pd.DataFrame) -> pd.DataFrame:
    df = orders.copy()
    df["non_cancelled_amount"] = df["total_amount"].where(df["status"] != "CANCELLED", 0.0)
    return df.groupby("city").agg(
        total_orders=("order_id", "count"),
        cancelled_orders=("status", lambda s: int((s == "CANCELLED").sum())),
        delivered_orders=("status", lambda s: int((s == "DELIVERED").sum())),
        gross_revenue=("non_cancelled_amount", "sum"),
    ).reset_index()


def customer_order_counts(orders: pd.DataFrame) -> pd.DataFrame:
    non_cancelled = orders.loc[orders["status"] != "CANCELLED"]
    return non_cancelled.groupby("customer_id").size().reset_index(name="order_count")


def order_funnel(status_history: pd.DataFrame, order_ids) -> pd.DataFrame:
    stage_order = [
        "PLACED", "CONFIRMED", "PREPARING", "READY_FOR_PICKUP", "RIDER_ASSIGNED",
        "PICKED_UP", "OUT_FOR_DELIVERY", "DELIVERED",
    ]
    scoped = status_history.loc[status_history["order_id"].isin(order_ids)]
    counts = scoped.groupby("status")["order_id"].nunique()
    funnel = counts.reindex(stage_order).fillna(0).astype(int).reset_index()
    funnel.columns = ["status", "orders_reached"]
    return funnel


def rider_performance_table(
    riders: pd.DataFrame, delivery_facts_filtered: pd.DataFrame, cities: list
) -> pd.DataFrame:
    scoped = riders.loc[riders["city"].isin(cities)].copy()
    completed = (
        delivery_facts_filtered.loc[delivery_facts_filtered["delivery_status"] == "delivered"]
        .groupby("rider_id").size()
    )
    failed = (
        delivery_facts_filtered.loc[delivery_facts_filtered["delivery_status"] == "failed"]
        .groupby("rider_id").size()
    )
    scoped["completed_deliveries"] = scoped["rider_id"].map(completed).fillna(0).astype(int)
    scoped["failed_deliveries"] = scoped["rider_id"].map(failed).fillna(0).astype(int)
    return scoped


def stage_durations(status_history_filtered: pd.DataFrame) -> pd.DataFrame:
    """Average minutes an order spends at each lifecycle stage before its
    next recorded status change - same idea as analytics/sql query 16's
    'slowest funnel stage' finding, recomputed here from filtered data."""
    df = status_history_filtered.sort_values(["order_id", "changed_at"]).copy()
    df["next_time"] = df.groupby("order_id")["changed_at"].shift(-1)
    df["duration_min"] = (df["next_time"] - df["changed_at"]).dt.total_seconds() / 60.0
    valid = df.dropna(subset=["duration_min"])
    return (
        valid.groupby("status")["duration_min"]
        .mean()
        .round(2)
        .reset_index()
        .rename(columns={"duration_min": "avg_minutes"})
    )


def delivery_time_by_city(delivery_facts_filtered: pd.DataFrame) -> pd.DataFrame:
    delivered = delivery_facts_filtered.loc[delivery_facts_filtered["delivery_status"] == "delivered"].copy()
    if delivered.empty:
        return pd.DataFrame(columns=["city", "avg_minutes", "median_minutes", "p90_minutes"])
    delivered["minutes"] = (
        delivered["delivered_at"] - delivered["order_placed_at"]
    ).dt.total_seconds() / 60.0
    return (
        delivered.groupby("city")["minutes"]
        .agg(
            avg_minutes="mean",
            median_minutes="median",
            p90_minutes=lambda s: s.quantile(0.9),
        )
        .round(2)
        .reset_index()
    )


def rider_city_load(orders_filtered: pd.DataFrame, riders: pd.DataFrame, cities: list) -> pd.DataFrame:
    """Orders per active rider, by city - the metric behind the 'is rider
    supply proportional to demand' finding in reports/business_insights.md,
    recomputed here from whatever the current filters select."""
    orders_per_city = orders_filtered.groupby("city").size().rename("orders")
    riders_per_city = riders.loc[riders["city"].isin(cities)].groupby("city").size().rename("active_riders")
    out = pd.concat([orders_per_city, riders_per_city], axis=1).fillna(0).reset_index()
    out = out.rename(columns={"index": "city"})
    out["orders_per_rider"] = (out["orders"] / out["active_riders"].replace(0, pd.NA)).round(2)
    return out
