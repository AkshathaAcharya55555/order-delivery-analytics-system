"""
Shared loader for the order-delivery-analytics skill.

Reads a mapping file (see references/mapping-spec.md) and returns a dict of
pandas DataFrames using CANONICAL column names, regardless of how the
user's source data is actually named or stored (CSV directory or Postgres).

Only pandas + numpy are required. Postgres access additionally needs
SQLAlchemy and a driver (psycopg2 / psycopg); the connection string is read
from an environment variable named in the mapping (never hardcoded).
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Dict, List, Optional

import pandas as pd

# Windows consoles default to cp1252; the reports print arrows / block bars.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# Canonical model: entity -> {canonical_column: kind}
# kind: id | ts | num | str | bool
CANONICAL: Dict[str, Dict[str, str]] = {
    "orders": {
        "order_id": "id", "customer_id": "id", "rider_id": "id",
        "placed_at": "ts", "status": "str", "total_amount": "num", "city": "str",
    },
    "deliveries": {
        "order_id": "id", "rider_id": "id", "assigned_at": "ts",
        "picked_up_at": "ts", "delivered_at": "ts", "status": "str",
        "distance_km": "num",
    },
    "riders": {"rider_id": "id", "city": "str", "is_active": "bool"},
    "customers": {"customer_id": "id", "signup_date": "ts"},
    "order_items": {"order_id": "id", "unit_price": "num", "quantity": "num"},
    "status_history": {"order_id": "id", "status": "str", "changed_at": "ts", "seq": "num"},
    "events": {"event_id": "id", "order_id": "id", "event_type": "str", "event_timestamp": "ts"},
}

REQUIRED = {"orders": ["order_id", "placed_at", "status"]}

OUTCOMES = ("delivered", "cancelled", "failed", "in_progress")


class MappingError(Exception):
    pass


def eprint(*args):
    print(*args, file=sys.stderr)


def load_mapping(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        mapping = json.load(fh)
    mapping.setdefault("settings", {})
    mapping["_base_dir"] = os.path.dirname(os.path.abspath(path))
    if "orders" not in mapping.get("tables", {}):
        raise MappingError("mapping.tables.orders is required")
    for col in REQUIRED["orders"]:
        if col not in mapping["tables"]["orders"].get("columns", {}):
            raise MappingError(f"mapping.tables.orders.columns.{col} is required")
    return mapping


# ---------------------------------------------------------------------------
# Raw readers
# ---------------------------------------------------------------------------
_ENGINE = None


def _engine(mapping: dict):
    global _ENGINE
    if _ENGINE is None:
        src = mapping.get("source", {})
        env_name = src.get("url_env", "DATABASE_URL")
        url = os.environ.get(env_name)
        if not url:
            raise MappingError(
                f"SQL source selected but environment variable {env_name} is not set. "
                f"Export it, e.g. {env_name}=postgresql://$DB_USER:$DB_PASSWORD@host:5432/db"
            )
        try:
            from sqlalchemy import create_engine
        except ImportError as exc:  # pragma: no cover
            raise MappingError("SQL sources need: pip install sqlalchemy plus a driver "
                               "(e.g. psycopg2-binary for Postgres, pymysql for MySQL)") from exc
        _ENGINE = create_engine(url)
    return _ENGINE


def _read_raw(mapping: dict, spec) -> pd.DataFrame:
    """spec is a file name / table name string, or {"query": "..."}."""
    src = mapping.get("source", {"type": "csv"})
    is_sql = src.get("type") in ("sql", "postgres")
    if isinstance(spec, dict) and "query" in spec:
        if not is_sql:
            raise MappingError("'query' sources are only valid for sql sources")
        from sqlalchemy import text
        with _engine(mapping).connect() as conn:
            return pd.read_sql(text(spec["query"]), conn)
    if src.get("type", "csv") == "csv":
        base = src.get("path", ".")
        if not os.path.isabs(base):
            base = os.path.join(mapping["_base_dir"], base)
        path = os.path.join(base, spec)
        if not os.path.exists(path):
            raise MappingError(f"CSV not found: {path}")
        return pd.read_csv(path, low_memory=False)
    if is_sql:
        from sqlalchemy import text
        with _engine(mapping).connect() as conn:
            quote = conn.dialect.identifier_preparer.quote
            ident = ".".join(quote(p) for p in str(spec).split("."))
            return pd.read_sql(text(f"SELECT * FROM {ident}"), conn)
    raise MappingError(f"Unknown source type: {src.get('type')}")


# ---------------------------------------------------------------------------
# Canonicalisation
# ---------------------------------------------------------------------------
def _coerce(series: pd.Series, kind: str) -> pd.Series:
    if kind == "ts":
        out = pd.to_datetime(series, errors="coerce", utc=True)
        return out.dt.tz_convert(None)
    if kind == "num":
        return pd.to_numeric(series, errors="coerce")
    if kind == "id":
        # keep ids comparable across tables: strings, stripped, '' -> NA
        s = series.astype("string").str.strip()
        s = s.str.replace(r"\.0$", "", regex=True)  # 12.0 -> 12 from float CSV columns
        return s.mask(s.isin(["", "nan", "None", "NaN", "<NA>"]))
    if kind == "bool":
        return series.map(lambda v: str(v).strip().lower() in {"true", "t", "1", "yes", "y"}
                          if pd.notna(v) else pd.NA)
    return series.astype("string")


def load_table(mapping: dict, entity: str) -> Optional[pd.DataFrame]:
    tspec = mapping["tables"].get(entity)
    if not tspec:
        return None
    raw = _read_raw(mapping, tspec["from"])
    for join in tspec.get("join", []):
        right = _read_raw(mapping, join["from"])
        cols = join["columns"]  # {new_name_in_left: column_in_right}
        right = right[[join["right_on"], *cols.values()]].rename(
            columns={v: k for k, v in cols.items()}
        )
        right = right.drop_duplicates(subset=[join["right_on"]])
        left_key, right_key = join["left_on"], join["right_on"]
        right = right.rename(columns={right_key: "__rk"})
        raw = raw.merge(right, how="left", left_on=left_key, right_on="__rk").drop(columns="__rk")

    colmap: Dict[str, str] = tspec.get("columns", {})
    out = pd.DataFrame(index=raw.index)
    for canon, source_col in colmap.items():
        if canon not in CANONICAL[entity]:
            continue
        if source_col not in raw.columns:
            raise MappingError(f"{entity}: source column '{source_col}' (for {canon}) not found. "
                               f"Available: {list(raw.columns)[:40]}")
        out[canon] = _coerce(raw[source_col], CANONICAL[entity][canon])
    # keep any extra raw columns available under a prefix for ad-hoc analysis
    out.attrs["raw_columns"] = list(raw.columns)
    return out.reset_index(drop=True)


def build_status_lookup(mapping: dict) -> Dict[str, str]:
    lookup = {}
    for outcome, values in mapping.get("status_map", {}).items():
        if outcome not in OUTCOMES:
            continue
        for v in values:
            lookup[str(v).strip().lower()] = outcome
    return lookup


def classify_status(series: pd.Series, lookup: Dict[str, str]) -> pd.Series:
    """Map raw status values to delivered/cancelled/failed/in_progress/unknown."""
    norm = series.astype("string").str.strip().str.lower()
    mapped = norm.map(lookup)
    if not lookup:  # heuristic fallback
        mapped = norm.map(guess_outcome)
    return mapped.fillna("unknown")


def guess_outcome(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NA:
        return "unknown"
    v = str(value).lower()
    if any(k in v for k in ("cancel", "reject", "void", "abandon")):
        return "cancelled"
    if any(k in v for k in ("fail", "return", "undeliver", "lost")):
        return "failed"
    if any(k in v for k in ("deliver", "complete", "fulfil", "done")) and "out" not in v:
        return "delivered"
    return "in_progress"


def load_dataset(mapping: dict) -> Dict[str, Optional[pd.DataFrame]]:
    data = {entity: load_table(mapping, entity) for entity in CANONICAL}
    lookup = build_status_lookup(mapping)
    orders = data["orders"]
    orders["outcome"] = classify_status(orders["status"], lookup)

    # Fill orders.city / rider_id from deliveries / riders when not mapped directly
    d = data["deliveries"]
    if "rider_id" not in orders.columns and d is not None and "rider_id" in d.columns:
        first = d.dropna(subset=["order_id"]).drop_duplicates("order_id")[["order_id", "rider_id"]]
        orders = orders.merge(first, on="order_id", how="left")
    r = data["riders"]
    if "city" not in orders.columns and r is not None and "city" in r.columns and "rider_id" in orders.columns:
        rc = r.drop_duplicates("rider_id")[["rider_id", "city"]]
        orders = orders.merge(rc, on="rider_id", how="left")
    if "city" not in orders.columns:
        orders["city"] = pd.Series(["(all)"] * len(orders), dtype="string")
    data["orders"] = orders
    return data


_STATE_SUFFIX = re.compile(r",?\s+[a-z]{2}$")


def category_key(v) -> str:
    """'  AUSTIN, TX ' / 'Austin' / 'austin' -> 'austin'. Abbreviations like 'Aus.' are left alone."""
    v = re.sub(r"\s+", " ", str(v).strip().lower())
    v = _STATE_SUFFIX.sub("", v)
    return v.replace(".", "")


def normalize_categories(series: pd.Series):
    """Collapse spelling variants onto the most frequent spelling in each group.
    Returns (normalized_series, rows_changed, {variant: canonical})."""
    vals = series.dropna()
    if vals.empty:
        return series, 0, {}
    counts = vals.value_counts()
    keys = pd.Series({v: category_key(v) for v in counts.index})
    # short abbreviations ('aus', 'chi') join the single longer key they prefix
    distinct = set(keys)
    for v, kk in keys.items():
        if len(kk) <= 4:
            longer = [o for o in distinct if o != kk and o.startswith(kk)]
            if len(longer) == 1:
                keys[v] = longer[0]
    fix = {}
    for _, members in keys.groupby(keys).groups.items():
        members = list(members)
        if len(members) > 1:
            canonical = max(members, key=lambda m: counts[m])
            fix.update({m: canonical for m in members if m != canonical})
    if not fix:
        return series, 0, {}
    changed = int(series.isin(list(fix)).sum())
    return series.replace(fix), changed, fix


def settings(mapping: dict) -> dict:
    s = {"sla_minutes": 45, "min_rider_deliveries": 20, "currency": "$", "normalize_city": True,
         "min_city_share_pct": 1.0,
         "long_delivery_factor": 3.0, "max_reasonable_delivery_hours": 6}
    s.update(mapping.get("settings", {}))
    return s


def md_table(df: pd.DataFrame, floatfmt: str = "{:,.2f}", max_rows: int = 50) -> str:
    """Dependency-free markdown table (no tabulate needed)."""
    if df is None or df.empty:
        return "_no rows_\n"
    df = df.head(max_rows)
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, row in df.iterrows():
        cells = []
        for v in row.tolist():
            if isinstance(v, float):
                cells.append("" if pd.isna(v) else floatfmt.format(v))
            elif isinstance(v, pd.Timestamp):
                cells.append(v.strftime("%Y-%m-%d"))
            else:
                cells.append("" if v is None or v is pd.NA else str(v).replace("|", "\\|"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def bar(value: float, max_value: float, width: int = 24) -> str:
    if not max_value or pd.isna(value):
        return ""
    n = int(round(width * float(value) / float(max_value)))
    return "█" * max(n, 0)
