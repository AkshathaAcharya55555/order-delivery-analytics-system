"""
Shared pytest fixtures for the tests/ suite.

Connects to the same oda_db PostgreSQL instance every other layer of this
project uses (docker-compose.yml / analytics/scripts/db.py). Defaults match
a host-based run; override via the same ODA_DB_* environment variables
analytics/scripts/db.py accepts if running against a container.

Default host is 127.0.0.1, not "localhost": on this Windows/Docker Desktop
setup, "localhost" sometimes resolves to the IPv6 loopback (::1) first, and
Docker Desktop's port-forwarding proxy has been observed to intermittently
reset connections made over that specific path (reproduced identically with
curl during the containerization/end-to-end testing phase) - forcing IPv4
avoids that flakiness.
"""

import os

import psycopg2
import pytest

DB_HOST = os.environ.get("ODA_DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("ODA_DB_PORT", "5432")
DB_NAME = os.environ.get("ODA_DB_NAME", "oda_db")
DB_USER = os.environ.get("ODA_DB_USER", "oda_user")
DB_PASSWORD = os.environ.get("ODA_DB_PASSWORD", "oda_password")


@pytest.fixture(scope="session")
def db_dsn():
    return f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"


@pytest.fixture
def db_conn(db_dsn):
    """A connection with autocommit off - each test gets its own transaction,
    rolled back at the end so constraint-violation tests never leave bad (or
    any) rows behind in the shared database."""
    conn = psycopg2.connect(db_dsn)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
