# Python Analytics Layer

Exploratory analysis of the full generated dataset (~100k orders — see root
README for how it's loaded into `oda_db`) using Python, pandas, NumPy,
matplotlib, and SQLAlchemy/psycopg2. This complements `analytics/sql/`
(pure-SQL business questions) rather than duplicating it — see "Why SQL
here, pandas there" below.

## Structure

```
analytics/
├── notebooks/
│   └── eda_analysis.ipynb   # executed narrative walkthrough (see below)
├── scripts/
│   ├── db.py                # SQLAlchemy engine (same oda_db credentials as everything else)
│   ├── queries.py           # all SQL used for DB-side aggregation/joins
│   ├── metrics.py           # pandas/NumPy metric calculations
│   ├── charts.py            # matplotlib chart generation
│   └── run_eda.py           # main script: runs everything, prints the numbers, saves charts
├── charts/                  # PNG output of the last real run — committed (small, ~215KB total)
└── README.md
```

## Run it

Requires `oda_postgres` running with the generated dataset loaded (see root
README's "Database layer" section) and the Python packages below.

```bash
pip install pandas numpy matplotlib sqlalchemy psycopg2-binary
python analytics/scripts/run_eda.py
```

To regenerate the notebook's executed output:

```bash
pip install nbformat nbclient nbconvert ipykernel
jupyter nbconvert --to notebook --execute --inplace analytics/notebooks/eda_analysis.ipynb
```

## What's analyzed

Order trends, delivery performance, rider performance, customer behavior,
city performance, and operational bottlenecks — see
`reports/business_insights.md` for the write-up aimed at a non-technical
reader, or open the notebook directly for the full walkthrough with inline
charts.

## Metrics calculated

Total orders, completed orders, cancellation rate, completion rate, average
order value, average/median/P90 delivery time, late-delivery rate (against
an explicitly labeled *assumed*, not measured, 45-minute SLA), rider
utilization (deliveries per day active), and repeat-customer rate. Exact
definitions and formulas are in `scripts/metrics.py`.

## Why SQL here, pandas there

Every query in `queries.py` either does a JOIN (across `deliveries` /
`orders` / `locations` / `riders`) or a `GROUP BY` that collapses row count
by 100-1000x before pandas ever sees the result — e.g. 91,257 delivery rows
join down to one row per rider (2,000) via SQL, not via a pandas merge +
groupby over the raw rows. That's SQL doing what a database is for.

`orders` and the joined `delivery_facts` table are pulled at row level
(100k / 91k rows) rather than further aggregated in SQL, because several
*different* pandas calculations reuse that same pull (completion rate,
cancellation rate, average order value, order trend, delivery percentiles,
histograms) — one round trip, several derived metrics, instead of a
separate SQL query per metric. Percentiles specifically are computed with
`np.percentile`/`.median()` in `metrics.py` rather than another
`PERCENTILE_CONT` query, since the same in-memory Series is also what feeds
the histogram and skewness check — that's the one thing pandas does that
requires the raw distribution, not just a single number.

## Validation actually performed

`analytics/scripts/run_eda.py` was run against the live database; every
number in `reports/business_insights.md` and in the executed notebook was
copied from that real run, not estimated. The notebook was executed
end-to-end via `nbconvert` (confirmed zero error cells across all 28 cells)
so its embedded charts and printed values are real, not illustrative
placeholders. Pandas/NumPy results were cross-checked against the
equivalent pure-SQL queries in `analytics/sql/` and agree within rounding
(e.g. median delivery time: 48.48 min here vs. 48.3-48.7 min per-city in
the SQL layer).

Not done: no performance/timing benchmarking of the Python layer itself.
