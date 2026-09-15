"""
Concurrent order-creation check: fires N POST /api/orders requests at once
(a thread pool, not a single-process load-test tool) against the running
order-service container, and reports real wall-clock time, per-request
latency, and success/failure counts.

This is a small, realistic concurrency check (a handful of simultaneous
customers), not a load/stress test - configuration is recorded alongside
the result so the number is never read out of context.

Run: python tests/performance/concurrent_orders.py [concurrency]
"""

import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BASE_ORDER = "http://127.0.0.1:8081"


def create_one_order(i):
    payload = {
        "customerId": 1, "deliveryLocationId": 1, "paymentMethod": "card",
        "items": [{"productName": f"Concurrent Test {i}", "category": "food", "unitPrice": 1.0, "quantity": 1}],
    }
    start = time.perf_counter()
    try:
        resp = requests.post(f"{BASE_ORDER}/api/orders", json=payload, timeout=30)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return resp.status_code == 201, elapsed_ms, resp.status_code
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return False, elapsed_ms, str(exc)


def main():
    concurrency = int(sys.argv[1]) if len(sys.argv) > 1 else 20

    try:
        requests.get(f"{BASE_ORDER}/api/orders?page=0&size=1", timeout=10)
    except Exception as exc:
        print(f"FATAL: order-service not reachable at {BASE_ORDER}: {exc}")
        sys.exit(1)

    print(f"Configuration: {concurrency} concurrent POST /api/orders requests, "
          f"ThreadPoolExecutor(max_workers={concurrency}), target={BASE_ORDER}")

    wall_start = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(create_one_order, i) for i in range(concurrency)]
        for f in as_completed(futures):
            results.append(f.result())
    wall_elapsed = time.perf_counter() - wall_start

    successes = [r for r in results if r[0]]
    failures = [r for r in results if not r[0]]
    latencies = sorted(r[1] for r in results)

    print(f"\nTotal wall-clock time for {concurrency} concurrent requests: {wall_elapsed * 1000:.1f}ms")
    print(f"Successful (201): {len(successes)}/{concurrency}")
    print(f"Failed: {len(failures)}/{concurrency}")
    if failures:
        print(f"Failure details (status/exception): {[r[2] for r in failures]}")
    if latencies:
        print(
            f"Per-request latency: min={latencies[0]:.1f}ms "
            f"median={statistics.median(latencies):.1f}ms "
            f"max={latencies[-1]:.1f}ms"
        )
    print(f"Effective throughput: {concurrency / wall_elapsed:.1f} orders/sec")


if __name__ == "__main__":
    main()
