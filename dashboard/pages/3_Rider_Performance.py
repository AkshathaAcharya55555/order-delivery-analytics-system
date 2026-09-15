"""Rider Performance - utilization leaderboard and rider load by city."""

import streamlit as st

from lib import charts, data
from lib.filters import filter_by_order_ids, filter_orders, sidebar_filters

st.set_page_config(page_title="Rider Performance", layout="wide", page_icon="📦")
st.title("Rider Performance")

try:
    orders = data.load_orders()
    delivery_facts = data.load_delivery_facts()
    riders = data.load_riders()
except Exception as exc:
    st.error(f"Could not connect to the database: {exc}")
    st.stop()

start_date, end_date, cities, statuses = sidebar_filters(orders)
filtered = filter_orders(orders, start_date, end_date, cities, statuses)

if filtered.empty:
    st.warning("No orders match the current filter selection.")
    st.stop()

filtered_delivery = filter_by_order_ids(delivery_facts, filtered["order_id"])

rider_table = data.rider_performance_table(riders, filtered_delivery, cities)
as_of_date = filtered["order_placed_at"].max().date()
rider_util = data.metrics.rider_utilization_metrics(rider_table, as_of_date)

c1, c2, c3 = st.columns(3)
c1.metric("Active Riders (selected cities)", f"{len(rider_table):,}")
c2.metric("Total Completed Deliveries", f"{int(rider_table['completed_deliveries'].sum()):,}")
c3.metric("Total Failed Deliveries", f"{int(rider_table['failed_deliveries'].sum()):,}")
st.caption(
    "'Deliveries per day active' uses the dataset's own latest order date as "
    "'today' (this is historical synthetic data). A handful of riders whose "
    "generated join date happens to fall very close to that date can show an "
    "unrealistically high rate - a known synthetic-data artifact, disclosed "
    "in reports/business_insights.md rather than hidden."
)

st.altair_chart(charts.rider_performance_chart(rider_util, top_n=20), width="stretch")

city_load = data.rider_city_load(filtered, riders, cities)
if not city_load.empty:
    st.altair_chart(charts.rider_city_load_chart(city_load), width="stretch")

with st.expander("Full rider table"):
    st.dataframe(
        rider_util[["rider_id", "city", "joined_date", "completed_deliveries", "failed_deliveries", "deliveries_per_day"]],
        width="stretch",
        hide_index=True,
    )
