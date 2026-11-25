#!/usr/bin/env python3
"""
Generate a realistic, fully synthetic food/parcel-delivery dataset.

Usage:
    python generate_demo_data.py --out ./demo_data [--orders 20000] [--days 60]
                                 [--seed 42] [--no-issues]

Writes 8 CSVs (locations, customers, riders, orders, order_items, deliveries,
order_status_history, event_log) plus mapping.json, so the other scripts
run against it with zero configuration:

    python dq_audit.py   --mapping ./demo_data/mapping.json
    python kpi_report.py --mapping ./demo_data/mapping.json

Built-in realism: weekday + lunch/dinner demand peaks, city-specific speed,
deliberately under-supplied cities, slower deliveries at peak, heavy-tailed
customer loyalty, cancellations/failures. Unless --no-issues is passed it
also injects known data-quality defects (dirty city spellings, clock skew,
status drift, duplicate events) at small rates and prints exactly how many,
so the audit's findings can be checked against ground truth.

All names, places and numbers are invented. No network access.
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd

CITIES = {  # name: (state, lat, lon, demand weight, rider weight, speed factor)
    "Austin":   ("TX", 30.2672, -97.7431, 0.22, 0.24, 0.95),
    "Chicago":  ("IL", 41.8781, -87.6298, 0.20, 0.22, 1.05),
    "Denver":   ("CO", 39.7392, -104.9903, 0.18, 0.19, 0.90),
    "Miami":    ("FL", 25.7617, -80.1918, 0.16, 0.10, 1.20),
    "Portland": ("OR", 45.5152, -122.6784, 0.12, 0.06, 1.10),
    "Seattle":  ("WA", 47.6062, -122.3321, 0.12, 0.17, 1.00),
}
MENU = [("Cheeseburger", "main", 8.50), ("Veggie Burger", "main", 7.75), ("Pizza Slice", "main", 4.25),
        ("Taco Plate", "main", 10.00), ("Chicken Bowl", "main", 11.50), ("Garden Salad", "main", 9.00),
        ("Fries", "side", 4.00), ("Chicken Wings", "side", 6.50), ("Onion Rings", "side", 4.50),
        ("Soda", "drink", 2.50), ("Coffee", "drink", 2.75), ("Iced Tea", "drink", 2.25),
        ("Churros", "dessert", 3.50), ("Brownie", "dessert", 3.25)]
STAGES = ["PLACED", "CONFIRMED", "PREPARING", "READY_FOR_PICKUP", "RIDER_ASSIGNED",
          "PICKED_UP", "OUT_FOR_DELIVERY", "DELIVERED"]
FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Casey", "Riley", "Morgan", "Jamie", "Avery", "Quinn",
         "Rowan", "Drew", "Kai", "Noor", "Ira", "Remy", "Sasha", "Toni", "Ari", "Bo"]
LAST = ["Rivera", "Chen", "Patel", "Okafor", "Novak", "Silva", "Kim", "Haddad", "Larsen", "Moreau",
        "Tanaka", "Diaz", "Singh", "Kowalski", "Mensah", "Ivanov", "Costa", "Brennan", "Yilmaz", "Ng"]


def generate(n_orders: int, days: int, seed: int, issues: bool, end: pd.Timestamp):
    rng = np.random.default_rng(seed)
    names = list(CITIES)
    demand_w = np.array([CITIES[c][3] for c in names]); demand_w /= demand_w.sum()
    rider_w = np.array([CITIES[c][4] for c in names]); rider_w /= rider_w.sum()
    n_customers = max(200, n_orders // 3)
    n_riders = max(30, n_orders // 60)

    # locations / customers (1 home location each)
    cust_city = rng.choice(len(names), size=n_customers, p=demand_w)
    lat = np.array([CITIES[names[i]][1] for i in cust_city]) + rng.normal(0, 0.05, n_customers)
    lon = np.array([CITIES[names[i]][2] for i in cust_city]) + rng.normal(0, 0.05, n_customers)
    locations = pd.DataFrame({
        "location_id": np.arange(1, n_customers + 1),
        "address_line": [f"{rng.integers(1, 9999)} {s} St" for s in rng.choice(["Oak", "Pine", "Main", "Cedar", "Lake", "Hill"], n_customers)],
        "city": [names[i] for i in cust_city],
        "state": [CITIES[names[i]][0] for i in cust_city],
        "latitude": lat.round(6), "longitude": lon.round(6)})
    customers = pd.DataFrame({
        "customer_id": np.arange(1, n_customers + 1),
        "first_name": rng.choice(FIRST, n_customers), "last_name": rng.choice(LAST, n_customers),
        "signup_date": (end - pd.to_timedelta(rng.integers(days, days + 400, n_customers), unit="D")).normalize(),
        "default_location_id": np.arange(1, n_customers + 1)})
    customers["email"] = [f"user{i}@example.com" for i in customers["customer_id"]]

    rider_city = rng.choice(len(names), size=n_riders, p=rider_w)
    rider_city[: 2 * len(names)] = np.repeat(np.arange(len(names)), 2)  # every city gets >= 2 riders
    riders = pd.DataFrame({
        "rider_id": np.arange(1, n_riders + 1),
        "first_name": rng.choice(FIRST, n_riders), "last_name": rng.choice(LAST, n_riders),
        "vehicle_type": rng.choice(["bike", "scooter", "car"], n_riders, p=[0.45, 0.35, 0.20]),
        "city": [names[i] for i in rider_city],
        "rating": rng.normal(4.6, 0.25, n_riders).clip(3.0, 5.0).round(1),
        "skill": rng.normal(1.0, 0.12, n_riders).clip(0.7, 1.4),   # hidden; drives rider spread
        "is_active": True})

    # orders: heavy-tailed customer loyalty
    loyalty = rng.lognormal(0, 1.1, n_customers); loyalty /= loyalty.sum()
    cust = rng.choice(n_customers, size=n_orders, p=loyalty)
    dates = pd.date_range(end.normalize() - pd.Timedelta(days=days - 1), periods=days, freq="D")
    dw = np.array([[1.0, 1.0, 1.0, 1.05, 1.4, 1.45, 1.2][d.weekday()] for d in dates])
    growth = np.linspace(0.85, 1.15, days)  # gentle growth so trend sections have something to say
    dw = dw * growth; dw /= dw.sum()
    hw = np.array([0.2, 0.1, 0.1, 0.1, 0.1, 0.2, 0.5, 0.8, 1.0, 1.0, 1.1, 1.5,
                   2.3, 2.0, 1.1, 0.9, 1.0, 1.3, 2.4, 2.7, 2.0, 1.3, 0.8, 0.4]); hw /= hw.sum()
    day = rng.choice(days, n_orders, p=dw)
    hour = rng.choice(24, n_orders, p=hw)
    placed = (dates[day] + pd.to_timedelta(hour, unit="h")
              + pd.to_timedelta(rng.integers(0, 3600, n_orders), unit="s"))
    order = pd.DataFrame({"order_id": np.arange(1, n_orders + 1), "customer_id": cust + 1,
                          "delivery_location_id": cust + 1, "order_placed_at": placed,
                          "payment_method": rng.choice(["card", "upi", "cash", "wallet"], n_orders, p=[.45, .25, .15, .15])})
    order = order.sort_values("order_placed_at").reset_index(drop=True)
    order["order_id"] = np.arange(1, n_orders + 1)
    city_idx = cust_city[order["customer_id"].to_numpy() - 1]
    order_city = np.array(names, dtype=object)[city_idx]

    # items
    n_items = rng.integers(1, 5, n_orders)
    item_order = np.repeat(order["order_id"].to_numpy(), n_items)
    pick = rng.integers(0, len(MENU), len(item_order))
    items = pd.DataFrame({"order_item_id": np.arange(1, len(item_order) + 1), "order_id": item_order,
                          "product_name": [MENU[i][0] for i in pick], "category": [MENU[i][1] for i in pick],
                          "unit_price": [MENU[i][2] for i in pick],
                          "quantity": rng.choice([1, 1, 1, 2, 2, 3], len(item_order))})
    order["total_amount"] = (items["unit_price"] * items["quantity"]).groupby(items["order_id"]).sum().round(2).to_numpy()

    # outcomes and stage timings (minutes after previous stage)
    u = rng.random(n_orders)
    last_stage = np.full(n_orders, 7)              # index into STAGES; 7 = DELIVERED
    terminal = np.array([""] * n_orders, dtype=object)
    early, mid = u < 0.05, (u >= 0.05) & (u < 0.07)
    failed = (u >= 0.07) & (u < 0.08)
    last_stage[early] = rng.integers(0, 2, early.sum()); terminal[early] = "CANCELLED"
    last_stage[mid] = 2; terminal[mid] = "CANCELLED"
    last_stage[failed] = 6; terminal[failed] = "FAILED"

    peak = np.isin(order["order_placed_at"].dt.hour.to_numpy(), [12, 13, 18, 19, 20])
    speed = np.array([CITIES[c][5] for c in order_city]) * np.where(peak, 1.18, 1.0)
    # demand/supply pressure: cities with fewer riders per order are slower
    supply_ratio = {c: CITIES[c][4] / CITIES[c][3] for c in names}
    speed = speed * np.array([1 + 0.35 * max(0, 1 - supply_ratio[c]) for c in order_city])

    # rider per order: same city, uniformly
    riders_by_city = {c: riders.loc[riders["city"] == c, "rider_id"].to_numpy() for c in names}
    rider = np.array([rng.choice(riders_by_city[c]) if len(riders_by_city[c]) else 0 for c in order_city])
    rskill = riders.set_index("rider_id")["skill"].reindex(rider).fillna(1.0).to_numpy()

    gaps = np.column_stack([
        np.zeros(n_orders),
        rng.uniform(0.5, 3, n_orders),                       # confirmed
        rng.uniform(1, 5, n_orders),                         # preparing
        rng.gamma(4, 2.4, n_orders) * speed,                 # ready
        rng.uniform(0.5, 4, n_orders) * speed,               # rider assigned
        rng.uniform(2, 9, n_orders) * speed,                 # picked up
        rng.uniform(0, 2, n_orders),                         # out for delivery
        rng.gamma(4, 3, n_orders) * speed * rskill,          # delivered
    ])
    times = order["order_placed_at"].to_numpy()[:, None] + pd.to_timedelta(gaps.cumsum(axis=1).ravel(), unit="m") \
        .to_numpy().reshape(n_orders, 8)

    # orders still in flight at the snapshot
    reached_time = times[np.arange(n_orders), last_stage]
    inflight = (pd.to_datetime(reached_time) > end) & (terminal == "")
    for i in np.where(inflight)[0]:
        ok = np.where(pd.to_datetime(times[i]) <= end)[0]
        last_stage[i] = ok.max() if len(ok) else 0

    status = np.array([STAGES[s] for s in last_stage], dtype=object)
    status = np.where(terminal != "", terminal, status)
    order["status"] = status
    has_rider = (last_stage >= 4) | (terminal == "FAILED")
    order["rider_id"] = pd.array(np.where(has_rider, rider, 0), dtype="Int64")
    order.loc[~has_rider, "rider_id"] = pd.NA

    # history (+ terminal row)
    h_ord, h_stat, h_time = [], [], []
    oid = order["order_id"].to_numpy()
    for s in range(8):
        m = last_stage >= s
        h_ord.append(oid[m]); h_stat.append(np.full(m.sum(), STAGES[s], dtype=object)); h_time.append(times[m, s])
    tm = terminal != ""
    h_ord.append(oid[tm]); h_stat.append(terminal[tm])
    h_time.append(times[np.where(tm)[0], last_stage[tm]] + np.timedelta64(2, "m"))
    hist = pd.DataFrame({"order_id": np.concatenate(h_ord), "status": np.concatenate(h_stat),
                         "changed_at": np.concatenate(h_time)}).sort_values(["order_id", "changed_at"])
    hist.insert(0, "history_id", np.arange(1, len(hist) + 1))

    # deliveries
    dm = has_rider
    deliveries = pd.DataFrame({
        "delivery_id": np.arange(1, dm.sum() + 1), "order_id": oid[dm], "rider_id": rider[dm],
        "assigned_at": times[dm, 4],
        "picked_up_at": np.where(last_stage[dm] >= 5, times[dm, 5], np.datetime64("NaT", "ns")),
        "delivered_at": np.where((last_stage[dm] >= 7) & (terminal[dm] == ""), times[dm, 7], np.datetime64("NaT", "ns")),
        "distance_km": rng.gamma(2.2, 1.6, dm.sum()).round(2)})
    deliveries["delivery_status"] = np.select(
        [deliveries["delivered_at"].notna(), terminal[dm] == "FAILED", deliveries["picked_up_at"].notna()],
        ["delivered", "failed", "picked_up"], "assigned")

    events = hist.rename(columns={"changed_at": "event_timestamp"}).copy()
    events["event_type"] = "ORDER_" + events["status"]
    events = events[["order_id", "event_type", "event_timestamp"]].reset_index(drop=True)

    injected = {}
    if issues:
        # 1. dirty city spellings
        k = int(len(locations) * 0.02)
        idx = rng.choice(locations.index, k, replace=False)
        variants = [lambda c: c.upper(), lambda c: c.lower(), lambda c: f" {c} ",
                    lambda c: f"{c}, {CITIES[c][0]}", lambda c: c[:3] + "."]
        locations["city"] = locations["city"].astype(object)
        locations.loc[idx, "city"] = [variants[i % 5](c) for i, c in zip(range(k), locations.loc[idx, "city"])]
        injected["dirty_city_spellings (DQ-10)"] = k
        # 2. clock skew: delivered before pickup
        cand = deliveries.index[deliveries["delivered_at"].notna()]
        k = int(len(cand) * 0.01)
        idx = rng.choice(cand, k, replace=False)
        deliveries.loc[idx, "delivered_at"] = deliveries.loc[idx, "picked_up_at"] - pd.to_timedelta(
            rng.uniform(1, 30, k), unit="m")
        injected["delivered_before_pickup (DQ-04)"] = k
        # 3. status drift: orders.status disagrees with history
        k = int(n_orders * 0.01)
        idx = rng.choice(order.index[order["status"] == "CANCELLED"], min(k // 2, (order["status"] == "CANCELLED").sum()), replace=False)
        idx2 = rng.choice(order.index[order["status"] == "DELIVERED"], k - len(idx), replace=False)
        order.loc[idx, "status"] = "DELIVERED"       # also creates delivered-without-rider (DQ-06)
        order.loc[idx2, "status"] = "OUT_FOR_DELIVERY"
        injected["status_drift (DQ-05)"] = int(len(idx) + len(idx2))
        injected["  of which delivered_without_rider (DQ-06)"] = int(len(idx))
        # 4. at-least-once redelivery duplicates
        k = int(len(events) * 0.015)
        events = pd.concat([events, events.sample(k, random_state=seed)], ignore_index=True)
        injected["duplicate_events (DQ-03)"] = k
    events = events.sort_values("event_timestamp").reset_index(drop=True)
    events.insert(0, "event_id", np.arange(1, len(events) + 1))

    order = order[["order_id", "customer_id", "delivery_location_id", "rider_id", "status",
                   "order_placed_at", "total_amount", "payment_method"]]
    return {"locations": locations, "customers": customers, "riders": riders.drop(columns="skill"),
            "orders": order, "order_items": items, "deliveries": deliveries,
            "order_status_history": hist, "event_log": events}, injected


DEMO_MAPPING = {
    "source": {"type": "csv", "path": "."},
    "tables": {
        "orders": {"from": "orders.csv",
                   "columns": {"order_id": "order_id", "customer_id": "customer_id", "rider_id": "rider_id",
                               "placed_at": "order_placed_at", "status": "status",
                               "total_amount": "total_amount", "city": "city"},
                   "join": [{"from": "locations.csv", "left_on": "delivery_location_id",
                             "right_on": "location_id", "columns": {"city": "city"}}]},
        "deliveries": {"from": "deliveries.csv",
                       "columns": {"order_id": "order_id", "rider_id": "rider_id", "assigned_at": "assigned_at",
                                   "picked_up_at": "picked_up_at", "delivered_at": "delivered_at",
                                   "status": "delivery_status", "distance_km": "distance_km"}},
        "riders": {"from": "riders.csv", "columns": {"rider_id": "rider_id", "city": "city", "is_active": "is_active"}},
        "customers": {"from": "customers.csv", "columns": {"customer_id": "customer_id", "signup_date": "signup_date"}},
        "order_items": {"from": "order_items.csv",
                        "columns": {"order_id": "order_id", "unit_price": "unit_price", "quantity": "quantity"}},
        "status_history": {"from": "order_status_history.csv",
                           "columns": {"order_id": "order_id", "status": "status", "changed_at": "changed_at",
                                       "seq": "history_id"}},
        "events": {"from": "event_log.csv",
                   "columns": {"event_id": "event_id", "order_id": "order_id", "event_type": "event_type",
                               "event_timestamp": "event_timestamp"}},
    },
    "status_map": {"delivered": ["DELIVERED"], "cancelled": ["CANCELLED"], "failed": ["FAILED"],
                   "in_progress": ["PLACED", "CONFIRMED", "PREPARING", "READY_FOR_PICKUP", "RIDER_ASSIGNED",
                                   "PICKED_UP", "OUT_FOR_DELIVERY"]},
    "settings": {"sla_minutes": 45, "currency": "$", "min_rider_deliveries": 20,
                 "lifecycle": STAGES},
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="demo_data")
    ap.add_argument("--orders", type=int, default=20_000)
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--end", default="2026-06-30 23:59:59", help="snapshot timestamp (fixed for reproducibility)")
    ap.add_argument("--no-issues", action="store_true")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    frames, injected = generate(args.orders, args.days, args.seed, not args.no_issues, pd.Timestamp(args.end))
    for name, df in frames.items():
        df.to_csv(os.path.join(args.out, f"{name}.csv"), index=False)
        print(f"  {name + '.csv':<28} {len(df):>9,} rows")
    with open(os.path.join(args.out, "mapping.json"), "w", encoding="utf-8") as fh:
        json.dump(DEMO_MAPPING, fh, indent=2)
    if injected:
        print("\nInjected data-quality defects (ground truth for dq_audit):")
        for k, v in injected.items():
            print(f"  {k:<44} {v:>7,}")
    print(f"\nDone: {os.path.abspath(args.out)} (mapping.json included)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
