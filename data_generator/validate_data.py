"""
Independent validation of the CSVs produced by generate_data.py.

This script does NOT trust the generator's own summary counts — it re-reads
the output files from disk and recomputes everything from scratch. Some
violations are EXPECTED here (they are the data-quality issues generate_data
deliberately injected); this script's job is to detect and count them
honestly, not to make the dataset look clean.

Run: python validate_data.py [output_dir]  (default: output)
"""

import os
import sys

import pandas as pd

ALLOWED_ORDER_STATUSES = {
    "placed", "confirmed", "preparing", "ready_for_pickup",
    "out_for_delivery", "delivered", "cancelled",
}
TABLE_NAMES = [
    "locations", "customers", "riders", "orders",
    "order_items", "deliveries", "order_status_history", "event_log",
]
PRIMARY_KEYS = {
    "locations": "location_id", "customers": "customer_id", "riders": "rider_id",
    "orders": "order_id", "order_items": "order_item_id", "deliveries": "delivery_id",
    "order_status_history": "history_id", "event_log": "event_id",
}
TIMESTAMP_COLUMNS = {
    "orders": ["order_placed_at"],
    "deliveries": ["assigned_at", "picked_up_at", "delivered_at"],
    "order_status_history": ["changed_at"],
    "event_log": ["event_timestamp"],
}


def load_tables(input_dir: str) -> dict:
    tables = {}
    for name in TABLE_NAMES:
        path = os.path.join(input_dir, f"{name}.csv")
        parse_dates = TIMESTAMP_COLUMNS.get(name, [])
        tables[name] = pd.read_csv(path, parse_dates=parse_dates)
    return tables


def check_row_counts(tables: dict) -> list:
    lines = ["## Row counts", ""]
    for name in TABLE_NAMES:
        lines.append(f"- {name}: {len(tables[name]):,}")
    return lines


def check_duplicate_ids(tables: dict) -> list:
    lines = ["", "## Duplicate ID check (surrogate primary keys — expect 0 for all)", ""]
    all_clean = True
    for name, col in PRIMARY_KEYS.items():
        dup_count = int(tables[name][col].duplicated().sum())
        status = "OK" if dup_count == 0 else "VIOLATION"
        if dup_count != 0:
            all_clean = False
        lines.append(f"- {name}.{col}: {dup_count} duplicate id(s) — {status}")

    lines.append("")
    lines.append("## Business-content duplicates (expected — from injected duplicate-row issue)")
    lines.append("")
    oi = tables["order_items"]
    oi_dupe_rows = int(
        oi.duplicated(subset=["order_id", "product_name", "unit_price", "quantity"], keep=False).sum()
    )
    lines.append(f"- order_items: {oi_dupe_rows} rows share (order_id, product, price, quantity) with another row")

    ev = tables["event_log"]
    ev_dupe_rows = int(ev.duplicated(subset=["order_id", "event_type", "event_timestamp"], keep=False).sum())
    lines.append(f"- event_log: {ev_dupe_rows} rows share (order_id, event_type, event_timestamp) with another row")

    return lines, all_clean


def check_foreign_keys(tables: dict) -> list:
    lines = ["", "## Foreign-key integrity (expect 0 orphans for all)", ""]
    all_clean = True

    checks = [
        ("orders.customer_id -> customers.customer_id", tables["orders"]["customer_id"], tables["customers"]["customer_id"], False),
        ("orders.delivery_location_id -> locations.location_id", tables["orders"]["delivery_location_id"], tables["locations"]["location_id"], False),
        ("orders.rider_id -> riders.rider_id", tables["orders"]["rider_id"], tables["riders"]["rider_id"], True),
        ("order_items.order_id -> orders.order_id", tables["order_items"]["order_id"], tables["orders"]["order_id"], False),
        ("deliveries.order_id -> orders.order_id", tables["deliveries"]["order_id"], tables["orders"]["order_id"], False),
        ("deliveries.rider_id -> riders.rider_id", tables["deliveries"]["rider_id"], tables["riders"]["rider_id"], False),
        ("order_status_history.order_id -> orders.order_id", tables["order_status_history"]["order_id"], tables["orders"]["order_id"], False),
        ("event_log.order_id -> orders.order_id", tables["event_log"]["order_id"], tables["orders"]["order_id"], False),
    ]

    for label, child_series, parent_series, allow_null in checks:
        vals = child_series.dropna() if allow_null else child_series
        orphans = int((~vals.isin(parent_series)).sum())
        status = "OK" if orphans == 0 else "VIOLATION"
        if orphans != 0:
            all_clean = False
        lines.append(f"- {label}: {orphans} orphan value(s) — {status}")

    dup_delivery_orders = int(tables["deliveries"]["order_id"].duplicated().sum())
    status = "OK" if dup_delivery_orders == 0 else "VIOLATION"
    if dup_delivery_orders != 0:
        all_clean = False
    lines.append(f"- deliveries.order_id uniqueness (1 delivery per order): {dup_delivery_orders} duplicate(s) — {status}")

    return lines, all_clean


def check_timestamp_consistency(tables: dict, config_start, config_end) -> list:
    lines = ["", "## Timestamp consistency", ""]

    d = tables["deliveries"]
    pickup_before_assign = int((d["picked_up_at"] < d["assigned_at"]).sum())
    lines.append(f"- deliveries: picked_up_at earlier than assigned_at: {pickup_before_assign} row(s) (expected: 0)")

    delivered_rows = d[d["delivery_status"] == "delivered"]
    delivered_before_pickup = int((delivered_rows["delivered_at"] < delivered_rows["picked_up_at"]).sum())
    lines.append(
        f"- deliveries: delivered_at earlier than picked_up_at: {delivered_before_pickup} row(s) "
        f"(expected: > 0 — this is the injected invalid-timestamp issue)"
    )

    h = tables["order_status_history"].sort_values(["order_id", "history_id"])
    non_decreasing = h.groupby("order_id")["changed_at"].apply(lambda s: (s.diff().dropna() >= pd.Timedelta(0)).all())
    backwards_orders = int((~non_decreasing).sum())
    lines.append(
        f"- order_status_history: orders with a backwards timestamp between consecutive stages: "
        f"{backwards_orders} (expected: 0)"
    )

    o = tables["orders"]
    out_of_window = int(((o["order_placed_at"] < config_start) | (o["order_placed_at"] > config_end)).sum())
    lines.append(f"- orders: order_placed_at outside the configured generation window: {out_of_window} (expected: 0)")

    merged = d.merge(o[["order_id", "order_placed_at"]], on="order_id", how="left")
    assigned_before_placed = int((merged["assigned_at"] < merged["order_placed_at"]).sum())
    lines.append(f"- deliveries: assigned_at earlier than the order's order_placed_at: {assigned_before_placed} (expected: 0)")

    return lines


def check_status_consistency(tables: dict) -> list:
    lines = ["", "## Status consistency", ""]

    o = tables["orders"]
    h = tables["order_status_history"]

    invalid_order_status = int((~o["status"].isin(ALLOWED_ORDER_STATUSES)).sum())
    lines.append(f"- orders.status values outside the allowed set: {invalid_order_status} (expected: 0)")

    invalid_history_status = int((~h["status"].isin(ALLOWED_ORDER_STATUSES)).sum())
    lines.append(f"- order_status_history.status values outside the allowed set: {invalid_history_status} (expected: 0)")

    last_history_status = h.sort_values(["order_id", "history_id"]).groupby("order_id")["status"].last()
    joined = o.set_index("order_id")["status"].to_frame("orders_status").join(
        last_history_status.rename("last_history_status")
    )
    mismatches = int((joined["orders_status"] != joined["last_history_status"]).sum())
    lines.append(
        f"- orders whose orders.status disagrees with the last order_status_history entry: {mismatches} "
        f"(expected: > 0 — this is the injected status-mismatch issue)"
    )

    delivered_orders = o[o["status"] == "delivered"]["order_id"]
    stage_counts = h[h["order_id"].isin(delivered_orders)].groupby("order_id").size()
    incomplete_delivered = int((stage_counts < 6).sum())
    lines.append(
        f"- delivered orders with fewer than the expected 6 history stages: {incomplete_delivered} "
        f"(expected: > 0 — some are the injected skipped-stage issue)"
    )

    return lines


def main():
    input_dir = sys.argv[1] if len(sys.argv) > 1 else "output"
    tables = load_tables(input_dir)

    # Generation window used by generate_data.py's default run: it normalizes
    # the start date to midnight, then lays out `number_of_days` full
    # calendar days from there (see generate_orders_and_items). Mirror that
    # exact logic here rather than using a raw end_date - 90d boundary, or
    # every order on the first partial day would be flagged incorrectly.
    end_date = pd.Timestamp("2025-06-30 23:59:59")
    number_of_days = 90
    config_start = (end_date - pd.Timedelta(days=number_of_days)).normalize()
    config_end = config_start + pd.Timedelta(days=number_of_days) - pd.Timedelta(seconds=1)

    report = ["# Data Generator Validation Report", ""]
    report += check_row_counts(tables)

    dup_lines, ids_clean = check_duplicate_ids(tables)
    report += dup_lines

    fk_lines, fk_clean = check_foreign_keys(tables)
    report += fk_lines

    report += check_timestamp_consistency(tables, config_start, config_end)
    report += check_status_consistency(tables)

    report += ["", "## Summary", ""]
    report.append(f"- Surrogate primary keys unique across all tables: {'YES' if ids_clean else 'NO'}")
    report.append(f"- Foreign-key relationships fully intact: {'YES' if fk_clean else 'NO'}")
    report.append(
        "- Data-quality issue counts above are expected to be non-zero where noted — "
        "they are the deliberately injected problems this dataset is meant to have."
    )

    text = "\n".join(report)
    print(text)

    out_path = os.path.join(input_dir, "validation_report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"\nReport written to: {out_path}")


if __name__ == "__main__":
    main()
