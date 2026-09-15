"""
Executive Overview - home page of the Order & Delivery Analytics dashboard.

Every number on this page is computed live from the oda_db PostgreSQL
database (see lib/data.py) and recalculated whenever the sidebar filters
change - nothing here is a hardcoded figure copied from reports/.
"""

import streamlit as st

from lib import charts, data
from lib.filters import filter_by_order_ids, filter_orders, sidebar_filters

st.set_page_config(page_title="Order & Delivery Analytics", layout="wide", page_icon="📦")

st.title("Order & Delivery Analytics")
st.caption(
    "Scalable Order & Delivery Analytics System - portfolio project. "
    "Data is synthetic (see data_generator/README.md); figures below are "
    "computed live from the database, not hardcoded."
)

try:
    orders = data.load_orders()
    delivery_facts = data.load_delivery_facts()
    status_history = data.load_status_history()
except Exception as exc:
    st.error(
        "Could not connect to the database (oda_db on localhost:5432). "
        "Make sure `docker compose up -d` is running and the dataset is "
        f"loaded. Details: {exc}"
    )
    st.stop()

start_date, end_date, cities, statuses = sidebar_filters(orders)
filtered = filter_orders(orders, start_date, end_date, cities, statuses)

if filtered.empty:
    st.warning("No orders match the current filter selection.")
    st.stop()

filtered_order_ids = filtered["order_id"]
filtered_delivery = filter_by_order_ids(delivery_facts, filtered_order_ids)
delivered = filtered_delivery.loc[filtered_delivery["delivery_status"] == "delivered"]

vol = data.metrics.order_volume_metrics(filtered)
customer_counts = data.customer_order_counts(filtered)
repeat = data.metrics.repeat_customer_rate(customer_counts) if len(customer_counts) else None
revenue = float(filtered.loc[filtered["status"] != "CANCELLED", "total_amount"].sum())

st.subheader("Key metrics")
row1 = st.columns(4)
row1[0].metric("Total Orders", f"{vol['total_orders']:,}")
row1[1].metric("Revenue", f"${revenue:,.2f}")
row1[2].metric("Completion Rate", f"{vol['completion_rate_pct']:.2f}%")
row1[3].metric("Cancellation Rate", f"{vol['cancellation_rate_pct']:.2f}%")

row2 = st.columns(4)
if len(delivered) > 0:
    dt_metrics = data.metrics.delivery_time_metrics(filtered_delivery)
    row2[0].metric("Avg Delivery Time", f"{dt_metrics['avg_delivery_minutes']:.1f} min")
    row2[1].metric("P90 Delivery Time", f"{dt_metrics['p90_delivery_minutes']:.1f} min")
    row2[2].metric(
        f"Late Delivery Rate (>{dt_metrics['assumed_sla_minutes']}min)",
        f"{dt_metrics['late_delivery_rate_pct']:.2f}%",
    )
else:
    for c in row2[:3]:
        c.metric("Delivery time", "n/a", help="No delivered orders in this selection")
if repeat is not None:
    row2[3].metric("Repeat Customer Rate", f"{repeat['repeat_customer_rate_pct']:.2f}%")
else:
    row2[3].metric("Repeat Customer Rate", "n/a")

st.caption(
    "Late Delivery Rate uses an illustrative 45-minute SLA (no real, "
    "business-approved SLA exists for this project) - see reports/business_insights.md."
)

st.divider()

col1, col2 = st.columns([3, 2])
with col1:
    daily = data.daily_stats(filtered)
    st.altair_chart(charts.order_trend_chart(daily), width="stretch")
with col2:
    funnel = data.order_funnel(status_history, filtered_order_ids)
    st.altair_chart(charts.order_funnel_chart(funnel), width="stretch")

city_perf = data.metrics.city_performance(data.city_summary(filtered))
st.altair_chart(charts.city_comparison_chart(city_perf), width="stretch")

with st.expander("City performance - full table"):
    st.dataframe(city_perf, width="stretch", hide_index=True)
