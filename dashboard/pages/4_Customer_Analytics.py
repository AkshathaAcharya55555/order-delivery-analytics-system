"""Customer Analytics - repeat-purchase rate and order-frequency distribution."""

import streamlit as st

from lib import charts, data
from lib.filters import filter_orders, sidebar_filters

st.set_page_config(page_title="Customer Analytics", layout="wide", page_icon="📦")
st.title("Customer Analytics")

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

customer_counts = data.customer_order_counts(filtered)

if customer_counts.empty:
    st.warning("No non-cancelled orders in the current selection to compute customer metrics from.")
    st.stop()

repeat = data.metrics.repeat_customer_rate(customer_counts)
c1, c2, c3 = st.columns(3)
c1.metric("Ordering Customers", f"{repeat['total_ordering_customers']:,}")
c2.metric("Repeat Customers (2+ orders)", f"{repeat['repeat_customers']:,}")
c3.metric("Repeat Customer Rate", f"{repeat['repeat_customer_rate_pct']:.2f}%")

st.altair_chart(charts.customer_frequency_chart(customer_counts), width="stretch")

st.caption(
    "This repeat-purchase rate reflects the synthetic data generator's "
    "deliberately skewed (lognormal) purchase-propensity design - see "
    "reports/business_insights.md's customer-behavior caveat - not a "
    "discovered fact about a real business."
)

with st.expander("Top customers by order count"):
    top = customer_counts.sort_values("order_count", ascending=False).head(20)
    st.dataframe(top, width="stretch", hide_index=True)
