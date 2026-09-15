"""
Matplotlib chart generation. Each function saves one PNG and returns the
path — kept separate from metrics.py so charts can be regenerated without
recomputing metrics, and vice versa.
"""

import os

import matplotlib
matplotlib.use("Agg")  # headless: this runs from a script/CI, not a GUI session
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _save(fig, out_dir: str, filename: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def order_trend_chart(daily_counts: pd.DataFrame, out_dir: str) -> str:
    df = daily_counts.sort_values("order_date").copy()
    df["rolling_7day"] = df["total_orders"].rolling(7, min_periods=1).mean()

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(df["order_date"], df["total_orders"], color="#9fb3c8", linewidth=1, label="Daily orders")
    ax.plot(df["order_date"], df["rolling_7day"], color="#2b6cb0", linewidth=2, label="7-day rolling avg")
    ax.set_title("Daily Order Volume")
    ax.set_xlabel("Date")
    ax.set_ylabel("Orders")
    ax.legend()
    fig.autofmt_xdate()
    return _save(fig, out_dir, "order_trend.png")


def delivery_time_histogram(minutes: pd.Series, sla_minutes: float, out_dir: str) -> str:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(minutes, bins=40, color="#4a7c59", alpha=0.85)
    ax.axvline(sla_minutes, color="#c0392b", linestyle="--", linewidth=2,
               label=f"Assumed SLA ({sla_minutes} min)")
    ax.axvline(minutes.median(), color="#333333", linestyle=":", linewidth=2,
               label=f"Median ({minutes.median():.1f} min)")
    ax.set_title("Delivery Time Distribution")
    ax.set_xlabel("Minutes (order placed -> delivered)")
    ax.set_ylabel("Number of deliveries")
    ax.legend()
    return _save(fig, out_dir, "delivery_time_histogram.png")


def city_performance_chart(city_perf: pd.DataFrame, out_dir: str) -> str:
    df = city_perf.sort_values("total_orders", ascending=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    ax1.barh(df["city"], df["total_orders"], color="#2b6cb0")
    ax1.set_title("Total Orders by City")
    ax1.set_xlabel("Orders")

    ax2.barh(df["city"], df["cancellation_rate_pct"], color="#c0392b")
    ax2.set_title("Cancellation Rate by City")
    ax2.set_xlabel("Cancellation rate (%)")

    fig.tight_layout()
    return _save(fig, out_dir, "city_performance.png")


def peak_hours_chart(orders: pd.DataFrame, out_dir: str) -> str:
    hours = orders["order_placed_at"].dt.hour.value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(hours.index, hours.values, color="#7a5195")
    ax.set_title("Orders by Hour of Day")
    ax.set_xlabel("Hour (0-23)")
    ax.set_ylabel("Orders")
    ax.set_xticks(range(0, 24, 2))
    return _save(fig, out_dir, "peak_hours.png")


def rider_utilization_chart(rider_util: pd.DataFrame, out_dir: str, top_n: int = 20) -> str:
    df = rider_util.head(top_n).iloc[::-1]  # reverse so #1 is at the top of the barh
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(df["rider_id"].astype(str), df["deliveries_per_day"], color="#f4a259")
    ax.set_title(f"Top {top_n} Riders by Deliveries/Day")
    ax.set_xlabel("Deliveries per day active")
    ax.set_ylabel("Rider ID")
    return _save(fig, out_dir, "rider_utilization.png")


def customer_frequency_chart(customer_counts: pd.DataFrame, out_dir: str) -> str:
    dist = customer_counts["order_count"].value_counts().sort_index()
    dist = dist[dist.index <= 15]  # long tail beyond 15 orders is a handful of customers; not useful to plot
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(dist.index, dist.values, color="#118ab2")
    ax.set_title("Customer Order Frequency (capped at 15 orders for readability)")
    ax.set_xlabel("Orders placed")
    ax.set_ylabel("Number of customers")
    return _save(fig, out_dir, "customer_frequency.png")
