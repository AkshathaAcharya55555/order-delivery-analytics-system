"""
Database connection helper for the Python analytics layer.

Connects to the same oda_db PostgreSQL instance the backend services and the
SQL analytics layer (analytics/sql/) use — same docker-compose.yml, same
credentials. This module only creates the SQLAlchemy engine; every query
lives in queries.py so the SQL is easy to read/audit separately from
connection plumbing.

Connection details can be overridden via environment variables (used when
this runs inside the dashboard's Docker container, which must reach Postgres
via the "postgres" service name rather than a loopback address).

Default host is 127.0.0.1, not "localhost": on this Windows/Docker Desktop
setup, "localhost" sometimes resolves to the IPv6 loopback (::1) first, and
Docker Desktop's port-forwarding proxy has been observed to intermittently
reset connections made over that specific path - reproduced directly with
run_eda.py during the final audit (two consecutive failures resolving
"localhost", succeeded immediately when forced to 127.0.0.1). Forcing IPv4
avoids that flakiness; this does not change behavior on Linux/macOS hosts,
where this was never an issue.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

DB_HOST = os.environ.get("ODA_DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("ODA_DB_PORT", "5432")
DB_NAME = os.environ.get("ODA_DB_NAME", "oda_db")
DB_USER = os.environ.get("ODA_DB_USER", "oda_user")
DB_PASSWORD = os.environ.get("ODA_DB_PASSWORD", "oda_password")

DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_engine() -> Engine:
    return create_engine(DB_URL)
