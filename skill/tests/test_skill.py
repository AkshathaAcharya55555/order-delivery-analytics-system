"""
End-to-end tests for the order-delivery-analytics skill.

    python -m pytest skill/tests -q

Generates the demo dataset (with known injected defects) and asserts the audit
finds exactly what was injected, that KPIs are identical when the same data is
renamed to a foreign schema and auto-mapped, and that the SQL source path
matches the CSV path.
"""

import json
import os
import shutil
import sqlite3
import subprocess
import sys

import pandas as pd
import pytest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "order-delivery-analytics", "scripts")
sys.path.insert(0, SCRIPTS)

import generate_demo_data  # noqa: E402
import dq_audit  # noqa: E402
import kpi_report  # noqa: E402
from _common import load_mapping, load_dataset, settings  # noqa: E402


def run(script, *args, env=None):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args],
                          capture_output=True, text=True, encoding="utf-8", env=env)


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    d = tmp_path_factory.mktemp("demo")
    assert generate_demo_data.main(["--out", str(d), "--orders", "8000", "--days", "45"]) == 0
    return d


def results_by_id(mapping_path):
    return {r.rule_id: r for r in dq_audit.run(load_mapping(str(mapping_path)))}


def test_audit_finds_exactly_the_injected_defects(demo):
    frames, injected = generate_demo_data.generate(8000, 45, 42, True, pd.Timestamp("2026-06-30 23:59:59"))
    r = results_by_id(demo / "mapping.json")
    assert r["DQ-04"].failed == injected["delivered_before_pickup (DQ-04)"]
    assert r["DQ-05"].failed == injected["status_drift (DQ-05)"]
    assert r["DQ-06"].failed == injected["  of which delivered_without_rider (DQ-06)"]
    assert r["DQ-03"].failed == injected["duplicate_events (DQ-03)"]
    assert r["DQ-10"].status == "FAIL"
    for clean in ("DQ-01", "DQ-02", "DQ-07", "DQ-08", "DQ-13", "DQ-14"):
        assert r[clean].status == "PASS", clean


def test_clean_dataset_has_no_failures(tmp_path):
    assert generate_demo_data.main(["--out", str(tmp_path), "--orders", "3000", "--no-issues"]) == 0
    r = results_by_id(tmp_path / "mapping.json")
    assert [k for k, v in r.items() if v.status in ("FAIL", "ERROR") and k != "DQ-12"] == []


def test_exit_codes(demo, tmp_path):
    ok = run("dq_audit.py", "--mapping", str(demo / "mapping.json"), "--out", str(tmp_path / "a.md"))
    assert ok.returncode == 0, ok.stderr                       # only HIGH/LOW failures
    gate = run("dq_audit.py", "--mapping", str(demo / "mapping.json"), "--out", str(tmp_path / "b.md"),
               "--fail-on", "HIGH")
    assert gate.returncode == 1
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"source": {"type": "csv", "path": str(demo)},
                               "tables": {"orders": {"from": "orders.csv", "columns": {
                                   "order_id": "nope", "placed_at": "order_placed_at", "status": "status"}}}}))
    err = run("kpi_report.py", "--mapping", str(bad), "--out", str(tmp_path / "c.md"))
    assert err.returncode == 2 and "nope" in err.stderr


def test_kpi_report_content(demo, tmp_path):
    out = tmp_path / "kpi.md"
    p = run("kpi_report.py", "--mapping", str(demo / "mapping.json"), "--out", str(out), "--json", str(tmp_path / "k.json"))
    assert p.returncode == 0, p.stderr
    md = out.read_text(encoding="utf-8")
    for section in ("## Key findings", "## City scorecard", "## Riders", "## Order funnel", "heatmap"):
        assert section in md
    m = load_mapping(str(demo / "mapping.json"))
    k = kpi_report.compute(load_dataset(m), settings(m))
    assert len(k["city"]) == 6                                   # dirty spellings merged
    assert k["city"]["sla_breach_pct"].idxmax() == "Miami"       # designed-in pattern
    # both deliberately under-supplied cities carry the highest load per rider
    assert set(k["city"]["orders_per_rider"].nlargest(2).index) == {"Miami", "Portland"}
    assert 0 < k["delivery"]["p50"] < k["delivery"]["p90"]
    json.loads((tmp_path / "k.json").read_text())


def test_foreign_schema_is_auto_mapped(demo, tmp_path):
    o = pd.read_csv(demo / "orders.csv").merge(pd.read_csv(demo / "locations.csv")[["location_id", "city"]],
                                              left_on="delivery_location_id", right_on="location_id")
    o["status"] = o["status"].map({"DELIVERED": "completed", "CANCELLED": "canceled_by_customer",
                                   "FAILED": "delivery_failed"}).fillna(o["status"].str.lower())
    o.rename(columns={"order_id": "id", "customer_id": "user_id", "city": "delivery_city",
                      "status": "order_status", "order_placed_at": "created_at", "total_amount": "grand_total"})[
        ["id", "user_id", "delivery_city", "order_status", "created_at", "grand_total"]].to_csv(tmp_path / "sales_orders.csv", index=False)
    pd.read_csv(demo / "deliveries.csv").rename(columns={"rider_id": "driver_id", "picked_up_at": "pickup_time",
                                                         "delivered_at": "dropoff_at", "assigned_at": "accepted_at"})[
        ["order_id", "driver_id", "accepted_at", "pickup_time", "dropoff_at"]].to_csv(tmp_path / "shipments.csv", index=False)
    p = run("profile_source.py", "--csv-dir", str(tmp_path), "--out", str(tmp_path / "m.json"))
    assert p.returncode == 0, p.stderr
    m_foreign, m_demo = load_mapping(str(tmp_path / "m.json")), load_mapping(str(demo / "mapping.json"))
    a = kpi_report.compute(load_dataset(m_foreign), settings(m_foreign))
    b = kpi_report.compute(load_dataset(m_demo), settings(m_demo))
    assert a["headline"]["orders"] == b["headline"]["orders"]
    assert a["headline"]["gmv"] == pytest.approx(b["headline"]["gmv"])
    assert a["delivery"]["p90"] == pytest.approx(b["delivery"]["p90"])


def test_sql_source_matches_csv(demo, tmp_path):
    db = tmp_path / "demo.sqlite"
    con = sqlite3.connect(db)
    for f in os.listdir(demo):
        if f.endswith(".csv"):
            pd.read_csv(demo / f).to_sql(f[:-4], con, index=False)
    con.close()
    env = dict(os.environ, TEST_DB_URL=f"sqlite:///{db}")
    p = run("profile_source.py", "--sql", "--url-env", "TEST_DB_URL", "--out", str(tmp_path / "m.json"), env=env)
    assert p.returncode == 0, p.stderr
    os.environ["TEST_DB_URL"] = env["TEST_DB_URL"]
    import _common
    _common._ENGINE = None
    try:
        r_sql = {x.rule_id: x.failed for x in dq_audit.run(load_mapping(str(tmp_path / "m.json")))}
    finally:
        _common._ENGINE = None
    r_csv = {x.rule_id: x.failed for x in dq_audit.run(load_mapping(str(demo / "mapping.json")))}
    assert r_sql == r_csv


def test_package_builds(tmp_path):
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "..", "..", "build_zip.py")],
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stdout + p.stderr
