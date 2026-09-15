"""
Real API response-time measurement against the running, containerized
order-service/delivery-service/tracking-service (docker-compose up -d).

Not a load-testing tool - just N sequential real HTTP calls per endpoint,
timed with time.perf_counter(), reporting min/median/p90/max. Every number
printed is an actual measurement from this run; nothing here is estimated.

Run: python tests/performance/api_latency.py
"""

import statistics
import sys
import time

import requests

BASE_ORDER = "http://127.0.0.1:8081"
BASE_DELIVERY = "http://127.0.0.1:8082"
BASE_TRACKING = "http://127.0.0.1:8083"
N = 20


def time_calls(label, fn, n=N):
    latencies_ms = []
    errors = 0
    for _ in range(n):
        start = time.perf_counter()
        try:
            resp = fn()
            resp.raise_for_status()
        except Exception:
            errors += 1
            continue
        latencies_ms.append((time.perf_counter() - start) * 1000)

    if not latencies_ms:
        print(f"{label}: all {n} calls failed - cannot measure")
        return

    latencies_ms.sort()
    print(
        f"{label}: n={len(latencies_ms)} errors={errors} "
        f"min={latencies_ms[0]:.1f}ms "
        f"median={statistics.median(latencies_ms):.1f}ms "
        f"p90={latencies_ms[int(len(latencies_ms) * 0.9) - 1]:.1f}ms "
        f"max={latencies_ms[-1]:.1f}ms"
    )


def main():
    print("Warming up (first request after JVM idle can be slower)...")
    try:
        requests.get(f"{BASE_ORDER}/api/orders?page=0&size=1", timeout=30)
    except Exception as exc:
        print(f"FATAL: order-service not reachable at {BASE_ORDER}: {exc}")
        sys.exit(1)

    time_calls("GET /api/orders (page of 20)",
               lambda: requests.get(f"{BASE_ORDER}/api/orders?page=0&size=20", timeout=10))

    time_calls("GET /api/orders/{id} (existing order)",
               lambda: requests.get(f"{BASE_ORDER}/api/orders/1", timeout=10))

    time_calls("GET /api/riders (page of 20)",
               lambda: requests.get(f"{BASE_DELIVERY}/api/riders?page=0&size=20", timeout=10))

    time_calls("GET /api/orders/{id}/tracking",
               lambda: requests.get(f"{BASE_TRACKING}/api/orders/1/tracking", timeout=10))

    def create_order():
        payload = {
            "customerId": 1, "deliveryLocationId": 1, "paymentMethod": "card",
            "items": [{"productName": "Perf Test", "category": "food", "unitPrice": 1.0, "quantity": 1}],
        }
        return requests.post(f"{BASE_ORDER}/api/orders", json=payload, timeout=15)

    time_calls("POST /api/orders (create)", create_order, n=10)


if __name__ == "__main__":
    main()
