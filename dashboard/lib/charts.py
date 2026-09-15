"""
Altair chart builders. Each function takes a small, already-filtered/
aggregated pandas DataFrame and returns an alt.Chart for st.altair_chart().

Altair (not matplotlib) is used here specifically because this is an
interactive app - hover tooltips and Streamlit-native resizing matter more
here than in the static analytics/scripts/charts.py PNGs, which serve a
different purpose (embedding in a notebook/report). Altair ships as a
Streamlit dependency, so no extra package beyond streamlit was added.
"""

import altair as alt
import pandas as pd

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
SEVERITY_COLORS = {
    "CRITICAL": "#c0392b",
    "HIGH": "#e07a3f",
    "MEDIUM": "#d4a72c",
    "LOW": "#4a7c59",
}


def order_trend_chart(daily: pd.DataFrame) -> alt.Chart:
    daily = daily.sort_values("order_date").copy()
    daily["rolling_7day"] = daily["total_orders"].rolling(7, min_periods=1).mean()
    base = alt.Chart(daily).encode(x=alt.X("order_date:T", title="Date"))
    daily_line = base.mark_line(color="#9fb3c8", opacity=0.7).encode(
        y=alt.Y("total_orders:Q", title="Orders"),
        tooltip=["order_date:T", "total_orders:Q"],
    )
    rolling_line = base.mark_line(color="#2b6cb0", strokeWidth=2.5).encode(
        y="rolling_7day:Q",
        tooltip=["order_date:T", alt.Tooltip("rolling_7day:Q", format=".1f")],
    )
    return (daily_line + rolling_line).properties(
        title="Daily Order Volume (with 7-day rolling average)", height=320
    ).interactive()


def revenue_trend_chart(daily: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(daily)
        .mark_line(color="#2b6cb0", point=alt.OverlayMarkDef(size=25))
        .encode(
            x=alt.X("order_date:T", title="Date"),
            y=alt.Y("revenue:Q", title="Revenue ($)"),
            tooltip=["order_date:T", alt.Tooltip("revenue:Q", format="$,.2f")],
        )
        .properties(title="Daily Revenue (non-cancelled orders)", height=320)
        .interactive()
    )


def cancellation_trend_chart(daily: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(daily)
        .mark_line(color="#c0392b", point=alt.OverlayMarkDef(size=25))
        .encode(
            x=alt.X("order_date:T", title="Date"),
            y=alt.Y("cancellation_rate_pct:Q", title="Cancellation rate (%)"),
            tooltip=["order_date:T", alt.Tooltip("cancellation_rate_pct:Q", format=".2f")],
        )
        .properties(title="Daily Cancellation Rate", height=320)
        .interactive()
    )


def delivery_time_histogram(minutes: pd.Series, sla_minutes: float) -> alt.Chart:
    df = pd.DataFrame({"minutes": minutes})
    median = float(minutes.median())
    hist = (
        alt.Chart(df)
        .mark_bar(color="#4a7c59", opacity=0.85)
        .encode(
            x=alt.X("minutes:Q", bin=alt.Bin(maxbins=40), title="Minutes (order placed -> delivered)"),
            y=alt.Y("count():Q", title="Number of deliveries"),
            tooltip=[alt.Tooltip("count():Q", title="Deliveries")],
        )
    )
    sla_rule = (
        alt.Chart(pd.DataFrame({"x": [sla_minutes]}))
        .mark_rule(color="#c0392b", strokeDash=[6, 3], size=2)
        .encode(x="x:Q")
    )
    median_rule = (
        alt.Chart(pd.DataFrame({"x": [median]}))
        .mark_rule(color="#333333", strokeDash=[2, 2], size=2)
        .encode(x="x:Q")
    )
    return (hist + sla_rule + median_rule).properties(
        title=f"Delivery Time Distribution (red = assumed {sla_minutes}-min SLA, "
        f"black = median {median:.1f} min)",
        height=320,
    )


def stage_duration_chart(stage_durations: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(stage_durations)
        .mark_bar(color="#7a5195")
        .encode(
            x=alt.X("avg_minutes:Q", title="Average minutes in stage"),
            y=alt.Y("status:N", sort="-x", title=None),
            tooltip=["status:N", alt.Tooltip("avg_minutes:Q", format=".1f")],
        )
        .properties(title="Average Time Spent per Lifecycle Stage", height=320)
    )


def delivery_time_by_city_chart(by_city: pd.DataFrame) -> alt.Chart:
    melted = by_city.melt(
        id_vars="city",
        value_vars=["avg_minutes", "median_minutes", "p90_minutes"],
        var_name="metric",
        value_name="minutes",
    )
    return (
        alt.Chart(melted)
        .mark_bar()
        .encode(
            x=alt.X("minutes:Q", title="Minutes"),
            y=alt.Y("city:N", title=None),
            color=alt.Color("metric:N", title="Metric"),
            yOffset="metric:N",
            tooltip=["city:N", "metric:N", alt.Tooltip("minutes:Q", format=".1f")],
        )
        .properties(title="Delivery Time by City (avg / median / P90)", height=320)
    )


def city_comparison_chart(city_perf: pd.DataFrame) -> alt.Chart:
    orders_bar = (
        alt.Chart(city_perf)
        .mark_bar(color="#2b6cb0")
        .encode(
            x=alt.X("total_orders:Q", title="Orders"),
            y=alt.Y("city:N", sort="-x", title=None),
            tooltip=["city:N", "total_orders:Q"],
        )
        .properties(title="Total Orders by City", height=280)
    )
    cancel_bar = (
        alt.Chart(city_perf)
        .mark_bar(color="#c0392b")
        .encode(
            x=alt.X("cancellation_rate_pct:Q", title="Cancellation rate (%)"),
            y=alt.Y("city:N", sort="-x", title=None),
            tooltip=["city:N", alt.Tooltip("cancellation_rate_pct:Q", format=".2f")],
        )
        .properties(title="Cancellation Rate by City", height=280)
    )
    return alt.hconcat(orders_bar, cancel_bar)


def order_funnel_chart(funnel: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(funnel)
        .mark_bar(color="#7a5195")
        .encode(
            x=alt.X("orders_reached:Q", title="Orders that reached this stage"),
            y=alt.Y("status:N", sort=None, title=None),
            tooltip=["status:N", "orders_reached:Q"],
        )
        .properties(title="Order Funnel (stages reached, current filters)", height=320)
    )


def rider_performance_chart(rider_util: pd.DataFrame, top_n: int = 20) -> alt.Chart:
    df = rider_util.head(top_n)
    return (
        alt.Chart(df)
        .mark_bar(color="#f4a259")
        .encode(
            x=alt.X("deliveries_per_day:Q", title="Deliveries per day active"),
            y=alt.Y("rider_id:N", sort="-x", title="Rider ID"),
            tooltip=["rider_id:N", "city:N", alt.Tooltip("deliveries_per_day:Q", format=".2f")],
        )
        .properties(title=f"Top {top_n} Riders by Deliveries/Day", height=420)
    )


def rider_city_load_chart(city_load: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(city_load)
        .mark_bar(color="#118ab2")
        .encode(
            x=alt.X("orders_per_rider:Q", title="Orders per active rider"),
            y=alt.Y("city:N", sort="-x", title=None),
            tooltip=["city:N", alt.Tooltip("orders_per_rider:Q", format=".1f")],
        )
        .properties(title="Rider Load by City (orders per active rider)", height=280)
    )


def customer_frequency_chart(customer_counts: pd.DataFrame) -> alt.Chart:
    dist = customer_counts["order_count"].value_counts().sort_index()
    dist = dist[dist.index <= 15]
    df = pd.DataFrame({"orders_placed": dist.index, "customers": dist.values})
    return (
        alt.Chart(df)
        .mark_bar(color="#118ab2")
        .encode(
            x=alt.X("orders_placed:O", title="Orders placed"),
            y=alt.Y("customers:Q", title="Number of customers"),
            tooltip=["orders_placed:O", "customers:Q"],
        )
        .properties(title="Customer Order Frequency (capped at 15 orders for readability)", height=320)
    )


def data_quality_chart(report: pd.DataFrame) -> alt.Chart:
    df = report.copy()
    df["severity"] = pd.Categorical(df["severity"], categories=SEVERITY_ORDER, ordered=True)
    return (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("failure_rate_pct:Q", title="Failure rate (%)"),
            y=alt.Y("rule_name:N", sort="-x", title=None),
            color=alt.Color(
                "severity:N",
                scale=alt.Scale(domain=SEVERITY_ORDER, range=[SEVERITY_COLORS[s] for s in SEVERITY_ORDER]),
                legend=alt.Legend(title="Severity"),
            ),
            tooltip=["rule_id", "rule_name", "failure_rate_pct", "severity", "expected_source"],
        )
        .properties(title="Data Quality Rule Failure Rates", height=320)
    )
