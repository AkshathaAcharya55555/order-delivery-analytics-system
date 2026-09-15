"""Delivery Performance - delivery-time distribution, by-city comparison,
and lifecycle stage durations (all recomputed from the current filters)."""

import streamlit as st

from lib import charts, data
from lib.filters import filter_by_order_ids, filter_orders, sidebar_filters

st.set_page_config(page_title="Delivery Performance", layout="wide", page_icon="📦")
st.title("Delivery Performance")

try:
    orders = data.load_orders()
    delivery_facts = data.load_delivery_facts()
    status_history = data.load_status_history()
except Exception as exc:
    st.error(f"Could not connect to the database: {exc}")
    st.stop()

start_date, end_date, cities, statuses = sidebar_filters(orders)
filtered = filter_orders(orders, start_date, end_date, cities, statuses)

if filtered.empty:
    st.warning("No orders match the current filter selection.")
    st.stop()

filtered_order_ids = filtered["order_id"]
filtered_delivery = filter_by_order_ids(delivery_facts, filtered_order_ids)
delivered = filtered_delivery.loc[filtered_delivery["delivery_status"] == "delivered"]

if delivered.empty:
    st.warning("No delivered orders match the current filter selection.")
    st.stop()

dt_metrics = data.metrics.delivery_time_metrics(filtered_delivery)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Avg Delivery Time", f"{dt_metrics['avg_delivery_minutes']:.1f} min")
c2.metric("Median Delivery Time", f"{dt_metrics['median_delivery_minutes']:.1f} min")
c3.metric("P90 Delivery Time", f"{dt_metrics['p90_delivery_minutes']:.1f} min")
c4.metric(
    f"Late Delivery Rate (>{dt_metrics['assumed_sla_minutes']}min)",
    f"{dt_metrics['late_delivery_rate_pct']:.2f}%",
)
st.caption(
    "The SLA threshold above is illustrative (45 minutes) - no real, "
    "business-approved SLA exists for this project."
)

minutes = data.metrics._delivery_minutes(filtered_delivery)
st.altair_chart(
    charts.delivery_time_histogram(minutes, dt_metrics["assumed_sla_minutes"]),
    width="stretch",
)

by_city = data.delivery_time_by_city(filtered_delivery)
if not by_city.empty:
    st.altair_chart(charts.delivery_time_by_city_chart(by_city), width="stretch")

durations = data.stage_durations(status_history.loc[status_history["order_id"].isin(filtered_order_ids)])
if not durations.empty:
    st.altair_chart(charts.stage_duration_chart(durations), width="stretch")
    st.caption(
        "Average minutes between an order entering a stage and its next "
        "recorded status change, for orders in the current selection."
    )
