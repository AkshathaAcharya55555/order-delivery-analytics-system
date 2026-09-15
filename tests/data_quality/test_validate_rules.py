"""
Unit tests for data_quality/validate.py's ten check_* rule functions.

Each test builds a small, hand-crafted set of DataFrames (not the full
generated CSVs - these are fast, self-contained, deterministic checks of the
rule LOGIC itself) covering: a clean case (0 failures expected) and a dirty
case (a specific, known violation the rule must catch). This is the layer
of testing the data-quality phase never had: validate.py was previously
verified only by running it against the real dataset and eyeballing the
output, never by asserting its rule functions actually detect a violation
they're supposed to.
"""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data_quality")))
import validate  # noqa: E402


def _base_dfs():
    """A minimal, internally-consistent set of tables: 2 clean orders, one
    delivered end-to-end, one still placed. Every rule should report 0
    failures against this baseline unless a test deliberately corrupts it."""
    locations = pd.DataFrame({
        "location_id": [1, 2],
        "city": ["Austin", "Denver"],
    })
    customers = pd.DataFrame({
        "customer_id": [1, 2],
        "signup_date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
    })
    riders = pd.DataFrame({
        "rider_id": [1],
        "joined_date": pd.to_datetime(["2026-01-01"]),
    })
    orders = pd.DataFrame({
        "order_id": [1, 2],
        "customer_id": [1, 2],
        "delivery_location_id": [1, 2],
        "rider_id": [1, None],
        "status": ["delivered", "placed"],
        "order_placed_at": pd.to_datetime(["2026-01-01 10:00", "2026-01-02 10:00"]),
        "total_amount": [25.0, 10.0],
    })
    order_items = pd.DataFrame({
        "order_id": [1, 2],
        "unit_price": [25.0, 10.0],
        "quantity": [1, 1],
    })
    deliveries = pd.DataFrame({
        "order_id": [1],
        "rider_id": [1],
        "assigned_at": pd.to_datetime(["2026-01-01 10:05"]),
        "picked_up_at": pd.to_datetime(["2026-01-01 10:15"]),
        "delivered_at": pd.to_datetime(["2026-01-01 10:45"]),
    })
    order_status_history = pd.DataFrame({
        "history_id": [1, 2, 3, 4, 5, 6, 7],
        "order_id": [1, 1, 1, 1, 1, 1, 2],
        "status": ["placed", "confirmed", "preparing", "ready_for_pickup",
                    "rider_assigned", "delivered", "placed"],
        "changed_at": pd.to_datetime([
            "2026-01-01 10:00", "2026-01-01 10:01", "2026-01-01 10:02",
            "2026-01-01 10:03", "2026-01-01 10:04", "2026-01-01 10:45",
            "2026-01-02 10:00",
        ]),
    })
    event_log = pd.DataFrame({
        "event_id": [1, 2],
        "order_id": [1, 2],
        "event_type": ["ORDER_CREATED", "ORDER_CREATED"],
        "event_timestamp": pd.to_datetime(["2026-01-01 10:00", "2026-01-02 10:00"]),
    })
    return {
        "locations": locations, "customers": customers, "riders": riders,
        "orders": orders, "order_items": order_items, "deliveries": deliveries,
        "order_status_history": order_status_history, "event_log": event_log,
    }


class TestMissingCustomerIds:
    def test_clean_data_reports_zero(self):
        result = validate.check_missing_customer_ids(_base_dfs())
        assert result.records_failed == 0

    def test_null_customer_id_is_detected(self):
        dfs = _base_dfs()
        dfs["orders"].loc[0, "customer_id"] = None
        result = validate.check_missing_customer_ids(dfs)
        assert result.records_failed == 1


class TestDuplicateOrderIds:
    def test_clean_data_reports_zero(self):
        result = validate.check_duplicate_order_ids(_base_dfs())
        assert result.records_failed == 0

    def test_duplicate_id_is_detected(self):
        dfs = _base_dfs()
        dfs["orders"].loc[1, "order_id"] = 1  # now a duplicate of row 0
        result = validate.check_duplicate_order_ids(dfs)
        assert result.records_failed == 1


class TestDuplicateEventIds:
    def test_clean_data_reports_zero(self):
        result = validate.check_duplicate_event_ids(_base_dfs())
        assert result.records_failed == 0

    def test_content_level_redelivery_is_detected(self):
        dfs = _base_dfs()
        redelivered = dfs["event_log"].iloc[[0]].copy()
        redelivered["event_id"] = 3  # fresh surrogate id, same content -> simulates Kafka at-least-once redelivery
        dfs["event_log"] = pd.concat([dfs["event_log"], redelivered], ignore_index=True)
        result = validate.check_duplicate_event_ids(dfs)
        assert result.records_failed == 2  # both rows sharing that content are flagged


class TestInvalidDeliveryDurations:
    def test_clean_data_reports_zero(self):
        result = validate.check_invalid_delivery_durations(_base_dfs())
        assert result.records_failed == 0

    def test_delivered_before_pickup_is_detected(self):
        dfs = _base_dfs()
        dfs["deliveries"].loc[0, "delivered_at"] = pd.Timestamp("2026-01-01 10:10")  # before picked_up_at 10:15
        result = validate.check_invalid_delivery_durations(dfs)
        assert result.records_failed == 1

    def test_pickup_before_assignment_is_detected(self):
        dfs = _base_dfs()
        dfs["deliveries"].loc[0, "picked_up_at"] = pd.Timestamp("2026-01-01 10:00")  # before assigned_at 10:05
        result = validate.check_invalid_delivery_durations(dfs)
        assert result.records_failed == 1


class TestInvalidStatusTransitions:
    def test_clean_data_reports_zero(self):
        result = validate.check_invalid_status_transitions(_base_dfs())
        assert result.records_failed == 0

    def test_status_mismatch_is_detected(self):
        dfs = _base_dfs()
        dfs["orders"].loc[1, "status"] = "delivered"  # history's last entry for order 2 is still "placed"
        result = validate.check_invalid_status_transitions(dfs)
        assert result.records_failed == 1


class TestMissingRiderAssignments:
    def test_clean_data_reports_zero(self):
        result = validate.check_missing_rider_assignments(_base_dfs())
        assert result.records_failed == 0

    def test_delivered_without_rider_is_detected(self):
        dfs = _base_dfs()
        dfs["orders"].loc[1, "status"] = "delivered"  # order 2 has rider_id=None
        result = validate.check_missing_rider_assignments(dfs)
        assert result.records_failed == 1


class TestOrphanRecords:
    def test_clean_data_reports_zero(self):
        result = validate.check_orphan_records(_base_dfs())
        assert result.records_failed == 0

    def test_orphan_order_item_is_detected(self):
        dfs = _base_dfs()
        orphan = pd.DataFrame({"order_id": [999], "unit_price": [1.0], "quantity": [1]})
        dfs["order_items"] = pd.concat([dfs["order_items"], orphan], ignore_index=True)
        result = validate.check_orphan_records(dfs)
        assert result.records_failed == 1

    def test_orphan_delivery_rider_is_detected(self):
        dfs = _base_dfs()
        dfs["deliveries"].loc[0, "rider_id"] = 999  # no such rider
        result = validate.check_orphan_records(dfs)
        assert result.records_failed == 1


class TestInvalidOrderValues:
    def test_clean_data_reports_zero(self):
        result = validate.check_invalid_order_values(_base_dfs())
        assert result.records_failed == 0

    def test_zero_total_amount_is_detected(self):
        dfs = _base_dfs()
        dfs["orders"].loc[0, "total_amount"] = 0.0
        result = validate.check_invalid_order_values(dfs)
        assert result.records_failed == 1

    def test_negative_unit_price_is_detected(self):
        dfs = _base_dfs()
        dfs["order_items"].loc[0, "unit_price"] = -1.0
        result = validate.check_invalid_order_values(dfs)
        assert result.records_failed == 1


class TestMissingTimestamps:
    def test_clean_data_reports_zero(self):
        result = validate.check_missing_timestamps(_base_dfs())
        assert result.records_failed == 0

    def test_missing_order_placed_at_is_detected(self):
        dfs = _base_dfs()
        dfs["orders"].loc[0, "order_placed_at"] = pd.NaT
        result = validate.check_missing_timestamps(dfs)
        assert result.records_failed == 1


class TestInconsistentCityValues:
    def test_clean_data_reports_zero(self):
        result = validate.check_inconsistent_city_values(_base_dfs())
        assert result.records_failed == 0

    def test_dirty_city_name_is_detected(self):
        dfs = _base_dfs()
        dfs["locations"].loc[0, "city"] = "AUSTIN "  # not in CANONICAL_CITIES exactly
        result = validate.check_inconsistent_city_values(dfs)
        assert result.records_failed == 1


class TestRunAllChecks:
    def test_run_all_checks_against_clean_baseline(self, tmp_path):
        dfs = _base_dfs()
        for name, df in dfs.items():
            df.to_csv(tmp_path / f"{name}.csv", index=False)
        result = validate.run_all_checks(str(tmp_path))
        assert len(result) == 10
        assert set(result["rule_id"]) == {f"DQ-{i:02d}" for i in range(1, 11)}
        # against this clean baseline every rule should report 0 failures
        assert result["records_failed"].sum() == 0
