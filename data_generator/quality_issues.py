"""
Controlled data-quality issue injection.

Each function corrupts a small, configurable fraction of rows in one
DataFrame to simulate a specific, realistic operational problem. Every
function returns (modified_dataframe, affected_row_count) — the count is
computed from what was actually changed, not invented, so the generator's
own run summary and the separate validation script can both be checked
against real numbers.

These issues are injected into the generated CSVs on purpose so that a
later data-quality / cleaning phase has real problems to detect and fix.
"""

from typing import List, Tuple

import numpy as np
import pandas as pd

from config import CITY_META, ORDER_STAGES


def inject_duplicate_rows(
    df: pd.DataFrame, rng: np.random.Generator, rate: float, id_col: str
) -> Tuple[pd.DataFrame, int]:
    """Re-insert a sample of rows as if the same event/item arrived twice.
    The surrogate id column gets a fresh value (as a real auto-increment
    key would), but every other column is an exact content duplicate."""
    n = len(df)
    k = int(round(n * rate))
    if k == 0:
        return df, 0

    dup_idx = rng.choice(df.index.to_numpy(), size=k, replace=False)
    duplicates = df.loc[dup_idx].copy()
    next_id = int(df[id_col].max()) + 1
    duplicates[id_col] = range(next_id, next_id + k)

    out = pd.concat([df, duplicates], ignore_index=True)
    return out, k


def inject_missing_values(
    df: pd.DataFrame, rng: np.random.Generator, rate: float, columns: List[str]
) -> Tuple[pd.DataFrame, int]:
    """Null out a sample of rows in each of the given columns independently."""
    out = df.copy()
    total_affected = 0
    for col in columns:
        n = len(out)
        k = int(round(n * rate))
        if k == 0:
            continue
        idx = rng.choice(out.index.to_numpy(), size=k, replace=False)
        out.loc[idx, col] = np.nan
        total_affected += k
    return out, total_affected


def inject_invalid_delivery_timestamps(
    deliveries_df: pd.DataFrame, rng: np.random.Generator, rate: float
) -> Tuple[pd.DataFrame, int]:
    """For a sample of completed deliveries, set delivered_at earlier than
    picked_up_at — simulating a clock-sync / late-event-arrival bug."""
    out = deliveries_df.copy()
    delivered_mask = out["delivery_status"] == "delivered"
    candidates = out.index[delivered_mask].to_numpy()
    k = int(round(len(candidates) * rate))
    if k == 0:
        return out, 0

    idx = rng.choice(candidates, size=k, replace=False)
    offset_minutes = rng.uniform(1, 30, size=k)
    out.loc[idx, "delivered_at"] = out.loc[idx, "picked_up_at"] - pd.to_timedelta(
        offset_minutes, unit="m"
    )
    return out, k


def inject_status_mismatch(
    orders_df: pd.DataFrame, rng: np.random.Generator, rate: float
) -> Tuple[pd.DataFrame, int]:
    """For a sample of orders, change orders.status to a different valid
    stage than what it actually was — simulating replication lag between
    the order service's own status field and its history log."""
    out = orders_df.copy()
    n = len(out)
    k = int(round(n * rate))
    if k == 0:
        return out, 0

    all_statuses = np.array(ORDER_STAGES + ["cancelled"])
    idx = rng.choice(out.index.to_numpy(), size=k, replace=False)
    current = out.loc[idx, "status"].to_numpy()
    new_status = np.empty(k, dtype=object)
    for i in range(k):
        choices = all_statuses[all_statuses != current[i]]
        new_status[i] = rng.choice(choices)
    out.loc[idx, "status"] = new_status
    return out, k


def inject_skipped_stage(
    history_df: pd.DataFrame, rng: np.random.Generator, rate: float
) -> Tuple[pd.DataFrame, int]:
    """For a sample of orders with a long enough history, drop one middle
    stage row — simulating a lost/undelivered status-change event."""
    stage_counts = history_df.groupby("order_id").size()
    eligible_orders = stage_counts[stage_counts >= 4].index.to_numpy()
    k = int(round(len(eligible_orders) * rate))
    if k == 0:
        return history_df, 0

    chosen_orders = rng.choice(eligible_orders, size=k, replace=False)
    rows_to_drop = []
    for order_id in chosen_orders:
        order_rows = history_df.index[history_df["order_id"] == order_id].to_numpy()
        # keep the first (placed) and last (final) row, drop one row in between
        middle_rows = order_rows[1:-1]
        rows_to_drop.append(rng.choice(middle_rows))

    out = history_df.drop(index=rows_to_drop).reset_index(drop=True)
    return out, len(rows_to_drop)


def inject_inconsistent_city_names(
    locations_df: pd.DataFrame, rng: np.random.Generator, rate: float
) -> Tuple[pd.DataFrame, int]:
    """For a sample of locations, replace a clean city name with a messy
    real-world variant (case, whitespace, abbreviation, state suffix)."""
    out = locations_df.copy()
    n = len(out)
    k = int(round(n * rate))
    if k == 0:
        return out, 0

    idx = rng.choice(out.index.to_numpy(), size=k, replace=False)
    transforms = [
        lambda c: c.upper(),
        lambda c: c.lower(),
        lambda c: f" {c} ",
        lambda c: f"{c[:3].upper()}",
        lambda c: f"{c}, {CITY_META.get(c, {}).get('state', '')}".strip(", "),
    ]
    choice_idx = rng.integers(0, len(transforms), size=k)
    for pos, row_idx in enumerate(idx):
        city_val = out.loc[row_idx, "city"]
        out.loc[row_idx, "city"] = transforms[choice_idx[pos]](city_val)
    return out, k
