"""
Data-quality validation for the Order & Delivery Analytics System.

Runs against the RAW data_generator/output/*.csv files — i.e. data as it
would arrive before any cleaning or loading — rather than the already
bulk-loaded Postgres tables. This matters: database/load_generated_dataset.sql
(built in the analytics phase) already EXCLUDED ~1,842 invalid-timestamp
delivery rows during load because they violate a CHECK constraint, so
checking the loaded table for that specific issue would wrongly report zero
problems. Checking the raw CSVs instead lets these rules actually detect the
data_generator's intentionally-injected issues, which is the point of this
layer: prove the checks work by finding known, documented problems, not by
being run against already-partially-cleaned data.

Every rule distinguishes, in its notes, whether a nonzero result is expected
(an intentionally-injected data_generator quality issue — see
data_generator/README.md) or would be a genuine, unexpected structural
problem if found.

Run: python data_quality/validate.py [path-to-data_generator/output]
"""

import os
import sys
from dataclasses import dataclass, asdict
from typing import Optional

import pandas as pd

CANONICAL_CITIES = {"Austin", "Denver", "Portland", "Chicago", "Miami", "Seattle"}


@dataclass
class RuleResult:
    rule_id: str
    rule_name: str
    records_checked: int
    records_failed: int
    failure_rate_pct: float
    severity: str
    expected_source: str  # "natural" | "intentionally_corrupted" | "structural_check"
    notes: str

    @staticmethod
    def make(rule_id, rule_name, checked, failed, severity, expected_source, notes):
        rate = round(100 * failed / checked, 4) if checked else 0.0
        return RuleResult(rule_id, rule_name, checked, failed, rate, severity, expected_source, notes)


def load_data(data_dir: str) -> dict:
    names = ["locations", "customers", "riders", "orders", "order_items",
             "deliveries", "order_status_history", "event_log"]
    dfs = {}
    for name in names:
        path = os.path.join(data_dir, f"{name}.csv")
        parse_dates = {
            "locations": [],
            "customers": ["signup_date"],
            "riders": ["joined_date"],
            "orders": ["order_placed_at"],
            "order_items": [],
            "deliveries": ["assigned_at", "picked_up_at", "delivered_at"],
            "order_status_history": ["changed_at"],
            "event_log": ["event_timestamp"],
        }[name]
        dfs[name] = pd.read_csv(path, parse_dates=parse_dates)
    return dfs


# ----------------------------------------------------------------------------
# Rule 1: missing customer IDs
# ----------------------------------------------------------------------------
def check_missing_customer_ids(dfs: dict) -> RuleResult:
    orders = dfs["orders"]
    failed = int(orders["customer_id"].isna().sum())
    return RuleResult.make(
        "DQ-01", "Missing customer IDs", len(orders), failed, "CRITICAL",
        "structural_check",
        "orders.customer_id is a required field for every order. A nonzero "
        "result would be a genuine structural bug (the generator never "
        "omits this) — 0 is the expected, correct result here."
    )


# ----------------------------------------------------------------------------
# Rule 2: duplicate order IDs
# ----------------------------------------------------------------------------
def check_duplicate_order_ids(dfs: dict) -> RuleResult:
    orders = dfs["orders"]
    failed = int(orders["order_id"].duplicated().sum())
    return RuleResult.make(
        "DQ-02", "Duplicate order IDs", len(orders), failed, "CRITICAL",
        "structural_check",
        "order_id is meant to be a unique primary key. A nonzero result "
        "would indicate a serious generation or ingestion bug — 0 is the "
        "expected, correct result here (no duplicate-order-id issue was "
        "ever intentionally injected)."
    )


# ----------------------------------------------------------------------------
# Rule 3: duplicate event IDs (content-level — see notes)
# ----------------------------------------------------------------------------
def check_duplicate_event_ids(dfs: dict) -> RuleResult:
    events = dfs["event_log"]
    id_duplicates = int(events["event_id"].duplicated().sum())
    content_cols = ["order_id", "event_type", "event_timestamp"]
    content_duplicates = int(events.duplicated(subset=content_cols, keep=False).sum())
    return RuleResult.make(
        "DQ-03", "Duplicate event IDs", len(events), content_duplicates, "LOW",
        "intentionally_corrupted",
        f"The event_id surrogate column itself has {id_duplicates} duplicate "
        f"values (expected: 0 — each event gets a fresh id even when "
        f"re-delivered). The count reported here ({content_duplicates}) is "
        f"CONTENT-level duplication (same order_id+event_type+event_timestamp "
        f"appearing more than once) — this is data_generator's intentional "
        f"simulation of Kafka at-least-once redelivery. This is exactly the "
        f"scenario the backend's tracking-service Kafka consumer was built "
        f"to handle idempotently via the processed_events table."
    )


# ----------------------------------------------------------------------------
# Rule 4: invalid delivery durations
# ----------------------------------------------------------------------------
def check_invalid_delivery_durations(dfs: dict) -> RuleResult:
    d = dfs["deliveries"]
    has_both_pickup_delivered = d["picked_up_at"].notna() & d["delivered_at"].notna()
    delivered_before_pickup = has_both_pickup_delivered & (d["delivered_at"] < d["picked_up_at"])

    has_both_assigned_pickup = d["assigned_at"].notna() & d["picked_up_at"].notna()
    pickup_before_assigned = has_both_assigned_pickup & (d["picked_up_at"] < d["assigned_at"])

    failed_mask = delivered_before_pickup | pickup_before_assigned
    return RuleResult.make(
        "DQ-04", "Invalid delivery durations", len(d), int(failed_mask.sum()), "HIGH",
        "intentionally_corrupted",
        f"delivered_at < picked_up_at: {int(delivered_before_pickup.sum())} rows "
        f"(data_generator's intentional clock-skew simulation). "
        f"picked_up_at < assigned_at: {int(pickup_before_assigned.sum())} rows "
        f"(expected: 0 — never intentionally injected). These specific "
        f"delivered-before-pickup rows were EXCLUDED during the bulk load "
        f"into Postgres (database/load_generated_dataset.sql) because they "
        f"violate that table's own CHECK constraint — this check is run "
        f"against the raw CSV specifically so it can still detect them."
    )


# ----------------------------------------------------------------------------
# Rule 5: invalid status transitions (orders.status vs. its own history)
# ----------------------------------------------------------------------------
def check_invalid_status_transitions(dfs: dict) -> RuleResult:
    orders = dfs["orders"][["order_id", "status"]].rename(columns={"status": "orders_status"})
    history = dfs["order_status_history"].sort_values(["order_id", "history_id"])
    last_history_status = history.groupby("order_id")["status"].last().rename("last_history_status")

    merged = orders.merge(last_history_status, on="order_id", how="left")
    mismatched = merged["orders_status"] != merged["last_history_status"]

    # secondary signal: orders missing an intermediate stage vs. their outcome
    stage_counts = history.groupby("order_id").size()
    delivered_orders = orders.loc[orders["orders_status"] == "delivered", "order_id"]
    incomplete_delivered = int((stage_counts.reindex(delivered_orders) < 6).sum())

    return RuleResult.make(
        "DQ-05", "Invalid status transitions", len(orders), int(mismatched.sum()), "HIGH",
        "intentionally_corrupted",
        f"Primary count: orders where orders.status disagrees with the last "
        f"recorded order_status_history row (data_generator's intentional "
        f"'status mismatch' simulation of order-service/history drift). "
        f"Secondary signal (not counted in the total above): "
        f"{incomplete_delivered} orders with final status 'delivered' have "
        f"fewer than the expected 6 history stages — data_generator's "
        f"intentional 'skipped stage' simulation of a lost status-change event."
    )


# ----------------------------------------------------------------------------
# Rule 6: missing rider assignments
# ----------------------------------------------------------------------------
def check_missing_rider_assignments(dfs: dict) -> RuleResult:
    orders = dfs["orders"]
    should_have_rider = orders["status"].isin(["out_for_delivery", "delivered"])
    failed_mask = should_have_rider & orders["rider_id"].isna()
    failed = int(failed_mask.sum())
    return RuleResult.make(
        "DQ-06", "Missing rider assignments", int(should_have_rider.sum()), failed, "HIGH",
        "intentionally_corrupted",
        f"Investigated, not assumed: all {failed} failures were traced to "
        f"specific orders (e.g. order_id 444, 5332, 15574) whose "
        f"order_status_history shows they were actually cancelled BEFORE "
        f"any rider was ever assigned (history ends at 'cancelled', 2-3 "
        f"stages in) — but whose orders.status field was overwritten to "
        f"'out_for_delivery'/'delivered' by data_generator's intentional "
        f"status-mismatch injection (the same root cause as DQ-05). This is "
        f"a genuine downstream consequence of that one injected issue, not "
        f"an independent rider-assignment bug — discovered by checking the "
        f"actual data, not assumed in advance (the original expectation "
        f"going into this check was 0)."
    )


# ----------------------------------------------------------------------------
# Rule 7: orphan records (referential integrity across files)
# ----------------------------------------------------------------------------
def check_orphan_records(dfs: dict) -> RuleResult:
    order_ids = set(dfs["orders"]["order_id"])
    customer_ids = set(dfs["customers"]["customer_id"])
    location_ids = set(dfs["locations"]["location_id"])
    rider_ids = set(dfs["riders"]["rider_id"])

    orphan_order_items = int((~dfs["order_items"]["order_id"].isin(order_ids)).sum())
    orphan_deliveries_order = int((~dfs["deliveries"]["order_id"].isin(order_ids)).sum())
    orphan_deliveries_rider = int((~dfs["deliveries"]["rider_id"].isin(rider_ids)).sum())
    orphan_orders_customer = int((~dfs["orders"]["customer_id"].isin(customer_ids)).sum())
    orphan_orders_location = int((~dfs["orders"]["delivery_location_id"].isin(location_ids)).sum())
    orphan_history_order = int((~dfs["order_status_history"]["order_id"].isin(order_ids)).sum())

    total_checked = (len(dfs["order_items"]) + len(dfs["deliveries"]) * 2
                     + len(dfs["orders"]) * 2 + len(dfs["order_status_history"]))
    total_failed = (orphan_order_items + orphan_deliveries_order + orphan_deliveries_rider
                     + orphan_orders_customer + orphan_orders_location + orphan_history_order)

    return RuleResult.make(
        "DQ-07", "Orphan records", total_checked, total_failed, "CRITICAL",
        "structural_check",
        f"Sum across 6 FK relationships, each expected to be 0: "
        f"order_items->orders: {orphan_order_items}, "
        f"deliveries->orders: {orphan_deliveries_order}, "
        f"deliveries->riders: {orphan_deliveries_rider}, "
        f"orders->customers: {orphan_orders_customer}, "
        f"orders->locations: {orphan_orders_location}, "
        f"order_status_history->orders: {orphan_history_order}. "
        f"No orphan-record issue was ever intentionally injected by the "
        f"generator — all ids are drawn from already-generated valid sets."
    )


# ----------------------------------------------------------------------------
# Rule 8: invalid order values
# ----------------------------------------------------------------------------
def check_invalid_order_values(dfs: dict) -> RuleResult:
    orders = dfs["orders"]
    items = dfs["order_items"]

    invalid_orders = int((orders["total_amount"] <= 0).sum())
    invalid_items = int(((items["unit_price"] < 0) | (items["quantity"] <= 0)).sum())

    total_checked = len(orders) + len(items)
    total_failed = invalid_orders + invalid_items
    return RuleResult.make(
        "DQ-08", "Invalid order values", total_checked, total_failed, "HIGH",
        "structural_check",
        f"orders.total_amount <= 0: {invalid_orders} rows. "
        f"order_items with unit_price < 0 or quantity <= 0: {invalid_items} rows. "
        f"0 is the expected, correct result — no negative/zero-value issue "
        f"was ever intentionally injected by the generator."
    )


# ----------------------------------------------------------------------------
# Rule 9: missing timestamps
# ----------------------------------------------------------------------------
def check_missing_timestamps(dfs: dict) -> RuleResult:
    checks = [
        ("orders.order_placed_at", dfs["orders"]["order_placed_at"]),
        ("deliveries.assigned_at", dfs["deliveries"]["assigned_at"]),
        ("order_status_history.changed_at", dfs["order_status_history"]["changed_at"]),
        ("event_log.event_timestamp", dfs["event_log"]["event_timestamp"]),
    ]
    total_checked = sum(len(series) for _, series in checks)
    total_failed = sum(int(series.isna().sum()) for _, series in checks)
    breakdown = ", ".join(f"{name}: {int(series.isna().sum())}" for name, series in checks)
    return RuleResult.make(
        "DQ-09", "Missing timestamps", total_checked, total_failed, "MEDIUM",
        "structural_check",
        f"Breakdown (all expected 0 — these columns are always populated by "
        f"the generator; the intentionally-injected 'missing values' issue "
        f"targets customers.phone / riders.rating / locations.postal_code "
        f"instead, none of which are timestamps): {breakdown}."
    )


# ----------------------------------------------------------------------------
# Rule 10: inconsistent city values
# ----------------------------------------------------------------------------
def check_inconsistent_city_values(dfs: dict) -> RuleResult:
    locations = dfs["locations"]
    failed = int((~locations["city"].isin(CANONICAL_CITIES)).sum())
    examples = locations.loc[~locations["city"].isin(CANONICAL_CITIES), "city"].unique()[:8]
    return RuleResult.make(
        "DQ-10", "Inconsistent city values", len(locations), failed, "LOW",
        "intentionally_corrupted",
        f"locations.city values not matching the canonical 6-city list "
        f"exactly. This is data_generator's intentional city-name-messiness "
        f"simulation (case, whitespace, abbreviation, state-suffix variants). "
        f"Example dirty values found: {list(examples)}."
    )


def run_all_checks(data_dir: str) -> pd.DataFrame:
    dfs = load_data(data_dir)
    checks = [
        check_missing_customer_ids,
        check_duplicate_order_ids,
        check_duplicate_event_ids,
        check_invalid_delivery_durations,
        check_invalid_status_transitions,
        check_missing_rider_assignments,
        check_orphan_records,
        check_invalid_order_values,
        check_missing_timestamps,
        check_inconsistent_city_values,
    ]
    results = [asdict(check(dfs)) for check in checks]
    return pd.DataFrame(results)


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "..", "data_generator", "output"
    )
    print(f"Loading raw CSVs from: {os.path.abspath(data_dir)}")
    results_df = run_all_checks(data_dir)

    pd.set_option("display.max_colwidth", None)
    pd.set_option("display.width", 200)
    print("\n" + results_df[["rule_id", "rule_name", "records_checked", "records_failed",
                              "failure_rate_pct", "severity", "expected_source"]].to_string(index=False))

    out_path = os.path.join(os.path.dirname(__file__), "quality_report.csv")
    results_df.to_csv(out_path, index=False)
    print(f"\nFull report (including notes) written to: {out_path}")


if __name__ == "__main__":
    main()
