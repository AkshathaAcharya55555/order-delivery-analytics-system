"""
Structural regression tests for analytics/sql/*.sql (the 20 analytical
queries from the SQL-analytics phase). Each file is executed for real
against the live oda_db database and must:
  1. execute without a SQL error,
  2. return a result set with at least one column, and
  3. return at least one row - a real correctness signal given the full
     ~100k-order/90-day dataset is loaded (a zero-row result from any of
     these against that dataset would mean a real regression, e.g. a broken
     JOIN or a stale filter).

These files are pure SQL (not Python), so this is the layer of testing they
never had before: previously they were only run once by hand during the SQL
analytics phase and eyeballed.

Note: 16_order_funnel.sql contains two SELECT statements (Part A and Part
B); psycopg2/libpq's simple query protocol runs both but only exposes the
LAST statement's result set via the cursor - this test still confirms the
whole file executes cleanly and that final result set is non-empty.
"""

import glob
import os

import pytest

SQL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "analytics", "sql"))
SQL_FILES = sorted(glob.glob(os.path.join(SQL_DIR, "*.sql")))


@pytest.fixture(scope="module")
def dataset_loaded(db_dsn):
    """Skip with a clear reason if the full generated dataset isn't loaded -
    these queries are only meaningful (and only return rows) against it."""
    import psycopg2
    conn = psycopg2.connect(db_dsn)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM orders")
        count = cur.fetchone()[0]
    finally:
        conn.close()
    if count < 1000:
        pytest.skip(
            f"Only {count} orders loaded - the full generated dataset "
            f"(database/load_generated_dataset.sql) is required for these "
            f"queries to return meaningful (non-empty) results."
        )
    return count


@pytest.mark.parametrize("sql_path", SQL_FILES, ids=[os.path.basename(p) for p in SQL_FILES])
def test_query_executes_and_returns_rows(sql_path, db_dsn, dataset_loaded):
    import psycopg2

    with open(sql_path, "r", encoding="utf-8") as f:
        sql_text = f.read()

    conn = psycopg2.connect(db_dsn)
    try:
        cur = conn.cursor()
        cur.execute(sql_text)
        assert cur.description is not None, f"{os.path.basename(sql_path)} did not return a result set"
        columns = [c.name for c in cur.description]
        rows = cur.fetchall()
        assert len(columns) > 0
        assert len(rows) > 0, f"{os.path.basename(sql_path)} returned 0 rows against a {dataset_loaded}-order dataset"
    finally:
        conn.close()


def test_all_twenty_files_are_present():
    assert len(SQL_FILES) == 20
