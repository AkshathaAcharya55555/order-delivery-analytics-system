"""
Real Kafka event-processing latency: creates a real order via the running
order-service REST API, then polls Postgres's processed_events table (the
tracking-service consumer's idempotency ledger) until a row appears for
that order's ORDER_CREATED event - measuring the full
produce -> broker -> consume -> DB-write latency, not a synthetic estimate.

Run: python tests/performance/kafka_latency.py [n_orders]
"""

import os
import sys
import time

import psycopg2
import requests

BASE_ORDER = "http://127.0.0.1:8081"

DB_HOST = os.environ.get("ODA_DB_HOST", "127.0.0.1")  # not "localhost" - see tests/conftest.py
DB_PORT = os.environ.get("ODA_DB_PORT", "5432")
DB_NAME = os.environ.get("ODA_DB_NAME", "oda_db")
DB_USER = os.environ.get("ODA_DB_USER", "oda_user")
DB_PASSWORD = os.environ.get("ODA_DB_PASSWORD", "oda_password")

POLL_INTERVAL_S = 0.1
POLL_TIMEOUT_S = 20


def create_order():
    payload = {
        "customerId": 1, "deliveryLocationId": 1, "paymentMethod": "card",
        "items": [{"productName": "Kafka Latency Test", "category": "food", "unitPrice": 1.0, "quantity": 1}],
    }
    resp = requests.post(f"{BASE_ORDER}/api/orders", json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()["orderId"]


def wait_for_processed_event(conn, order_id):
    deadline = time.perf_counter() + POLL_TIMEOUT_S
    while time.perf_counter() < deadline:
        cur = conn.cursor()
        cur.execute(
            "SELECT processed_at FROM processed_events "
            "WHERE order_id = %s AND event_type = 'ORDER_CREATED'",
            (order_id,),
        )
        row = cur.fetchone()
        conn.commit()
        if row:
            return True
        time.sleep(POLL_INTERVAL_S)
    return False


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5

    try:
        requests.get(f"{BASE_ORDER}/api/orders?page=0&size=1", timeout=10)
    except Exception as exc:
        print(f"FATAL: order-service not reachable at {BASE_ORDER}: {exc}")
        sys.exit(1)

    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

    print(f"Configuration: {n} sequential orders, polling processed_events every "
          f"{POLL_INTERVAL_S * 1000:.0f}ms, {POLL_TIMEOUT_S}s timeout per order, "
          f"measuring order-service publish -> tracking-service consume+persist latency\n")

    latencies_ms = []
    for i in range(n):
        start = time.perf_counter()
        order_id = create_order()
        found = wait_for_processed_event(conn, order_id)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if found:
            latencies_ms.append(elapsed_ms)
            print(f"  order {order_id}: processed in {elapsed_ms:.0f}ms")
        else:
            print(f"  order {order_id}: NOT observed in processed_events within {POLL_TIMEOUT_S}s")

    conn.close()

    if latencies_ms:
        latencies_ms.sort()
        print(f"\nn={len(latencies_ms)}/{n} succeeded | "
              f"min={latencies_ms[0]:.0f}ms "
              f"median={latencies_ms[len(latencies_ms)//2]:.0f}ms "
              f"max={latencies_ms[-1]:.0f}ms")
    else:
        print("\nNo events observed within timeout - could not measure latency.")


if __name__ == "__main__":
    main()
