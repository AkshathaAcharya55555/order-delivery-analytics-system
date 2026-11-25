#!/usr/bin/env python3
"""
Profile an unfamiliar order/delivery dataset and draft a mapping file.

Usage:
    python profile_source.py --csv-dir ./data            [--out mapping.json]
    python profile_source.py --sql [--schema public] [--url-env DATABASE_URL] [--out mapping.json]

For every table/file it prints row counts, columns, null rates and sample
values, then guesses which table plays each canonical role (orders,
deliveries, riders, ...) and which column fills each canonical field, using
name synonyms plus value-type sniffing. Distinct status values are bucketed
into delivered / cancelled / failed / in_progress.

The draft is a STARTING POINT: every guess is listed with a confidence so a
human (or the agent) can confirm it. Nothing is written to the data source.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from _common import CANONICAL, guess_outcome, eprint  # noqa: E402

TABLE_SYNONYMS = {
    "orders": ["orders", "order", "sales_orders", "fact_orders", "order_header", "purchases"],
    "deliveries": ["deliveries", "delivery", "shipments", "shipment", "trips", "dispatches", "jobs", "fulfillments"],
    "riders": ["riders", "rider", "drivers", "driver", "couriers", "courier", "agents", "partners", "delivery_partners"],
    "customers": ["customers", "customer", "users", "user", "clients", "buyers", "accounts"],
    "order_items": ["order_items", "order_lines", "line_items", "items", "order_details", "orderlines"],
    "status_history": ["order_status_history", "status_history", "order_events_history", "order_audit",
                       "order_status_log", "status_log", "order_timeline"],
    "events": ["event_log", "events", "raw_events", "order_events", "webhook_events", "kafka_events"],
}

COL_SYNONYMS = {
    "order_id": ["order_id", "orderid", "order_no", "order_number", "order_ref", "id"],
    "customer_id": ["customer_id", "customerid", "user_id", "client_id", "buyer_id", "account_id", "id"],
    "rider_id": ["rider_id", "driver_id", "courier_id", "agent_id", "partner_id", "assigned_rider_id", "id"],
    "event_id": ["event_id", "message_id", "id", "uuid"],
    "placed_at": ["order_placed_at", "placed_at", "ordered_at", "order_date", "order_time", "created_at",
                  "order_created_at", "order_datetime", "timestamp"],
    "status": ["status", "order_status", "state", "delivery_status", "current_status"],
    "total_amount": ["total_amount", "amount", "order_total", "total", "grand_total", "order_value",
                     "gmv", "price", "total_price"],
    "city": ["city", "delivery_city", "town", "market", "region", "zone", "area", "hub"],
    "assigned_at": ["assigned_at", "accepted_at", "dispatched_at", "rider_assigned_at", "allocated_at"],
    "picked_up_at": ["picked_up_at", "pickup_at", "pickup_time", "collected_at", "pickup_ts"],
    "delivered_at": ["delivered_at", "dropoff_at", "drop_off_at", "completed_at", "delivery_time",
                     "delivered_time", "dropped_at"],
    "distance_km": ["distance_km", "distance", "km", "trip_distance"],
    "is_active": ["is_active", "active", "enabled"],
    "signup_date": ["signup_date", "created_at", "registered_at", "joined_at", "signup_at"],
    "unit_price": ["unit_price", "price", "item_price"],
    "quantity": ["quantity", "qty", "count", "units"],
    "changed_at": ["changed_at", "updated_at", "status_at", "event_time", "timestamp", "created_at"],
    "seq": ["history_id", "seq", "sequence", "version", "id"],
    "event_type": ["event_type", "type", "event_name", "topic", "name"],
    "event_timestamp": ["event_timestamp", "event_time", "timestamp", "occurred_at", "created_at"],
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", s.lower()).strip("_")


def sniff_kind(series: pd.Series) -> str:
    s = series.dropna()
    if s.empty:
        return "empty"
    if pd.api.types.is_bool_dtype(s):
        return "bool"
    if pd.api.types.is_numeric_dtype(s):
        return "num"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "ts"
    sample = s.astype(str).head(200)
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    if parsed.notna().mean() > 0.9 and sample.str.contains(r"\d{4}|\d{1,2}[/-]\d{1,2}").mean() > 0.9:
        return "ts"
    return "str"


def load_sources(args) -> Dict[str, pd.DataFrame]:
    """Returns {table_name: sample_dataframe} (≤ 50k rows each) plus full row counts in attrs."""
    out = {}
    if args.csv_dir:
        for fn in sorted(os.listdir(args.csv_dir)):
            if fn.lower().endswith(".csv"):
                path = os.path.join(args.csv_dir, fn)
                df = pd.read_csv(path, nrows=50_000, low_memory=False)
                with open(path, "rb") as fh:
                    df.attrs["rows"] = max(sum(1 for _ in fh) - 1, 0)
                out[fn] = df
        return out
    from sqlalchemy import create_engine, inspect, select, func, table as sa_table
    url = os.environ.get(args.url_env)
    if not url:
        raise SystemExit(f"Set {args.url_env} to a SQLAlchemy URL, e.g. postgresql://$DB_USER:$DB_PASSWORD@host:5432/db")
    eng = create_engine(url)
    insp = inspect(eng)
    schema = args.schema or None
    names = insp.get_table_names(schema=schema) + insp.get_view_names(schema=schema)
    with eng.connect() as conn:
        for t in sorted(set(names)):
            tbl = sa_table(t, schema=schema)
            df = pd.read_sql(select("*").select_from(tbl).limit(50_000), conn)
            df.attrs["rows"] = int(conn.execute(select(func.count()).select_from(tbl)).scalar())
            key = t if not schema or schema == "public" else f"{schema}.{t}"
            out[key] = df
    return out


def table_score(entity: str, name: str, df: pd.DataFrame) -> float:
    stem = name[:-4] if name.lower().endswith(".csv") else name
    base = norm(stem.split(".")[-1])  # drop a "schema." prefix for postgres tables
    score = 0.0
    syns = TABLE_SYNONYMS[entity]
    if base in syns:
        score += 3 - 0.1 * syns.index(base)
    elif any(sy in base for sy in syns):
        score += 1.5
    cols = {norm(c) for c in df.columns}
    for canon in CANONICAL[entity]:
        if any(sy in cols for sy in COL_SYNONYMS.get(canon, [canon]) if sy != "id"):
            score += 0.5
    return score


def best_column(canon: str, kind: str, df: pd.DataFrame, entity: str, used: set) -> Tuple[Optional[str], str]:
    cols = {norm(c): c for c in df.columns}
    syns = COL_SYNONYMS.get(canon, [canon])
    for i, sy in enumerate(syns):
        if sy == "id":
            # bare 'id' only counts for the table's own primary key
            own = {"orders": "order_id", "riders": "rider_id", "customers": "customer_id", "events": "event_id",
                   "status_history": "seq"}.get(entity)
            if own != canon:
                continue
        if sy in cols and cols[sy] not in used:
            col = cols[sy]
            k = sniff_kind(df[col])
            if kind == "ts" and k not in ("ts", "empty"):
                continue
            if kind == "num" and k not in ("num", "empty"):
                continue
            return col, "high" if i == 0 else "medium"
    # fuzzy: synonym contained in column name
    for sy in syns:
        if sy == "id" or len(sy) < 4:
            continue
        for n, col in cols.items():
            if sy in n and col not in used:
                k = sniff_kind(df[col])
                if (kind == "ts" and k != "ts") or (kind == "num" and k != "num"):
                    continue
                return col, "low"
    return None, "none"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--csv-dir")
    g.add_argument("--sql", "--postgres", dest="sql", action="store_true",
                   help="read from the SQLAlchemy URL in --url-env (Postgres, MySQL, SQLite, Snowflake, ...)")
    ap.add_argument("--schema", default=None, help="database schema (default: the connection's default)")
    ap.add_argument("--url-env", default="DATABASE_URL")
    ap.add_argument("--out", default="mapping.json")
    args = ap.parse_args(argv)

    sources = load_sources(args)
    if not sources:
        eprint("No tables / CSV files found.")
        return 2

    print("# Source profile\n")
    for name, df in sources.items():
        print(f"## {name} — {df.attrs.get('rows', len(df)):,} rows, {df.shape[1]} columns")
        for c in df.columns:
            nulls = 100 * df[c].isna().mean()
            samples = ", ".join(str(v)[:24] for v in df[c].dropna().unique()[:3])
            print(f"   {c:<28} {sniff_kind(df[c]):<5} null {nulls:5.1f}%  e.g. {samples}")
        print()

    # assign tables to entities greedily by score
    pairs = sorted(((table_score(e, n, df), e, n) for e in TABLE_SYNONYMS for n, df in sources.items()), reverse=True)
    role: Dict[str, str] = {}
    taken = set()
    for score, e, n in pairs:
        if score < 1.5 or e in role or n in taken:
            continue
        role[e] = n
        taken.add(n)

    mapping = {"source": {"type": "csv", "path": os.path.abspath(args.csv_dir)} if args.csv_dir
               else {"type": "sql", "url_env": args.url_env},
               "tables": {}, "status_map": {}, "settings": {"sla_minutes": 45, "currency": "$"}}
    review: List[str] = []
    for entity, name in role.items():
        df = sources[name]
        used, cols = set(), {}
        for canon, kind in CANONICAL[entity].items():
            col, conf = best_column(canon, kind, df, entity, used)
            if col:
                cols[canon] = col
                used.add(col)
                if conf != "high":
                    review.append(f"{entity}.{canon} ← {name}:{col} ({conf} confidence)")
        mapping["tables"][entity] = {"from": name, "columns": cols}

    orders_spec = mapping["tables"].get("orders")
    if not orders_spec:
        review.insert(0, "NO orders table detected — set tables.orders by hand.")
    else:
        for req in ("order_id", "placed_at", "status"):
            if req not in orders_spec["columns"]:
                review.insert(0, f"REQUIRED orders.{req} not found — fill it in by hand.")
        # city via a location/address lookup table?
        if "city" not in orders_spec["columns"]:
            odf = sources[orders_spec["from"]]
            for n, df in sources.items():
                cityc = next((c for c in df.columns if norm(c) in ("city", "town", "market")), None)
                if not cityc or n == orders_spec["from"]:
                    continue
                pk = next((c for c in df.columns if norm(c).endswith("_id") and norm(c).split("_id")[0] in norm(n)), None)
                fk = next((c for c in odf.columns if pk and norm(c).endswith(norm(pk))), None)
                if pk and fk:
                    orders_spec["join"] = [{"from": n, "left_on": fk, "right_on": pk, "columns": {"city": cityc}}]
                    orders_spec["columns"]["city"] = "city"
                    review.append(f"orders.city joined from {n} via {fk} → {pk} (verify)")
                    break
        st_col = orders_spec["columns"].get("status")
        if st_col:
            values = sources[orders_spec["from"]][st_col].dropna().astype(str).str.strip().unique().tolist()
            buckets: Dict[str, List[str]] = {"delivered": [], "cancelled": [], "failed": [], "in_progress": []}
            for v in sorted(values):
                buckets[guess_outcome(v)].append(v)
            mapping["status_map"] = buckets
            review.append("status_map buckets were guessed from keywords — confirm each value: "
                          + json.dumps(buckets))

    unmapped = [e for e in CANONICAL if e not in role]
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(mapping, fh, indent=2)

    print("# Draft mapping\n")
    for e, n in role.items():
        print(f"  {e:<15} ← {n}")
    if unmapped:
        print(f"  (not found: {', '.join(unmapped)} — related KPIs/rules will be skipped)")
    print("\n# Needs review")
    for r in review or ["nothing flagged"]:
        print("  -", r)
    print(f"\nWrote {args.out}. Review it, then run dq_audit.py and kpi_report.py with --mapping {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
