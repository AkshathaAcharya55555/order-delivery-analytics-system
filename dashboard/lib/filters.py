"""
Shared sidebar filters (date range, city, order status).

Widgets use fixed keys so Streamlit's session_state persists the selection
across pages when the user navigates the multipage app - the filters chosen
on one page stay applied when switching to another.
"""

import datetime as dt

import pandas as pd
import streamlit as st

ALL_ORDER_STATUSES = [
    "PLACED", "CONFIRMED", "PREPARING", "READY_FOR_PICKUP", "RIDER_ASSIGNED",
    "PICKED_UP", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED", "FAILED",
]


def sidebar_filters(orders: pd.DataFrame):
    st.sidebar.header("Filters")

    min_date = orders["order_placed_at"].min().date()
    max_date = orders["order_placed_at"].max().date()
    date_value = st.sidebar.date_input(
        "Date range (order placed)",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="oda_date_range",
    )
    if isinstance(date_value, tuple) and len(date_value) == 2:
        start_date, end_date = date_value
    elif isinstance(date_value, tuple) and len(date_value) == 1:
        start_date = end_date = date_value[0]
    else:
        start_date = end_date = date_value

    cities = sorted(orders["city"].unique())
    selected_cities = st.sidebar.multiselect(
        "City", options=cities, default=cities, key="oda_city_filter"
    )

    statuses = sorted(orders["status"].unique())
    selected_statuses = st.sidebar.multiselect(
        "Order status", options=statuses, default=statuses, key="oda_status_filter"
    )

    st.sidebar.caption(
        "Filters apply to every page except Data Quality, which validates "
        "the full raw dataset regardless of these selections."
    )

    return (
        start_date,
        end_date,
        selected_cities if selected_cities else cities,
        selected_statuses if selected_statuses else statuses,
    )


def filter_orders(
    orders: pd.DataFrame,
    start_date: dt.date,
    end_date: dt.date,
    cities: list,
    statuses: list,
) -> pd.DataFrame:
    mask = (
        (orders["order_placed_at"].dt.date >= start_date)
        & (orders["order_placed_at"].dt.date <= end_date)
        & (orders["city"].isin(cities))
        & (orders["status"].isin(statuses))
    )
    return orders.loc[mask].copy()


def filter_by_order_ids(df: pd.DataFrame, order_ids) -> pd.DataFrame:
    return df.loc[df["order_id"].isin(order_ids)].copy()
