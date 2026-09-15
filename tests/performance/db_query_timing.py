"""
Real database query execution timing via Postgres's own EXPLAIN ANALYZE
(the server's own measured planning/execution time, not a client-side
stopwatch that would also include network/psycopg2 overhead).

Run: python tests/performance/db_query_timing.py
"""

import os
import re

import psycopg2

DB_HOST = os.environ.get("ODA_DB_HOST", "127.0.0.1")  # not "localhost" - see tests/conftest.py
DB_PORT = os.environ.get("ODA_DB_PORT", "5432")
DB_NAME = os.environ.get("ODA_DB_NAME", "oda_db")
DB_USER = os.environ.get("ODA_DB_USER", "oda_user")
DB_PASSWORD = os.environ.get("ODA_DB_PASSWORD", "oda_password")

SQL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "analytics", "sql"))


def explain_analyze(cur, label, sql):
    cur.execute(f"EXPLAIN (ANALYZE, FORMAT TEXT) {sql}")
    plan_lines = [row[0] for row in cur.fetchall()]
    exec_line = next((l for l in plan_lines if l.strip().startswith("Execution Time")), None)
    planning_line = next((l for l in plan_lines if l.strip().startswith("Planning Time")), None)
    exec_ms = re.search(r"([\d.]+) ms", exec_line).group(1) if exec_line else "?"
    plan_ms = re.search(r"([\d.]+) ms", planning_line).group(1) if planning_line else "?"
    print(f"{label}: planning={plan_ms}ms execution={exec_ms}ms")


def main():
    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM orders")
    total_orders = cur.fetchone()[0]
    print(f"Dataset size: {total_orders:,} orders\n")

    print("-- Simple indexed lookup (primary key) --")
    explain_analyze(cur, "SELECT * FROM orders WHERE order_id = 1", "SELECT * FROM orders WHERE order_id = 1")

    print("\n-- Simple non-indexed-column filter --")
    explain_analyze(cur, "SELECT * FROM orders WHERE status = 'DELIVERED' LIMIT 100",
                     "SELECT * FROM orders WHERE status = 'DELIVERED' LIMIT 100")

    print("\n-- Join across 4 tables (delivery facts, same shape as analytics/scripts/queries.py) --")
    explain_analyze(cur, "deliveries JOIN orders JOIN locations JOIN riders", """
        SELECT d.order_id, r.city, l.city, o.order_placed_at, d.delivery_status
        FROM deliveries d
        JOIN orders o ON o.order_id = d.order_id
        JOIN locations l ON l.location_id = o.delivery_location_id
        JOIN riders r ON r.rider_id = d.rider_id
    """)

    print("\n-- analytics/sql query files (aggregations over the full dataset) --")
    for filename in ["01_daily_order_volume.sql", "06_p90_delivery_time.sql", "18_demand_vs_rider_availability.sql"]:
        path = os.path.join(SQL_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            sql = f.read().rstrip().rstrip(";")
        try:
            explain_analyze(cur, filename, sql)
        except Exception as exc:
            conn.rollback()
            print(f"{filename}: could not EXPLAIN ANALYZE ({exc})")

    conn.rollback()  # EXPLAIN ANALYZE actually executes the query; no writes were made, but roll back defensively
    conn.close()


if __name__ == "__main__":
    main()
