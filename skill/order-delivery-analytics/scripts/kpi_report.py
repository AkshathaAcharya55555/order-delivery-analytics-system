#!/usr/bin/env python3
"""
Operational KPI report for order & delivery data.

Usage:
    python kpi_report.py --mapping mapping.json [--out kpi_report.md] [--json kpis.json]
                         [--since YYYY-MM-DD] [--until YYYY-MM-DD]

Computes volume, revenue, outcome mix, delivery-time percentiles, SLA breach,
peak hours, rider leaderboard, supply/demand balance, customer retention,
funnel and anomalies — then writes an executive-ready markdown report that
opens with auto-generated "Key findings". Sections whose inputs are not
mapped are omitted and listed at the end, never faked.

Delivery-time KPIs exclude rows that fail the data-quality sanity rules
(negative durations, or over settings.max_reasonable_delivery_hours); the
number excluded is always printed next to the metric.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, __import__("os").path.dirname(__file__))
from _common import (load_mapping, load_dataset, settings, md_table, bar, normalize_categories,  # noqa: E402
                     MappingError, eprint)

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _pct(n, d):
    return float(100.0 * n / d) if d else float("nan")


def _fmt_money(v, cur):
    return f"{cur}{v:,.2f}"


def compute(data: Dict[str, Optional[pd.DataFrame]], s: dict, since=None, until=None) -> dict:
    o = data["orders"].dropna(subset=["order_id", "placed_at"]).drop_duplicates("order_id").copy()
    if since:
        o = o[o["placed_at"] >= pd.Timestamp(since)]
    if until:
        o = o[o["placed_at"] < pd.Timestamp(until) + pd.Timedelta(days=1)]
    if o.empty:
        raise MappingError("No orders in the selected window.")
    k: dict = {"omitted": [], "notes": []}
    if s.get("normalize_city", True):
        o["city"], changed, fix = normalize_categories(o["city"])
        if changed:
            k["notes"].append(f"City spelling variants merged before grouping: {changed:,} orders "
                              f"({len(fix)} variants, e.g. " + ", ".join(f"'{a}'→'{b}'" for a, b in list(fix.items())[:3])
                              + "). Disable with settings.normalize_city=false.")
    o["city"] = o["city"].fillna("(unknown)")
    has_amount = "total_amount" in o.columns

    # ---------------- headline ----------------
    n = len(o)
    outcome = o["outcome"].value_counts()
    k["headline"] = {
        "orders": n,
        "from": o["placed_at"].min(), "to": o["placed_at"].max(),
        "days": int((o["placed_at"].max().normalize() - o["placed_at"].min().normalize()).days) + 1,
        "cities": int(o["city"].nunique()),
        "customers": int(o["customer_id"].nunique()) if "customer_id" in o.columns else None,
        "delivered_pct": _pct(outcome.get("delivered", 0), n),
        "cancelled_pct": _pct(outcome.get("cancelled", 0), n),
        "failed_pct": _pct(outcome.get("failed", 0), n),
        "in_progress_pct": _pct(outcome.get("in_progress", 0), n),
    }
    if has_amount:
        rev = o.loc[o["outcome"] != "cancelled", "total_amount"]
        k["headline"].update({"gmv": float(rev.sum()), "aov": float(rev.mean())})

    # ---------------- daily trend ----------------
    daily = o.groupby(o["placed_at"].dt.normalize()).agg(orders=("order_id", "size"))
    if has_amount:
        daily["revenue"] = o[o["outcome"] != "cancelled"].groupby(o["placed_at"].dt.normalize())["total_amount"].sum()
    daily = daily.asfreq("D", fill_value=0)
    daily["rolling_7d"] = daily["orders"].rolling(7, min_periods=1).mean()
    k["daily"] = daily

    monthly = o.groupby(o["placed_at"].dt.to_period("M")).agg(orders=("order_id", "size"))
    if has_amount:
        monthly["revenue"] = o[o["outcome"] != "cancelled"].groupby(o["placed_at"].dt.to_period("M"))["total_amount"].sum()
    monthly["mom_growth_pct"] = monthly["orders"].pct_change() * 100
    k["monthly"] = monthly

    # ---------------- by city ----------------
    city = o.groupby("city").agg(orders=("order_id", "size"))
    for oc in ("delivered", "cancelled", "failed"):
        city[f"{oc}_pct"] = o.assign(x=o["outcome"].eq(oc)).groupby("city")["x"].mean() * 100
    if has_amount:
        city["revenue"] = o[o["outcome"] != "cancelled"].groupby("city")["total_amount"].sum()

    # ---------------- delivery times ----------------
    dl = data["deliveries"]
    k["delivery"] = None
    if dl is not None and "delivered_at" in dl.columns:
        dd = dl.dropna(subset=["order_id", "delivered_at"]).drop_duplicates("order_id")
        cols = ["order_id", "delivered_at"] + [c for c in ("picked_up_at", "assigned_at", "rider_id") if c in dd.columns]
        m = o[["order_id", "placed_at", "city", "outcome"] + (["rider_id"] if "rider_id" in o.columns and "rider_id" not in cols else [])] \
            .merge(dd[cols], on="order_id", how="inner")
        m = m[m["outcome"] == "delivered"]
        m["mins"] = (m["delivered_at"] - m["placed_at"]).dt.total_seconds() / 60
        if "picked_up_at" in m.columns:
            m["last_mile"] = (m["delivered_at"] - m["picked_up_at"]).dt.total_seconds() / 60
        max_m = float(s["max_reasonable_delivery_hours"]) * 60
        bad = (m["mins"] < 0) | (m["mins"] > max_m) | (m.get("last_mile", pd.Series(0, index=m.index)) < 0)
        excluded = int(bad.sum())
        m = m[~bad]
        sla = float(s["sla_minutes"])
        m["breach"] = m["mins"] > sla
        if not m.empty:
            k["delivery"] = {
                "n": len(m), "excluded": excluded, "sla": sla,
                "avg": float(m["mins"].mean()), "p50": float(m["mins"].median()),
                "p90": float(m["mins"].quantile(0.9)), "p99": float(m["mins"].quantile(0.99)),
                "breach_pct": _pct(int(m["breach"].sum()), len(m)),
                "last_mile_p50": float(m["last_mile"].median()) if "last_mile" in m.columns else None,
            }
            g = m.groupby("city")["mins"]
            city["p50_mins"] = g.median()
            city["p90_mins"] = g.quantile(0.9)
            city["sla_breach_pct"] = m.groupby("city")["breach"].mean() * 100
            wk = m.groupby(m["placed_at"].dt.to_period("W-SUN"))
            k["weekly_delivery"] = pd.DataFrame({"deliveries": wk.size(), "p50_mins": wk["mins"].median(),
                                                 "p90_mins": wk["mins"].quantile(0.9),
                                                 "sla_breach_pct": wk["breach"].mean() * 100})
            # anomalies: > factor x city median
            med = m.groupby("city")["mins"].transform("median")
            f = float(s["long_delivery_factor"])
            k["anomalies"] = m[m["mins"] > f * med].sort_values("mins", ascending=False) \
                [["order_id", "city", "placed_at", "mins"]].assign(city_median=med[m["mins"] > f * med].round(1))
            k["_deliv_frame"] = m
    if k["delivery"] is None:
        k["omitted"].append("Delivery time & SLA (map deliveries.delivered_at)")
    k["city"] = city.sort_values("orders", ascending=False)

    # ---------------- time of day ----------------
    k["hourly"] = o.groupby(o["placed_at"].dt.hour)["order_id"].size().reindex(range(24), fill_value=0)
    heat = o.groupby([o["placed_at"].dt.dayofweek, o["placed_at"].dt.hour]).size().unstack(fill_value=0)
    k["heat"] = heat.reindex(index=range(7), columns=range(24), fill_value=0)

    # ---------------- riders ----------------
    k["riders"] = None
    if "_deliv_frame" in k and "rider_id" in k["_deliv_frame"].columns:
        m = k["_deliv_frame"].dropna(subset=["rider_id"])
        active_days = m.groupby("rider_id")["placed_at"].apply(lambda x: x.dt.normalize().nunique())
        r = m.groupby("rider_id").agg(city=("city", lambda x: x.mode().iat[0] if not x.mode().empty else ""),
                                       deliveries=("order_id", "size"), p50_mins=("mins", "median"),
                                       on_time_pct=("breach", lambda x: 100 * (1 - x.mean())))
        r["per_active_day"] = r["deliveries"] / active_days
        r = r[r["deliveries"] >= int(s["min_rider_deliveries"])]
        if not r.empty:
            r = r.reset_index()
            r["score"] = r["on_time_pct"].rank(pct=True) * 0.6 + r["per_active_day"].rank(pct=True) * 0.4
            k["riders"] = r.sort_values("score", ascending=False)
            supply = m.groupby("city")["rider_id"].nunique()
            k["city"]["active_riders"] = supply
            k["city"]["orders_per_rider"] = k["city"]["orders"] / supply
    if k["riders"] is None:
        k["omitted"].append(f"Rider leaderboard (needs rider_id + delivered_at, ≥{s['min_rider_deliveries']} deliveries/rider)")

    # ---------------- customers ----------------
    k["customers"] = None
    if "customer_id" in o.columns:
        per = o.dropna(subset=["customer_id"]).groupby("customer_id").size()
        buckets = pd.cut(per, bins=[0, 1, 2, 4, 9, np.inf], labels=["1", "2", "3-4", "5-9", "10+"])
        k["customers"] = {"total": int(len(per)), "repeat_pct": _pct(int((per > 1).sum()), len(per)),
                          "orders_per_customer": float(per.mean()),
                          "dist": buckets.value_counts().sort_index(),
                          "top10_share_pct": _pct(per.sort_values(ascending=False).head(max(1, len(per) // 10)).sum(), per.sum())}
    else:
        k["omitted"].append("Customer retention (map orders.customer_id)")

    # ---------------- funnel ----------------
    h = data["status_history"]
    k["funnel"] = None
    lifecycle = s.get("lifecycle")
    if h is not None and "status" in h.columns:
        hh = h[h["order_id"].isin(o["order_id"])]
        reached = hh.assign(st=hh["status"].str.upper().str.strip()).groupby("st")["order_id"].nunique()
        order = [x.upper() for x in lifecycle] if lifecycle else reached.sort_values(ascending=False).index.tolist()
        f = pd.DataFrame({"stage": order, "orders": [int(reached.get(x, 0)) for x in order]})
        f["pct_of_placed"] = f["orders"] / max(len(o), 1) * 100
        k["funnel"] = f
    else:
        k["omitted"].append("Order funnel (map status_history)")

    k.pop("_deliv_frame", None)
    k["findings"] = findings(k, s)
    return k


def findings(k: dict, s: dict) -> List[str]:
    out = []
    h = k["headline"]
    c = k["city"]
    # only rank cities with a meaningful share of volume (tiny groups give extreme, noisy rates)
    c = c[c["orders"] >= h["orders"] * float(s["min_city_share_pct"]) / 100]
    cur = s["currency"]
    if "gmv" in h:
        out.append(f"{h['orders']:,} orders over {h['days']} days generated {_fmt_money(h['gmv'], cur)} GMV "
                   f"(AOV {_fmt_money(h['aov'], cur)}).")
    if len(c) > 1:
        worst = c["cancelled_pct"].idxmax()
        out.append(f"Cancellation is highest in **{worst}** at {c.loc[worst, 'cancelled_pct']:.1f}% "
                   f"vs {h['cancelled_pct']:.1f}% overall.")
    d = k.get("delivery")
    if d:
        out.append(f"Median delivery takes {d['p50']:.0f} min, the slowest 10% take over {d['p90']:.0f} min; "
                   f"{d['breach_pct']:.1f}% of deliveries breach the {d['sla']:.0f}-min SLA.")
        if "sla_breach_pct" in c.columns and c["sla_breach_pct"].notna().sum() > 1:
            w = c["sla_breach_pct"].idxmax()
            b = c["sla_breach_pct"].idxmin()
            out.append(f"SLA breach ranges from {c.loc[b, 'sla_breach_pct']:.1f}% in {b} to "
                       f"**{c.loc[w, 'sla_breach_pct']:.1f}% in {w}** — the first city to investigate.")
        wk = k.get("weekly_delivery")
        if wk is not None and len(wk) >= 4:
            first, last = wk["p50_mins"].iloc[:2].mean(), wk["p50_mins"].iloc[-2:].mean()
            trend = "worsened" if last > first * 1.05 else "improved" if last < first * 0.95 else "held steady"
            out.append(f"Median delivery time has {trend} over the period ({first:.0f} → {last:.0f} min).")
    if "orders_per_rider" in c.columns and c["orders_per_rider"].notna().sum() > 1:
        hi = c["orders_per_rider"].idxmax()
        avg = c["orders_per_rider"].mean()
        out.append(f"**{hi}** carries {c.loc[hi, 'orders_per_rider']:.0f} orders per active rider vs a "
                   f"{avg:.0f} average — likely under-supplied; check whether its SLA breach is correlated.")
    hr = k["hourly"]
    peak = int(hr.idxmax())
    top3 = hr.sort_values(ascending=False).head(3)
    out.append(f"Demand peaks at {peak:02d}:00; the top three hours ({', '.join(f'{i:02d}:00' for i in top3.index)}) "
               f"carry {100 * top3.sum() / hr.sum():.0f}% of orders — staff riders accordingly.")
    cu = k.get("customers")
    if cu:
        out.append(f"{cu['repeat_pct']:.1f}% of customers ordered more than once; the top 10% of customers "
                   f"place {cu['top10_share_pct']:.0f}% of orders.")
    mo = k["monthly"]
    if len(mo) >= 2 and pd.notna(mo["mom_growth_pct"].iloc[-1]):
        out.append(f"Latest month ({mo.index[-1]}) order volume changed {mo['mom_growth_pct'].iloc[-1]:+.1f}% "
                   f"vs the prior month (partial months distort this — check the date range).")
    return out


def render(k: dict, s: dict, mapping_path: str) -> str:
    h, cur = k["headline"], s["currency"]
    L = [f"# Order & Delivery Performance Report\n\n",
         f"_Period {h['from']:%Y-%m-%d} → {h['to']:%Y-%m-%d} · generated {datetime.now():%Y-%m-%d %H:%M} "
         f"from `{mapping_path}`_\n\n"]
    L.append("## Key findings\n\n" + "".join(f"- {f}\n" for f in k["findings"]) + "\n")

    L.append("## Headline KPIs\n\n")
    rows = [("Orders", f"{h['orders']:,}"), ("Days", h["days"]), ("Cities", h["cities"])]
    if h.get("customers") is not None:
        rows.append(("Customers", f"{h['customers']:,}"))
    if "gmv" in h:
        rows += [("GMV (excl. cancelled)", _fmt_money(h["gmv"], cur)), ("Avg order value", _fmt_money(h["aov"], cur))]
    rows += [("Delivered", f"{h['delivered_pct']:.1f}%"), ("Cancelled", f"{h['cancelled_pct']:.1f}%"),
             ("Failed", f"{h['failed_pct']:.1f}%"), ("Still in progress", f"{h['in_progress_pct']:.1f}%")]
    d = k.get("delivery")
    if d:
        rows += [("Delivery time p50 / p90 / p99", f"{d['p50']:.1f} / {d['p90']:.1f} / {d['p99']:.1f} min"),
                 (f"SLA breach (> {d['sla']:.0f} min)", f"{d['breach_pct']:.1f}%")]
        if d["last_mile_p50"] is not None:
            rows.append(("Last-mile (pickup→drop) p50", f"{d['last_mile_p50']:.1f} min"))
        rows.append(("Rows excluded as invalid", f"{d['excluded']:,} (see dq_audit DQ-04/DQ-12)"))
    L.append(md_table(pd.DataFrame(rows, columns=["Metric", "Value"])) + "\n")

    L.append("## City scorecard\n\n")
    c = k["city"].reset_index().rename(columns={"index": "city"})
    L.append(md_table(c, floatfmt="{:,.1f}") + "\n")

    L.append("## Trend\n\n### Monthly\n\n")
    mo = k["monthly"].reset_index()
    mo["placed_at"] = mo["placed_at"].astype(str)
    L.append(md_table(mo.rename(columns={"placed_at": "month"}), floatfmt="{:,.1f}") + "\n")
    L.append("### Last 14 days\n\n")
    dl = k["daily"].tail(14).reset_index().rename(columns={"placed_at": "day"})
    mx = dl["orders"].max()
    dl["volume"] = dl["orders"].map(lambda v: bar(v, mx))
    L.append(md_table(dl, floatfmt="{:,.1f}") + "\n")
    if k.get("weekly_delivery") is not None:
        L.append("### Weekly delivery performance\n\n")
        wk = k["weekly_delivery"].reset_index()
        wk.iloc[:, 0] = wk.iloc[:, 0].astype(str)
        L.append(md_table(wk.rename(columns={wk.columns[0]: "week"}), floatfmt="{:,.1f}") + "\n")

    L.append("## When orders arrive\n\n")
    hr = k["hourly"]
    hdf = pd.DataFrame({"hour": [f"{i:02d}:00" for i in hr.index], "orders": hr.values,
                        "share %": (100 * hr / hr.sum()).round(1).values,
                        "": [bar(v, hr.max()) for v in hr.values]})
    L.append(md_table(hdf) + "\n")
    heat = k["heat"]
    shades = " ░▒▓█"
    hm = heat.to_numpy()
    top = hm.max() or 1
    axis = list(" " * 24)
    for hh in (0, 6, 12, 18):
        for j, ch in enumerate(str(hh)):
            axis[hh + j] = ch
    L.append("Day × hour heatmap (darker = busier)\n\n```\n     " + "".join(axis) + "  (hour)\n")
    for i, dname in enumerate(DOW):
        L.append(f"{dname}  " + "".join(shades[min(4, int(4 * v / top + 0.5))] for v in hm[i]) + "\n")
    L.append("```\n\n")

    if k.get("riders") is not None:
        r = k["riders"]
        cols = ["rider_id", "city", "deliveries", "per_active_day", "p50_mins", "on_time_pct"]
        L.append(f"## Riders (≥{s['min_rider_deliveries']} deliveries; score = 60% on-time rank + 40% throughput rank)\n\n")
        L.append("### Top 10\n\n" + md_table(r[cols].head(10), floatfmt="{:,.1f}") + "\n")
        L.append("### Bottom 10 — coaching candidates\n\n" + md_table(r[cols].tail(10).iloc[::-1], floatfmt="{:,.1f}") + "\n")

    if k.get("customers"):
        cu = k["customers"]
        L.append("## Customers\n\n")
        L.append(f"- Customers: {cu['total']:,} · repeat rate **{cu['repeat_pct']:.1f}%** · "
                 f"{cu['orders_per_customer']:.2f} orders per customer · top-10% share {cu['top10_share_pct']:.0f}%\n\n")
        dist = cu["dist"].reset_index()
        dist.columns = ["orders placed", "customers"]
        dist[""] = dist["customers"].map(lambda v: bar(v, dist["customers"].max()))
        L.append(md_table(dist) + "\n")

    if k.get("funnel") is not None:
        L.append("## Order funnel (orders that ever reached each stage)\n\n")
        f = k["funnel"].copy()
        f[""] = f["orders"].map(lambda v: bar(v, f["orders"].max()))
        L.append(md_table(f, floatfmt="{:,.1f}") + "\n")

    an = k.get("anomalies")
    if an is not None and not an.empty:
        L.append(f"## Abnormally long deliveries (> {s['long_delivery_factor']}× city median) — {len(an):,} orders\n\n")
        L.append(md_table(an.head(15).rename(columns={"mins": "minutes"}), floatfmt="{:,.1f}") + "\n")

    if k["omitted"]:
        L.append("## Not computed (inputs not mapped)\n\n" + "".join(f"- {x}\n" for x in k["omitted"]))
    if k.get("notes"):
        L.append("\n## Data handling notes\n\n" + "".join(f"- {x}\n" for x in k["notes"]))
    return "".join(L)


def _jsonable(obj):
    if isinstance(obj, pd.DataFrame):
        df = obj.reset_index()
        for col in df.columns:
            if not pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].astype(str)
        return df.to_dict(orient="records")
    if isinstance(obj, pd.Series):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    return obj


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mapping", required=True)
    ap.add_argument("--out", default="kpi_report.md")
    ap.add_argument("--json", default=None)
    ap.add_argument("--since")
    ap.add_argument("--until")
    args = ap.parse_args(argv)
    try:
        mapping = load_mapping(args.mapping)
        s = settings(mapping)
        k = compute(load_dataset(mapping), s, args.since, args.until)
    except MappingError as exc:
        eprint(f"Error: {exc}")
        return 2
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(render(k, s, args.mapping))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(_jsonable({x: y for x, y in k.items() if x != "heat"}), fh, indent=2)
    print("Key findings:")
    for f in k["findings"]:
        print(" -", f.replace("**", ""))
    print(f"\nReport written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
