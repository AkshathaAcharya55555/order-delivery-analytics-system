"""Order Trends - daily volume, revenue, and cancellation trends."""

import streamlit as st

from lib import charts, data
from lib.filters import filter_orders, sidebar_filters

st.set_page_config(page_title="Order Trends", layout="wide", page_icon="📦")
st.title("Order Trends")

try:
    orders = data.load_orders()
except Exception as exc:
    st.error(f"Could not connect to the database: {exc}")
    st.stop()

start_date, end_date, cities, statuses = sidebar_filters(orders)
filtered = filter_orders(orders, start_date, end_date, cities, statuses)

if filtered.empty:
    st.warning("No orders match the current filter selection.")
    st.stop()

daily = data.daily_stats(filtered)

vol = data.metrics.order_volume_metrics(filtered)
val = data.metrics.order_value_metrics(filtered)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Orders", f"{vol['total_orders']:,}")
c2.metric("Avg Order Value", f"${val['avg_order_value']:.2f}")
c3.metric("Median Order Value", f"${val['median_order_value']:.2f}")
c4.metric("Days in range", f"{daily.shape[0]}")

st.altair_chart(charts.order_trend_chart(daily), width="stretch")
st.altair_chart(charts.revenue_trend_chart(daily), width="stretch")
st.altair_chart(charts.cancellation_trend_chart(daily), width="stretch")

with st.expander("Daily figures - full table"):
    st.dataframe(
        daily.rename(columns={"order_date": "date"}),
        width="stretch",
        hide_index=True,
    )
