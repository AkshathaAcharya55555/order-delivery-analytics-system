"""
Metric calculations — the pandas/NumPy half of the "SQL vs pandas" split.

Each function takes a DataFrame already pulled (and, where it mattered,
pre-aggregated) via queries.py and computes one or more of the specific
metrics this project's analytics phase was asked for. Percentiles, medians,
and rate calculations are done here with pandas/NumPy rather than repeating
them as more SQL, since these DataFrames are already small enough that
vectorized pandas operations are simpler to read and to unit-test than
another layer of SQL would be.
"""

import numpy as np
import pandas as pd

# Documented, not measured: no real SLA exists for this project, so an
# illustrative threshold is used and labeled as such everywhere it appears —
# same value and same caveat as analytics/sql/README.md's query 11.
ASSUMED_SLA_MINUTES = 45


def order_volume_metrics(orders: pd.DataFrame) -> dict:
    total_orders = len(orders)
    status_counts = orders["status"].value_counts()
    completed_orders = int(status_counts.get("DELIVERED", 0))
    cancelled_orders = int(status_counts.get("CANCELLED", 0))
    in_progress_orders = total_orders - completed_orders - cancelled_orders

    return {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders,
        "in_progress_orders": in_progress_orders,
        "completion_rate_pct": round(100 * completed_orders / total_orders, 2),
        "cancellation_rate_pct": round(100 * cancelled_orders / total_orders, 2),
        "in_progress_rate_pct": round(100 * in_progress_orders / total_orders, 2),
    }


def order_value_metrics(orders: pd.DataFrame) -> dict:
    non_cancelled = orders.loc[orders["status"] != "CANCELLED", "total_amount"]
    return {
        "avg_order_value": round(float(non_cancelled.mean()), 2),
        "median_order_value": round(float(non_cancelled.median()), 2),
    }


def _delivery_minutes(delivery_facts: pd.DataFrame) -> pd.Series:
    delivered = delivery_facts.loc[delivery_facts["delivery_status"] == "delivered"].copy()
    minutes = (delivered["delivered_at"] - delivered["order_placed_at"]).dt.total_seconds() / 60.0
    return minutes


def delivery_time_metrics(delivery_facts: pd.DataFrame) -> dict:
    minutes = _delivery_minutes(delivery_facts)
    late = (minutes > ASSUMED_SLA_MINUTES).sum()
    return {
        "avg_delivery_minutes": round(float(minutes.mean()), 2),
        "median_delivery_minutes": round(float(minutes.median()), 2),
        # np.percentile and pandas' .quantile() agree by construction (same
        # linear-interpolation method); computed via NumPy here explicitly
        # since "P90" was asked for as its own named metric.
        "p90_delivery_minutes": round(float(np.percentile(minutes, 90)), 2),
        "assumed_sla_minutes": ASSUMED_SLA_MINUTES,
        "late_delivery_rate_pct": round(100 * late / len(minutes), 2),
        "delivered_sample_size": int(len(minutes)),
    }


def rider_utilization_metrics(rider_counts: pd.DataFrame, as_of_date) -> pd.DataFrame:
    """
    Returns a per-rider utilization DataFrame (deliveries per day active).
    as_of_date should be the dataset's own latest order date, NOT the real
    "today" — this is historical synthetic data, so using the real current
    date would make every rider look almost entirely idle. Same reasoning as
    analytics/sql/12_rider_utilization.sql.
    """
    df = rider_counts.copy()
    df["days_active"] = (pd.Timestamp(as_of_date) - df["joined_date"]).dt.days.clip(lower=1)
    df["deliveries_per_day"] = (df["completed_deliveries"] / df["days_active"]).round(3)
    return df.sort_values("deliveries_per_day", ascending=False)


def repeat_customer_rate(customer_order_counts: pd.DataFrame) -> dict:
    total_customers = len(customer_order_counts)
    repeat_customers = int((customer_order_counts["order_count"] >= 2).sum())
    return {
        "total_ordering_customers": total_customers,
        "repeat_customers": repeat_customers,
        "repeat_customer_rate_pct": round(100 * repeat_customers / total_customers, 2),
    }


def city_performance(city_summary: pd.DataFrame) -> pd.DataFrame:
    df = city_summary.copy()
    df["cancellation_rate_pct"] = (100 * df["cancelled_orders"] / df["total_orders"]).round(2)
    df["completion_rate_pct"] = (100 * df["delivered_orders"] / df["total_orders"]).round(2)
    return df.sort_values("total_orders", ascending=False)
