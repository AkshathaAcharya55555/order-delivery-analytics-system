"""
Main entry point for the Python analytics layer. Connects to the live
oda_db database (the same one analytics/sql/ queries — the full generated
~100k-order dataset, not the small seed sample), computes every metric
requested for this phase, generates charts, and prints a plain-text summary.

The numbers this script prints are the ONLY source for reports/business_insights.md
— nothing in that report was hand-typed or estimated separately from an
actual run of this script.

Run: python analytics/scripts/run_eda.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import db
import queries
import metrics
import charts

CHARTS_DIR = os.path.join(os.path.dirname(__file__), "..", "charts")


def main():
    engine = db.get_engine()

    print("Loading data from Postgres...")
    orders = queries.fetch_orders(engine)
    delivery_facts = queries.fetch_delivery_facts(engine)
    daily_counts = queries.fetch_daily_order_counts(engine)
    city_summary = queries.fetch_city_summary(engine)
    rider_counts = queries.fetch_rider_delivery_counts(engine)
    customer_counts = queries.fetch_customer_order_counts(engine)
    print(f"  orders: {len(orders):,} rows | delivery_facts: {len(delivery_facts):,} rows "
          f"| riders: {len(rider_counts):,} rows | customers with orders: {len(customer_counts):,} rows")

    print("\n=== ORDER VOLUME ===")
    vol = metrics.order_volume_metrics(orders)
    for k, v in vol.items():
        print(f"  {k}: {v}")

    print("\n=== ORDER VALUE ===")
    val = metrics.order_value_metrics(orders)
    for k, v in val.items():
        print(f"  {k}: {v}")

    print("\n=== DELIVERY PERFORMANCE ===")
    dt = metrics.delivery_time_metrics(delivery_facts)
    for k, v in dt.items():
        print(f"  {k}: {v}")

    print("\n=== REPEAT CUSTOMERS ===")
    rc = metrics.repeat_customer_rate(customer_counts)
    for k, v in rc.items():
        print(f"  {k}: {v}")

    print("\n=== CITY PERFORMANCE ===")
    city_perf = metrics.city_performance(city_summary)
    print(city_perf.to_string(index=False))

    print("\n=== RIDER UTILIZATION (top 10) ===")
    as_of_date = orders["order_placed_at"].max().date()
    rider_util = metrics.rider_utilization_metrics(rider_counts, as_of_date)
    print(f"  (as_of_date used for 'days_active': {as_of_date})")
    print(rider_util.head(10).to_string(index=False))

    print("\nGenerating charts...")
    minutes = metrics._delivery_minutes(delivery_facts)
    paths = [
        charts.order_trend_chart(daily_counts, CHARTS_DIR),
        charts.delivery_time_histogram(minutes, dt["assumed_sla_minutes"], CHARTS_DIR),
        charts.city_performance_chart(city_perf, CHARTS_DIR),
        charts.peak_hours_chart(orders, CHARTS_DIR),
        charts.rider_utilization_chart(rider_util, CHARTS_DIR),
        charts.customer_frequency_chart(customer_counts, CHARTS_DIR),
    ]
    for p in paths:
        print(f"  saved: {p}")

    print("\nDone.")


if __name__ == "__main__":
    main()
