# Resume Alignment

Resume bullets and a project summary targeted at an **Associate Data
Analyst** role, built only from work actually completed in this repository.
No business-impact numbers are invented (no "% improved efficiency" or
similar) — every figure here is a schema fact, a row count, a test count,
or the output of an actual run, each traceable to a specific file in this
project.

## One-line project summary (for a resume "Projects" section header)

> **Scalable Order & Delivery Analytics System** — an independent, full-stack
> portfolio project (PostgreSQL, Python, SQL, Java/Spring Boot, Kafka,
> Redis, Streamlit) simulating a food-delivery business, built to
> demonstrate end-to-end data analysis: schema design, ETL, data quality,
> SQL and Python analytics, and a live BI dashboard.

## Resume bullets

Pick 4-6 depending on the role's emphasis; the first group is most directly
relevant to an Associate Data Analyst posting.

**SQL & database analysis**
- Designed a normalized 9-table PostgreSQL schema (customers, orders,
  riders, deliveries, order-status history) with foreign keys, CHECK
  constraints, and 6 analytical views, then wrote 20 SQL queries answering
  specific business questions using window functions (`RANK`, `LAG`,
  `LEAD`), CTEs, `PERCENTILE_CONT`, and correlated subqueries.
- Analyzed a 100,000-order operational dataset in PostgreSQL to compute
  delivery-time percentiles (median, P90), cancellation and completion
  rates by city, rider utilization, and a full order-lifecycle funnel.
- Wrote 19 automated tests validating every CHECK/foreign-key/unique
  constraint in the schema directly against PostgreSQL, independent of
  application code.

**Python & data analysis**
- Built a Python (pandas/NumPy/matplotlib) exploratory data analysis layer
  reading live from PostgreSQL via SQLAlchemy, covering order trends,
  delivery performance, rider utilization, and customer repeat behavior,
  with results cross-validated against an independent SQL implementation.
- Authored an executed Jupyter notebook (28 cells, zero errors) presenting
  the same analysis with embedded charts for non-technical stakeholders.
- Built a configurable synthetic data generator producing a 100,000-order,
  50,000-customer dataset with deliberately injected, documented data-
  quality issues, used to validate the analytics and data-quality layers
  against realistic imperfect data rather than a clean toy dataset.

**Data quality**
- Designed and implemented 10 automated data-quality rules (missing
  values, orphaned foreign keys, duplicate records, invalid value ranges,
  inconsistent categorical values) with severity classification and
  pass/fail reporting, backed by 24 unit tests against hand-built clean and
  corrupted fixtures.
- Investigated an unexpected data-quality finding by tracing individual
  records back through their full history rather than accepting the number
  at face value, identifying the true root cause before reporting it.

**Dashboard / BI**
- Built a 6-page Streamlit dashboard (Executive Overview, Order Trends,
  Delivery Performance, Rider Performance, Customer Analytics, Data
  Quality) with interactive date/city/status filters, reading every KPI and
  chart live from PostgreSQL with no hardcoded values.
- Authored a business-insights report translating raw analytics into
  actionable findings for a non-technical audience, including explicit
  documentation of every assumption (e.g., an illustrative SLA threshold)
  so no number could be misread as more certain than it was.

**Full-stack / engineering context** *(supporting bullets — use if the role values technical breadth)*
- Built three independent Java/Spring Boot REST services integrated via
  Apache Kafka (7 event topics) with idempotent event consumption, and a
  Redis caching layer with a tested Postgres fallback, containerized end to
  end with Docker Compose.
- Wrote and ran 122 automated tests (JUnit, pytest) across the database,
  backend services, data-quality rules, and SQL analytics layer, and
  recorded real performance measurements (API latency, concurrent order
  creation, database query timing, Kafka event-processing latency) rather
  than estimating them.

## Skills-to-evidence map

| Skill an Associate Data Analyst posting typically lists | Where it's demonstrated |
|---|---|
| SQL (joins, aggregation, window functions) | `analytics/sql/` (20 queries), `database/views.sql` |
| Data modeling / schema design | `database/schema.sql`, `docs/DATABASE.md` |
| Python for data analysis (pandas/NumPy) | `analytics/scripts/`, `analytics/notebooks/eda_analysis.ipynb` |
| Data cleaning / data quality | `data_quality/` (10 rules), `data_generator/` (injected issues) |
| Data visualization / BI tooling | `dashboard/` (Streamlit, 6 pages) |
| Communicating findings to non-technical audiences | `reports/business_insights.md` |
| Statistics (percentiles, distributions) | delivery-time median/P90/skewness analysis |
| ETL / data pipelines | `database/staging_schema.sql` + `load_generated_dataset.sql` |
| Testing / data validation rigor | `docs/TESTING.md` (122 tests), `tests/` |
| Version control & documentation | this repository's structure and `docs/` |

## Notes on honesty in framing

- Every number above (100,000 orders, 20 queries, 10 rules, 6 dashboard
  pages, 122 tests, 28 notebook cells) is copied from this project's actual
  state, not rounded up or estimated — see `docs/DATABASE.md`,
  `docs/ANALYTICS.md`, and `docs/TESTING.md` for where each comes from.
- No bullet claims a production deployment, a real company's data, measured
  business impact (cost savings, revenue lift, efficiency gains), or a
  performance benchmark that wasn't actually measured in
  `docs/PERFORMANCE.md`. If asked in an interview, describe this as an
  independent portfolio project built to demonstrate these skills — not a
  professional engagement.
