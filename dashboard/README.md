# Analytics Dashboard

A Streamlit dashboard over the same `oda_db` PostgreSQL database used by the
backend services, the SQL analytics layer (`analytics/sql/`), and the Python
analytics layer (`analytics/`). Every number and chart is computed live from
the database (or, on the Data Quality page, from `data_quality/quality_report.csv`)
when the app runs - nothing is hardcoded.

## Structure

```
dashboard/
├── app.py                        # Executive Overview (home page)
├── pages/
│   ├── 1_Order_Trends.py
│   ├── 2_Delivery_Performance.py
│   ├── 3_Rider_Performance.py
│   ├── 4_Customer_Analytics.py
│   └── 5_Data_Quality.py
├── lib/
│   ├── data.py                   # cached SQL loaders + pandas aggregation helpers
│   ├── filters.py                # sidebar date/city/status filters
│   └── charts.py                 # Altair chart builders
├── requirements.txt
└── README.md
```

## Startup

Requires `oda_postgres` running with the generated dataset loaded (see the
root README's "Database layer" and "Running the data generator" sections -
this dashboard queries the full ~100k-order dataset, not the small seed
sample).

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

Streamlit prints a local URL (default `http://localhost:8501`); open it in a
browser. Use the left sidebar to switch between the six pages.

If Postgres isn't reachable, every page shows a clear connection error
instead of a traceback or stale/hardcoded numbers.

## Pages

1. **Executive Overview** - the 8 headline KPIs, the order trend + funnel,
   and a city comparison.
2. **Order Trends** - daily order volume, revenue, and cancellation-rate
   trends over the selected range.
3. **Delivery Performance** - delivery-time distribution (with the assumed
   SLA and median marked), delivery time by city, and average time spent per
   lifecycle stage.
4. **Rider Performance** - top riders by deliveries/day and rider load
   (orders per active rider) by city.
5. **Customer Analytics** - repeat-customer rate and order-frequency
   distribution.
6. **Data Quality** - the `data_quality/validate.py` results, read directly
   from `quality_report.csv`. This page does **not** use the sidebar filters:
   it always reflects the full raw dataset, since that's what was actually
   checked (see `data_quality/README.md`).

## Filters

The sidebar (present on pages 1-5) has three filters, applied together:

- **Date range** (on `order_placed_at`)
- **City** (multi-select, from `locations.city`)
- **Order status** (multi-select, the 10-stage lifecycle status)

Filter selections use fixed widget keys, so they persist across pages within
a session (choosing a city on one page keeps it selected when you switch to
another). All KPIs and charts on pages 1-5 recompute from the filtered data -
e.g. selecting a single city recalculates that city's completion rate,
delivery times, etc. rather than just re-labeling the same numbers.

## KPIs

Total Orders, Revenue, Completion Rate, Cancellation Rate, Average Delivery
Time, P90 Delivery Time, Late Delivery Rate, Repeat Customer Rate - all
computed with the exact same formulas as `analytics/scripts/metrics.py`
(imported directly, not reimplemented) so the dashboard's numbers match
`analytics/sql/` and `reports/business_insights.md` whenever the filters
select the full dataset.

## Design choices

- **SQL vs. pandas split**: three lightweight SQL queries pull row-level
  orders/deliveries/status-history/riders once per session (cached with
  `st.cache_data`); every filter, aggregation, and metric after that is
  pandas, so changing a filter re-slices in-memory data instead of
  re-querying Postgres - this is what makes the filters feel instant.
- **Single source of truth for metrics**: `lib/data.py` imports
  `analytics/scripts/db.py` (connection) and `analytics/scripts/metrics.py`
  (formulas) directly via `sys.path`, rather than copying either. Only the
  SQL queries are new, and only because the dashboard needs city/status
  columns on every row for filtering, which the existing analytics queries
  don't carry.
- **Altair over matplotlib**: `analytics/scripts/charts.py` (matplotlib)
  produces static PNGs for the notebook/report. The dashboard is interactive,
  so its charts (`lib/charts.py`) use Altair (a Streamlit-bundled dependency,
  no extra install) for hover tooltips and native resizing.

## Validation actually performed

- Ran `python -m streamlit run dashboard/app.py` against the live database
  and requested every page; also used Streamlit's `AppTest` framework
  (`streamlit.testing.v1.AppTest`) to execute `app.py` and, via
  `switch_page`, all five `pages/*.py` scripts end-to-end against the real
  database - confirmed zero exceptions on every page.
- Cross-checked the rendered KPI values against the independently-produced
  `reports/business_insights.md` and `data_quality/quality_report.csv` with
  no filters applied - they match exactly (e.g. Total Orders 100,000, Avg
  Delivery Time 49.3 min, P90 67.1 min, Late Delivery Rate 59.35%, Repeat
  Customer Rate 61.66%, Data Quality total records failed 28,127).
- Exercised the filters interactively (city = Austin only; status =
  CANCELLED only) and confirmed the KPIs recompute correctly - e.g. filtering
  to Austin reproduces that city's exact row from the business-insights city
  table (21,878 orders, 8.12% cancellation, 90.27% completion).
- Fixed a real, reproducible issue found during this testing: `st.altair_chart`/
  `st.dataframe` calls used the deprecated `use_container_width=True` argument
  (Streamlit 1.63 warns this is scheduled for removal); replaced with
  `width="stretch"` throughout and re-ran the full AppTest suite to confirm
  no regressions.

Not done: no automated UI/visual regression tests, no load testing, no
authentication (this is a local analytics tool, not a hosted service).
