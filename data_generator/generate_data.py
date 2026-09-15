"""
Reproducible synthetic data generator for the Order & Delivery Analytics
System.

Generates 8 CSV files matching database/schema.sql: locations, customers,
riders, orders, order_items, deliveries, order_status_history, event_log.

Design decisions (documented here since they shape every downstream table):
  - Each customer has exactly one saved delivery address (1 location per
    customer, location_id == customer_id). Real systems support multiple
    addresses per customer; this is a deliberate simplification.
  - Order timestamps follow assumed (not measured) day-of-week and
    hour-of-day demand patterns, so "when is demand highest" has a real
    signal to find later.
  - Rider city distribution is intentionally different from order city
    distribution (see config.RIDER_CITY_WEIGHTS) to create a supply/demand
    imbalance across cities.
  - A small window of the most recent orders is left "in progress" rather
    than fully resolved, to simulate a live operational snapshot.
  - All cancellation / failure / stage-duration rates are configured
    assumptions for scenario realism, not measured business data.

Run: python generate_data.py [--number-of-customers N] [--number-of-orders N] ...
"""

import argparse
import json
import os
import time

import numpy as np
import pandas as pd

from config import (
    CITY_META,
    FIRST_NAMES,
    IN_PROGRESS_WINDOW_HOURS,
    LAST_NAMES,
    ORDER_STAGES,
    P_CANCELLED_EARLY,
    P_CANCELLED_MID,
    P_FAILED_DELIVERY,
    PAYMENT_METHODS,
    PAYMENT_WEIGHTS,
    PRODUCT_CATALOG,
    RIDER_CITY_WEIGHTS,
    STREET_NAMES,
    VEHICLE_TYPES,
    VEHICLE_WEIGHTS,
    GeneratorConfig,
)
from quality_issues import (
    inject_duplicate_rows,
    inject_inconsistent_city_names,
    inject_invalid_delivery_timestamps,
    inject_missing_values,
    inject_skipped_stage,
    inject_status_mismatch,
)


def _city_weights(cities, weight_source):
    weights = np.array([weight_source.get(c, 1.0) for c in cities], dtype=float)
    return weights / weights.sum()


def generate_locations(config: GeneratorConfig, rng: np.random.Generator) -> pd.DataFrame:
    n = config.number_of_customers
    weights = _city_weights(config.cities, {c: m["weight"] for c, m in CITY_META.items()})
    city_arr = rng.choice(np.array(config.cities, dtype=object), size=n, p=weights)

    meta = pd.DataFrame(CITY_META).T.reset_index().rename(columns={"index": "city"})
    df = pd.DataFrame({"location_id": np.arange(1, n + 1), "city": city_arr}).merge(
        meta, on="city", how="left"
    )

    numbers = rng.integers(100, 9999, size=n)
    streets = rng.choice(np.array(STREET_NAMES, dtype=object), size=n)
    df["address_line"] = [f"{num} {st}" for num, st in zip(numbers, streets)]
    df["latitude"] = (df["lat"].astype(float) + rng.normal(0, 0.03, n)).round(6)
    df["longitude"] = (df["lon"].astype(float) + rng.normal(0, 0.03, n)).round(6)
    df["postal_code"] = df["zip_prefix"] + rng.integers(10, 99, n).astype(str)

    return df[["location_id", "address_line", "city", "state", "postal_code", "latitude", "longitude"]]


def generate_customers(config: GeneratorConfig, rng: np.random.Generator) -> pd.DataFrame:
    n = config.number_of_customers
    customer_id = np.arange(1, n + 1)
    first = rng.choice(np.array(FIRST_NAMES, dtype=object), size=n)
    last = rng.choice(np.array(LAST_NAMES, dtype=object), size=n)
    email = [f"{f.lower()}.{l.lower()}{cid}@example.com" for f, l, cid in zip(first, last, customer_id)]
    phone = [f"555-{rng.integers(100, 999)}-{rng.integers(1000, 9999)}" for _ in range(n)]

    # every customer signs up before the order-generation window begins
    start_date = config.end_date - pd.Timedelta(days=config.number_of_days)
    signup_window_start = start_date - pd.Timedelta(days=610)
    signup_offset_days = rng.integers(0, 609, size=n)
    signup_date = (signup_window_start + pd.to_timedelta(signup_offset_days, unit="D")).date

    return pd.DataFrame(
        {
            "customer_id": customer_id,
            "first_name": first,
            "last_name": last,
            "email": email,
            "phone": phone,
            "signup_date": signup_date,
            "default_location_id": customer_id,  # 1:1 with locations, by design
        }
    )


def generate_riders(config: GeneratorConfig, rng: np.random.Generator) -> pd.DataFrame:
    n = config.number_of_riders
    rider_id = np.arange(1, n + 1)
    first = rng.choice(np.array(FIRST_NAMES, dtype=object), size=n)
    last = rng.choice(np.array(LAST_NAMES, dtype=object), size=n)
    phone = [f"555-{rng.integers(100, 999)}-{rng.integers(1000, 9999)}" for _ in range(n)]
    vehicle = rng.choice(np.array(VEHICLE_TYPES, dtype=object), size=n, p=VEHICLE_WEIGHTS)
    weights = _city_weights(config.cities, RIDER_CITY_WEIGHTS)
    city = rng.choice(np.array(config.cities, dtype=object), size=n, p=weights)
    rating = np.clip(rng.normal(4.5, 0.4, size=n), 3.0, 5.0).round(1)
    is_active = rng.random(n) < 0.95
    joined_offset_days = rng.integers(0, 548, size=n)
    joined_date = (config.end_date - pd.to_timedelta(joined_offset_days, unit="D")).date

    return pd.DataFrame(
        {
            "rider_id": rider_id,
            "first_name": first,
            "last_name": last,
            "phone": phone,
            "vehicle_type": vehicle,
            "city": city,
            "rating": rating,
            "is_active": is_active,
            "joined_date": joined_date,
        }
    )


def generate_orders_and_items(config: GeneratorConfig, rng: np.random.Generator, locations_df: pd.DataFrame):
    n = config.number_of_orders
    order_id = np.arange(1, n + 1)

    # purchase propensity: a minority of customers order disproportionately
    # often (assumed lognormal shape), giving realistic repeat-customer skew
    propensity = rng.lognormal(mean=0.0, sigma=0.8, size=config.number_of_customers)
    propensity = propensity / propensity.sum()
    customer_idx = rng.choice(config.number_of_customers, size=n, p=propensity)
    order_customer_id = customer_idx + 1  # customer_id is 1-indexed
    order_location_id = order_customer_id  # 1:1 customer-location design

    city_by_location = locations_df.sort_values("location_id")["city"].to_numpy()
    order_city = city_by_location[order_location_id - 1]

    # demand pattern: day-of-week and hour-of-day weighting
    start_date = config.end_date - pd.Timedelta(days=config.number_of_days)
    calendar_dates = pd.date_range(start_date.normalize(), periods=config.number_of_days, freq="D")
    weekday_weight = {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.05, 4: 1.4, 5: 1.4, 6: 1.2}  # Mon..Sun
    day_weights = np.array([weekday_weight[d.weekday()] for d in calendar_dates])
    day_weights = day_weights / day_weights.sum()
    day_offset = rng.choice(config.number_of_days, size=n, p=day_weights)

    hour_weight = np.array(
        [0.2, 0.1, 0.1, 0.1, 0.1, 0.2, 0.5, 0.8, 1.0, 1.0, 1.1, 1.4,
         2.2, 2.0, 1.1, 0.9, 1.0, 1.3, 2.4, 2.6, 2.0, 1.3, 0.8, 0.4]
    )
    hour_weight = hour_weight / hour_weight.sum()
    hour = rng.choice(24, size=n, p=hour_weight)
    minute = rng.integers(0, 60, size=n)
    second = rng.integers(0, 60, size=n)

    order_placed_at = (
        pd.Timestamp(start_date.normalize())
        + pd.to_timedelta(day_offset, unit="D")
        + pd.to_timedelta(hour, unit="h")
        + pd.to_timedelta(minute, unit="m")
        + pd.to_timedelta(second, unit="s")
    )

    payment_method = rng.choice(np.array(PAYMENT_METHODS, dtype=object), size=n, p=PAYMENT_WEIGHTS)

    orders_df = pd.DataFrame(
        {
            "order_id": order_id,
            "customer_id": order_customer_id,
            "delivery_location_id": order_location_id,
            "order_placed_at": order_placed_at,
            "payment_method": payment_method,
        }
    )

    # order items — fully vectorized
    n_items = rng.integers(1, 5, size=n)
    total_items = int(n_items.sum())
    item_order_id = np.repeat(order_id, n_items)
    product_idx = rng.integers(0, len(PRODUCT_CATALOG), size=total_items)
    product_names = np.array([p[0] for p in PRODUCT_CATALOG], dtype=object)
    categories = np.array([p[1] for p in PRODUCT_CATALOG], dtype=object)
    unit_prices = np.array([p[2] for p in PRODUCT_CATALOG], dtype=float)
    quantity = rng.integers(1, 4, size=total_items)
    line_total = (unit_prices[product_idx] * quantity).round(2)

    order_items_df = pd.DataFrame(
        {
            "order_item_id": np.arange(1, total_items + 1),
            "order_id": item_order_id,
            "product_name": product_names[product_idx],
            "category": categories[product_idx],
            "unit_price": unit_prices[product_idx],
            "quantity": quantity,
            "line_total": line_total,
        }
    )

    order_total = order_items_df.groupby("order_id")["line_total"].sum()
    orders_df["total_amount"] = orders_df["order_id"].map(order_total).round(2)

    return orders_df, order_items_df, order_city


def generate_lifecycle(config: GeneratorConfig, rng: np.random.Generator, orders_df: pd.DataFrame,
                        riders_df: pd.DataFrame, order_city: np.ndarray):
    n = len(orders_df)
    order_id = orders_df["order_id"].to_numpy()
    order_placed_at = orders_df["order_placed_at"].to_numpy()

    is_in_progress = order_placed_at >= np.datetime64(config.end_date - pd.Timedelta(hours=IN_PROGRESS_WINDOW_HOURS))
    outcome = np.full(n, "success", dtype=object)
    outcome[is_in_progress] = "in_progress"
    roll = rng.random(n)
    not_in_progress = ~is_in_progress
    outcome[not_in_progress & (roll < P_CANCELLED_EARLY)] = "cancelled_early"
    outcome[not_in_progress & (roll >= P_CANCELLED_EARLY) & (roll < P_CANCELLED_EARLY + P_CANCELLED_MID)] = "cancelled_mid"
    outcome[
        not_in_progress
        & (roll >= P_CANCELLED_EARLY + P_CANCELLED_MID)
        & (roll < P_CANCELLED_EARLY + P_CANCELLED_MID + P_FAILED_DELIVERY)
    ] = "failed_delivery"
    in_progress_reached = rng.integers(1, 5, size=n)  # 1=confirmed .. 4=out_for_delivery

    gap_placed_confirmed = rng.uniform(1, 5, size=n)
    gap_confirmed_preparing = rng.uniform(1, 4, size=n)
    gap_preparing_ready = rng.uniform(8, 20, size=n)
    gap_ready_pickup = rng.uniform(1, 6, size=n)
    distance_km = rng.uniform(0.5, 9.0, size=n)
    pace_min_per_km = rng.uniform(3, 6, size=n)
    transit_overhead = rng.uniform(2, 8, size=n)
    gap_cancel_early = rng.uniform(1, 10, size=n)
    gap_cancel_mid = rng.uniform(1, 15, size=n)

    riders_by_city = {city: grp["rider_id"].to_numpy() for city, grp in riders_df.groupby("city")}
    all_rider_ids = riders_df["rider_id"].to_numpy()

    def pick_rider(city):
        pool = riders_by_city.get(city)
        if pool is None or len(pool) == 0:
            pool = all_rider_ids
        return int(rng.choice(pool))

    stages_log = []
    deliveries_log = []
    final_status = np.empty(n, dtype=object)
    final_rider_id = np.full(n, -1, dtype=np.int64)

    for i in range(n):
        oid = int(order_id[i])
        outcome_i = outcome[i]
        t_placed = pd.Timestamp(order_placed_at[i])
        stages_log.append((oid, "placed", t_placed))

        t_confirmed = t_placed + pd.Timedelta(minutes=gap_placed_confirmed[i])
        if outcome_i == "cancelled_early":
            t_cancel = t_confirmed + pd.Timedelta(minutes=gap_cancel_early[i])
            stages_log.append((oid, "confirmed", t_confirmed))
            stages_log.append((oid, "cancelled", t_cancel))
            final_status[i] = "cancelled"
            continue

        stages_log.append((oid, "confirmed", t_confirmed))
        if outcome_i == "in_progress" and in_progress_reached[i] == 1:
            final_status[i] = "confirmed"
            continue

        t_preparing = t_confirmed + pd.Timedelta(minutes=gap_confirmed_preparing[i])
        if outcome_i == "cancelled_mid":
            t_cancel = t_preparing + pd.Timedelta(minutes=gap_cancel_mid[i])
            stages_log.append((oid, "preparing", t_preparing))
            stages_log.append((oid, "cancelled", t_cancel))
            final_status[i] = "cancelled"
            continue

        stages_log.append((oid, "preparing", t_preparing))
        if outcome_i == "in_progress" and in_progress_reached[i] == 2:
            final_status[i] = "preparing"
            continue

        t_ready = t_preparing + pd.Timedelta(minutes=gap_preparing_ready[i])
        stages_log.append((oid, "ready_for_pickup", t_ready))
        if outcome_i == "in_progress" and in_progress_reached[i] == 3:
            final_status[i] = "ready_for_pickup"
            continue

        rider_id_i = pick_rider(order_city[i])
        final_rider_id[i] = rider_id_i
        t_pickup = t_ready + pd.Timedelta(minutes=gap_ready_pickup[i])
        stages_log.append((oid, "out_for_delivery", t_pickup))
        delivery_common = dict(order_id=oid, rider_id=rider_id_i, assigned_at=t_ready, picked_up_at=t_pickup)

        if outcome_i == "in_progress" and in_progress_reached[i] == 4:
            final_status[i] = "out_for_delivery"
            deliveries_log.append(
                {**delivery_common, "delivered_at": pd.NaT, "delivery_status": "picked_up",
                 "distance_km": round(float(distance_km[i]), 2)}
            )
            continue

        transit_minutes = distance_km[i] * pace_min_per_km[i] + transit_overhead[i]
        t_delivered = t_pickup + pd.Timedelta(minutes=transit_minutes)

        if outcome_i == "failed_delivery":
            stages_log.append((oid, "cancelled", t_delivered))
            final_status[i] = "cancelled"
            deliveries_log.append(
                {**delivery_common, "delivered_at": pd.NaT, "delivery_status": "failed",
                 "distance_km": round(float(distance_km[i]), 2)}
            )
            continue

        stages_log.append((oid, "delivered", t_delivered))
        final_status[i] = "delivered"
        deliveries_log.append(
            {**delivery_common, "delivered_at": t_delivered, "delivery_status": "delivered",
             "distance_km": round(float(distance_km[i]), 2)}
        )

    orders_df = orders_df.copy()
    orders_df["status"] = final_status
    rider_id_list = [None if v == -1 else int(v) for v in final_rider_id]
    orders_df["rider_id"] = pd.array(rider_id_list, dtype="Int64")

    history_df = pd.DataFrame(stages_log, columns=["order_id", "status", "changed_at"])
    history_df.insert(0, "history_id", np.arange(1, len(history_df) + 1))

    deliveries_df = pd.DataFrame(deliveries_log)
    deliveries_df.insert(0, "delivery_id", np.arange(1, len(deliveries_df) + 1))
    deliveries_df = deliveries_df[
        ["delivery_id", "order_id", "rider_id", "assigned_at", "picked_up_at", "delivered_at",
         "delivery_status", "distance_km"]
    ]

    return orders_df, history_df, deliveries_df


def derive_event_log(history_df: pd.DataFrame, orders_df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    channel_by_order = pd.Series(
        rng.choice(["mobile_app", "web"], size=len(orders_df)), index=orders_df["order_id"].to_numpy()
    )
    df = history_df.copy()
    df["event_type"] = "order_" + df["status"]
    channel = df["order_id"].map(channel_by_order)
    df["payload"] = [
        json.dumps({"source": ch, "order_id": int(oid)}) for ch, oid in zip(channel, df["order_id"])
    ]
    df = df.rename(columns={"changed_at": "event_timestamp"})
    df.insert(0, "event_id", np.arange(1, len(df) + 1))
    return df[["event_id", "order_id", "event_type", "payload", "event_timestamp"]]


def apply_quality_issues(config: GeneratorConfig, rng: np.random.Generator, tables: dict) -> dict:
    if not config.inject_data_quality_issues:
        return {"applied": False}

    rate = config.quality_issue_rate
    summary = {"applied": True, "rate": rate}

    tables["order_items"], summary["duplicate_order_items"] = inject_duplicate_rows(
        tables["order_items"], rng, rate, "order_item_id"
    )
    tables["event_log"], summary["duplicate_events"] = inject_duplicate_rows(
        tables["event_log"], rng, rate, "event_id"
    )
    tables["customers"], missing_phone_count = inject_missing_values(tables["customers"], rng, rate, ["phone"])
    tables["riders"], missing_rating_count = inject_missing_values(tables["riders"], rng, rate, ["rating"])
    tables["locations"], missing_zip_count = inject_missing_values(tables["locations"], rng, rate, ["postal_code"])
    summary["missing_values"] = {
        "customers.phone": missing_phone_count,
        "riders.rating": missing_rating_count,
        "locations.postal_code": missing_zip_count,
    }
    tables["deliveries"], summary["invalid_delivery_timestamps"] = inject_invalid_delivery_timestamps(
        tables["deliveries"], rng, rate
    )
    tables["orders"], summary["status_mismatches"] = inject_status_mismatch(tables["orders"], rng, rate)
    tables["order_status_history"], summary["skipped_stages"] = inject_skipped_stage(
        tables["order_status_history"], rng, rate
    )
    tables["locations"], summary["inconsistent_city_names"] = inject_inconsistent_city_names(
        tables["locations"], rng, rate
    )
    return summary


def _round_timestamps_to_seconds(tables: dict) -> None:
    """Real order-tracking timestamps don't carry nanosecond precision — this
    is an artifact of building them from float-minute offsets. Round every
    datetime64 column to the nearest second in place."""
    for df in tables.values():
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.round("s")


def write_outputs(tables: dict, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(os.path.join(output_dir, f"{name}.csv"), index=False)


def run(config: GeneratorConfig) -> dict:
    t0 = time.time()
    config.end_date = pd.Timestamp(config.end_date)  # normalize so date arithmetic below is unambiguous
    rng = np.random.default_rng(config.random_seed)

    locations_df = generate_locations(config, rng)
    customers_df = generate_customers(config, rng)
    riders_df = generate_riders(config, rng)
    orders_df, order_items_df, order_city = generate_orders_and_items(config, rng, locations_df)
    orders_df, history_df, deliveries_df = generate_lifecycle(config, rng, orders_df, riders_df, order_city)
    event_log_df = derive_event_log(history_df, orders_df, rng)

    # column order matching database/schema.sql
    orders_df = orders_df[
        ["order_id", "customer_id", "delivery_location_id", "rider_id", "status",
         "order_placed_at", "total_amount", "payment_method"]
    ]

    tables = {
        "locations": locations_df,
        "customers": customers_df,
        "riders": riders_df,
        "orders": orders_df,
        "order_items": order_items_df,
        "deliveries": deliveries_df,
        "order_status_history": history_df,
        "event_log": event_log_df,
    }

    quality_summary = apply_quality_issues(config, rng, tables)
    _round_timestamps_to_seconds(tables)
    write_outputs(tables, config.output_dir)

    elapsed = time.time() - t0
    row_counts = {name: len(df) for name, df in tables.items()}
    return {"row_counts": row_counts, "quality_summary": quality_summary, "elapsed_seconds": round(elapsed, 1)}


def parse_args() -> GeneratorConfig:
    parser = argparse.ArgumentParser(description="Generate synthetic order & delivery data.")
    parser.add_argument("--number-of-customers", type=int, default=GeneratorConfig.number_of_customers)
    parser.add_argument("--number-of-orders", type=int, default=GeneratorConfig.number_of_orders)
    parser.add_argument("--number-of-riders", type=int, default=GeneratorConfig.number_of_riders)
    parser.add_argument("--number-of-days", type=int, default=GeneratorConfig.number_of_days)
    parser.add_argument("--random-seed", type=int, default=GeneratorConfig.random_seed)
    parser.add_argument("--output-dir", type=str, default=GeneratorConfig.output_dir)
    parser.add_argument("--cities", type=str, default=None, help="comma-separated subset of cities")
    parser.add_argument("--no-quality-issues", action="store_true", help="disable data-quality issue injection")
    parser.add_argument("--quality-issue-rate", type=float, default=GeneratorConfig.quality_issue_rate)
    args = parser.parse_args()

    config = GeneratorConfig(
        number_of_customers=args.number_of_customers,
        number_of_orders=args.number_of_orders,
        number_of_riders=args.number_of_riders,
        number_of_days=args.number_of_days,
        random_seed=args.random_seed,
        output_dir=args.output_dir,
        inject_data_quality_issues=not args.no_quality_issues,
        quality_issue_rate=args.quality_issue_rate,
    )
    if args.cities:
        config.cities = [c.strip() for c in args.cities.split(",")]
    return config


def main():
    config = parse_args()
    print(f"Generating synthetic data with config: {config}")
    result = run(config)
    print("Row counts:")
    for name, count in result["row_counts"].items():
        print(f"  {name}: {count:,}")
    print(f"Quality issue summary: {result['quality_summary']}")
    print(f"Elapsed: {result['elapsed_seconds']}s")
    print(f"Output written to: {config.output_dir}")


if __name__ == "__main__":
    main()
