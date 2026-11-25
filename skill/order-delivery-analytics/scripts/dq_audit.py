#!/usr/bin/env python3
"""
Data-quality audit for order & delivery data.

Usage:
    python dq_audit.py --mapping mapping.json [--out dq_report.md] [--json dq_report.json]
                       [--fail-on CRITICAL|HIGH|MEDIUM|LOW|NONE]

Runs up to 14 rules against the canonical model (rules whose inputs are not
mapped are reported as SKIPPED, never silently passed). Writes a markdown
report with counts, failure rates, sample offending keys and a remediation
hint per rule. Exit code is 1 if any rule at or above --fail-on severity
fails (default CRITICAL), so it can gate a CI / pipeline step.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Callable, List, Optional

import pandas as pd

sys.path.insert(0, __import__("os").path.dirname(__file__))
from _common import (load_mapping, load_dataset, settings, md_table, normalize_categories,  # noqa: E402
                     MappingError, eprint)

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


@dataclass
class Result:
    rule_id: str
    name: str
    severity: str
    status: str  # PASS | FAIL | SKIPPED
    checked: int = 0
    failed: int = 0
    rate_pct: float = 0.0
    detail: str = ""
    samples: List[str] = field(default_factory=list)
    fix: str = ""


def _res(rule_id, name, severity, checked, failed_mask_or_count, detail="", samples=None, fix=""):
    failed = int(failed_mask_or_count.sum()) if hasattr(failed_mask_or_count, "sum") else int(failed_mask_or_count)
    rate = round(100.0 * failed / checked, 3) if checked else 0.0
    samples = [] if samples is None else list(samples)
    return Result(rule_id, name, severity, "FAIL" if failed else "PASS", int(checked), failed, rate,
                  detail, [str(s) for s in samples][:5], fix)


def _skip(rule_id, name, severity, why):
    return Result(rule_id, name, severity, "SKIPPED", detail=why)


def _has(df: Optional[pd.DataFrame], *cols) -> bool:
    return df is not None and all(c in df.columns for c in cols)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
def r01_missing_keys(d, s):
    o = d["orders"]
    cols = [c for c in ("order_id", "customer_id") if c in o.columns]
    mask = o[cols].isna().any(axis=1)
    return _res("DQ-01", "Missing order / customer keys", "CRITICAL", len(o), mask,
                f"Checked columns: {cols}",
                o.index[mask][:5].map(lambda i: f"row {i}"),
                "Reject at ingestion; keys must be NOT NULL in the source system.")


def r02_duplicate_orders(d, s):
    o = d["orders"]
    mask = o["order_id"].notna() & o["order_id"].duplicated(keep="first")
    return _res("DQ-02", "Duplicate order IDs", "CRITICAL", len(o), mask, "",
                o.loc[mask, "order_id"].unique()[:5],
                "Enforce a unique key; de-duplicate keeping the latest version of each order.")


def r03_duplicate_events(d, s):
    e = d["events"]
    if not _has(e, "order_id", "event_type", "event_timestamp"):
        return _skip("DQ-03", "Duplicate events (redelivery)", "LOW", "events table not mapped")
    content = e.duplicated(subset=["order_id", "event_type", "event_timestamp"], keep="first")
    id_dupes = int(e["event_id"].duplicated().sum()) if "event_id" in e.columns else 0
    return _res("DQ-03", "Duplicate events (redelivery)", "LOW", len(e), content,
                f"Content-level duplicates (same order+type+timestamp). event_id duplicates: {id_dupes}. "
                "Typical of at-least-once delivery (Kafka/SQS/webhooks).",
                e.loc[content, "order_id"].head(5),
                "Make consumers idempotent: dedupe on a producer-assigned event id (processed_events ledger).")


def r04_timestamp_order(d, s):
    dl = d["deliveries"]
    if not _has(dl, "assigned_at", "picked_up_at", "delivered_at"):
        return _skip("DQ-04", "Delivery timestamps out of order", "HIGH", "deliveries assigned/picked_up/delivered not mapped")
    a = dl["picked_up_at"].notna() & dl["assigned_at"].notna() & (dl["picked_up_at"] < dl["assigned_at"])
    b = dl["delivered_at"].notna() & dl["picked_up_at"].notna() & (dl["delivered_at"] < dl["picked_up_at"])
    mask = a | b
    return _res("DQ-04", "Delivery timestamps out of order", "HIGH", len(dl), mask,
                f"picked_up < assigned: {int(a.sum())}; delivered < picked_up: {int(b.sum())}",
                dl.loc[mask, "order_id"].head(5),
                "Usually device clock skew or late events. Use server-side timestamps; quarantine rows "
                "before computing delivery-time KPIs (they produce negative durations).")


def r05_status_vs_history(d, s):
    o, h = d["orders"], d["status_history"]
    if not _has(h, "order_id", "status"):
        return _skip("DQ-05", "Order status disagrees with history", "HIGH", "status_history not mapped")
    sort_cols = ["order_id"] + [c for c in ("changed_at", "seq") if c in h.columns]
    last = h.dropna(subset=["order_id"]).sort_values(sort_cols).groupby("order_id")["status"].last()
    m = o[["order_id", "status"]].merge(last.rename("last_hist").reset_index(), on="order_id", how="inner")
    mask = m["status"].str.lower().str.strip() != m["last_hist"].str.lower().str.strip()
    return _res("DQ-05", "Order status disagrees with history", "HIGH", len(m), mask,
                "Compares orders.status with the most recent status_history row per order.",
                m.loc[mask, "order_id"].head(5),
                "A lost or out-of-order status event. Rebuild current status from the append-only history "
                "(or an outbox) instead of updating two places independently.")


def r06_missing_rider(d, s):
    o = d["orders"]
    if "rider_id" not in o.columns:
        return _skip("DQ-06", "Delivered orders without a rider", "HIGH", "no rider_id on orders or deliveries")
    should = o["outcome"].eq("delivered")
    mask = should & o["rider_id"].isna()
    return _res("DQ-06", "Delivered orders without a rider", "HIGH", int(should.sum()), mask, "",
                o.loc[mask, "order_id"].head(5),
                "Check whether these orders were actually cancelled pre-assignment (see DQ-05) "
                "or whether the assignment event was dropped.")


def r07_orphans(d, s):
    o = d["orders"]
    order_ids = set(o["order_id"].dropna())
    parts, checked, failed, samples = [], 0, 0, []

    def check(label, child: pd.Series, parent_ids: set):
        nonlocal checked, failed
        c = child.dropna()
        bad = c[~c.isin(parent_ids)]
        checked += len(c)
        failed += len(bad)
        parts.append(f"{label}: {len(bad)}")
        samples.extend(bad.head(2).tolist())

    if _has(d["deliveries"], "order_id"):
        check("deliveries→orders", d["deliveries"]["order_id"], order_ids)
    if _has(d["order_items"], "order_id"):
        check("order_items→orders", d["order_items"]["order_id"], order_ids)
    if _has(d["status_history"], "order_id"):
        check("status_history→orders", d["status_history"]["order_id"], order_ids)
    if _has(d["customers"], "customer_id") and "customer_id" in o.columns:
        check("orders→customers", o["customer_id"], set(d["customers"]["customer_id"].dropna()))
    if _has(d["riders"], "rider_id"):
        rider_ids = set(d["riders"]["rider_id"].dropna())
        if _has(d["deliveries"], "rider_id"):
            check("deliveries→riders", d["deliveries"]["rider_id"], rider_ids)
        elif "rider_id" in o.columns:
            check("orders→riders", o["rider_id"], rider_ids)
    if not parts:
        return _skip("DQ-07", "Orphan records", "CRITICAL", "no child tables mapped")
    return _res("DQ-07", "Orphan records", "CRITICAL", checked, failed, "; ".join(parts), samples,
                "Add foreign keys, or load parents before children; investigate partial loads.")


def r08_invalid_amounts(d, s):
    o = d["orders"]
    parts, checked, failed = [], 0, 0
    if "total_amount" in o.columns:
        bad = o["total_amount"].notna() & (o["total_amount"] <= 0)
        parts.append(f"orders.total_amount <= 0: {int(bad.sum())}")
        checked += len(o); failed += int(bad.sum())
    it = d["order_items"]
    if _has(it, "unit_price", "quantity"):
        bad = (it["unit_price"] < 0) | (it["quantity"] <= 0)
        parts.append(f"items with price < 0 or qty <= 0: {int(bad.sum())}")
        checked += len(it); failed += int(bad.sum())
    if not parts:
        return _skip("DQ-08", "Invalid monetary values", "HIGH", "no amount columns mapped")
    return _res("DQ-08", "Invalid monetary values", "HIGH", checked, failed, "; ".join(parts), [],
                "Zero-value orders may be legit (100% promo) — confirm with the business, then add CHECK constraints.")


def r09_missing_timestamps(d, s):
    checks = [("orders.placed_at", d["orders"]["placed_at"])]
    dl = d["deliveries"]
    if _has(dl, "assigned_at"):
        checks.append(("deliveries.assigned_at", dl["assigned_at"]))
    if _has(d["status_history"], "changed_at"):
        checks.append(("status_history.changed_at", d["status_history"]["changed_at"]))
    total = sum(len(x) for _, x in checks)
    failed = sum(int(x.isna().sum()) for _, x in checks)
    return _res("DQ-09", "Missing / unparseable timestamps", "MEDIUM", total, failed,
                ", ".join(f"{n}: {int(x.isna().sum())}" for n, x in checks), [],
                "Unparseable values are counted as missing — check timezone/format consistency at the source.")


def r10_inconsistent_categories(d, s):
    frames = [("orders.city", d["orders"]["city"])]
    if _has(d["riders"], "city"):
        frames.append(("riders.city", d["riders"]["city"]))
    checked = failed = 0
    examples = []
    for label, col in frames:
        vals = col.dropna()
        if vals.empty or (vals == "(all)").all():
            continue
        _, changed, fix = normalize_categories(vals)
        failed += changed
        examples += [f"{label}: '{k}' → '{v}'" for k, v in list(fix.items())[:5]]
        checked += len(vals)
    if checked == 0:
        return _skip("DQ-10", "Inconsistent category spellings", "LOW", "no city column mapped")
    return _res("DQ-10", "Inconsistent category spellings", "LOW", checked, failed,
                "Spelling variants that normalise to the same value (case, whitespace, state suffix, dots).",
                examples, "Normalise on ingest with a lookup table; group-bys on raw values split one city into many.")


def r11_out_of_range_ts(d, s):
    o = d["orders"]
    now = pd.Timestamp(datetime.now(timezone.utc)).tz_convert(None)
    future = o["placed_at"] > now + pd.Timedelta(days=1)
    ancient = o["placed_at"] < pd.Timestamp("2000-01-01")
    mask = future | ancient
    return _res("DQ-11", "Out-of-range order timestamps", "MEDIUM", len(o), mask,
                f"future-dated: {int(future.sum())}; before 2000: {int(ancient.sum())}",
                o.loc[mask, "order_id"].head(5),
                "Often epoch-0 defaults or ms-vs-s unit mix-ups.")


def r12_implausible_durations(d, s):
    dl = d["deliveries"]
    o = d["orders"]
    if not _has(dl, "delivered_at"):
        return _skip("DQ-12", "Implausible delivery durations", "MEDIUM", "deliveries.delivered_at not mapped")
    m = dl[["order_id", "delivered_at"]].merge(o[["order_id", "placed_at"]], on="order_id", how="inner")
    m = m.dropna()
    mins = (m["delivered_at"] - m["placed_at"]).dt.total_seconds() / 60
    max_h = float(s["max_reasonable_delivery_hours"])
    mask = (mins < 1) | (mins > max_h * 60)
    return _res("DQ-12", "Implausible delivery durations", "MEDIUM", len(m), mask,
                f"placed→delivered under 1 minute or over {max_h:g} h "
                f"(<1 min: {int((mins < 1).sum())}, >{max_h:g} h: {int((mins > max_h * 60).sum())})",
                m.loc[mask, "order_id"].head(5),
                "Exclude from SLA KPIs and investigate; scheduled/pre-orders may need their own placed_at.")


def r13_unknown_status(d, s):
    o = d["orders"]
    mask = o["outcome"].eq("unknown")
    vals = o.loc[mask, "status"].value_counts().head(5)
    return _res("DQ-13", "Unmapped status values", "HIGH", len(o), mask,
                "Statuses not covered by mapping.status_map: " + ", ".join(f"'{k}' ({v})" for k, v in vals.items()),
                [], "Add each value to status_map so outcome KPIs are complete.")


def r14_amount_vs_items(d, s):
    o, it = d["orders"], d["order_items"]
    if not (_has(it, "order_id", "unit_price", "quantity") and "total_amount" in o.columns):
        return _skip("DQ-14", "Order total ≠ sum of items", "MEDIUM", "order_items or total_amount not mapped")
    sums = (it["unit_price"] * it["quantity"]).groupby(it["order_id"]).sum().rename("items_total")
    m = o[["order_id", "total_amount"]].merge(sums.reset_index(), on="order_id", how="inner")
    tol = float(s.get("amount_tolerance", 0.01))
    diff = (m["total_amount"] - m["items_total"]).abs()
    mask = diff > tol
    return _res("DQ-14", "Order total ≠ sum of items", "MEDIUM", len(m), mask,
                f"Tolerance {tol}. If totals include fees/tax/discounts, set settings.amount_tolerance or skip this rule.",
                m.loc[mask, "order_id"].head(5),
                "Recompute totals from line items, or store fees/discounts as explicit columns.")


RULES: List[Callable] = [r01_missing_keys, r02_duplicate_orders, r03_duplicate_events, r04_timestamp_order,
                         r05_status_vs_history, r06_missing_rider, r07_orphans, r08_invalid_amounts,
                         r09_missing_timestamps, r10_inconsistent_categories, r11_out_of_range_ts,
                         r12_implausible_durations, r13_unknown_status, r14_amount_vs_items]


def run(mapping: dict) -> List[Result]:
    data = load_dataset(mapping)
    s = settings(mapping)
    skip = set(s.get("skip_rules", []))
    results = []
    for rule in RULES:
        rid = "DQ-" + rule.__name__[1:3]
        if rid in skip:
            results.append(_skip(rid, rule.__name__[4:].replace("_", " "), "-", "skipped via settings.skip_rules"))
            continue
        try:
            results.append(rule(data, s))
        except Exception as exc:  # a broken rule must never hide the others
            results.append(Result(rid, rule.__name__, "-", "ERROR", detail=f"{type(exc).__name__}: {exc}"))
    return results


def render_markdown(results: List[Result], mapping_path: str) -> str:
    fails = [r for r in results if r.status == "FAIL"]
    score_rules = [r for r in results if r.status in ("PASS", "FAIL")]
    weights = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    total_w = sum(weights.get(r.severity, 0) for r in score_rules) or 1
    lost = sum(weights.get(r.severity, 0) * min(1.0, r.rate_pct / 5.0) for r in fails)
    score = round(100 * (1 - lost / total_w), 1)

    out = [f"# Data-Quality Audit\n",
           f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} from `{mapping_path}`_\n",
           f"**Health score: {score}/100** — {len(fails)} failing, "
           f"{sum(r.status == 'PASS' for r in results)} passing, "
           f"{sum(r.status == 'SKIPPED' for r in results)} skipped "
           f"(score weights severity × failure rate, capped at 5% per rule).\n",
           "## Summary\n"]
    rows = pd.DataFrame([{"Rule": r.rule_id, "Check": r.name, "Severity": r.severity, "Status": r.status,
                          "Checked": f"{r.checked:,}", "Failed": f"{r.failed:,}", "Rate %": f"{r.rate_pct:.3f}"}
                         for r in results])
    out.append(md_table(rows))
    if fails:
        out.append("\n## Findings (most severe first)\n")
        for r in sorted(fails, key=lambda r: (SEVERITY_ORDER.index(r.severity) if r.severity in SEVERITY_ORDER else 9,
                                              -r.rate_pct)):
            out.append(f"### {r.rule_id} · {r.name} — {r.severity}\n")
            out.append(f"- **{r.failed:,}** of {r.checked:,} ({r.rate_pct:.3f}%)\n")
            if r.detail:
                out.append(f"- Detail: {r.detail}\n")
            if r.samples:
                out.append(f"- Samples: {', '.join('`' + x + '`' for x in r.samples)}\n")
            if r.fix:
                out.append(f"- Fix: {r.fix}\n")
            out.append("\n")
    skipped = [r for r in results if r.status in ("SKIPPED", "ERROR")]
    if skipped:
        out.append("\n## Not evaluated\n")
        for r in skipped:
            out.append(f"- {r.rule_id} {r.name}: {r.status} — {r.detail}\n")
    return "".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mapping", required=True)
    ap.add_argument("--out", default="dq_report.md")
    ap.add_argument("--json", default=None)
    ap.add_argument("--fail-on", default="CRITICAL", choices=SEVERITY_ORDER + ["NONE"])
    args = ap.parse_args(argv)
    try:
        mapping = load_mapping(args.mapping)
        results = run(mapping)
    except MappingError as exc:
        eprint(f"Mapping error: {exc}")
        return 2
    md = render_markdown(results, args.mapping)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(md)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump([asdict(r) for r in results], fh, indent=2, default=str)
    for r in results:
        print(f"{r.rule_id:6} {r.status:8} {r.severity:9} {r.failed:>9,} / {r.checked:<10,} {r.name}")
    print(f"\nReport written to {args.out}")
    if args.fail_on != "NONE":
        threshold = SEVERITY_ORDER.index(args.fail_on)
        if any(r.status == "FAIL" and r.severity in SEVERITY_ORDER and SEVERITY_ORDER.index(r.severity) <= threshold
               for r in results):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
