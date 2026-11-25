# Mapping file specification

`mapping.json` tells the scripts where the data lives and which source column
plays each canonical role. `profile_source.py` drafts one. Edit it by hand to
confirm or fix guesses. Relative paths resolve against the mapping file's
own folder.

## Top level

```json
{
  "source":     { "type": "csv", "path": "./data" },
  "tables":     { "<entity>": { ... } },
  "status_map": { "delivered": [...], "cancelled": [...], "failed": [...], "in_progress": [...] },
  "settings":   { "sla_minutes": 45 }
}
```

### `source`

| type  | fields | notes |
|-------|--------|-------|
| `csv` | `path` | Folder of CSV files. `tables.*.from` is a file name. |
| `sql` | `url_env` (default `DATABASE_URL`) | Any SQLAlchemy URL, read from that **environment variable** (never put credentials in the file). `tables.*.from` is a table/view name (`schema.table` allowed) or `{"query": "SELECT ..."}`. `postgres` is accepted as an alias. |

Example URLs: `postgresql://$DB_USER:$DB_PASSWORD@host:5432/db` (psycopg2), `mysql+pymysql://$DB_USER:$DB_PASSWORD@host/db`,
`sqlite:///local.db`, `snowflake://...` (snowflake-sqlalchemy).

## Entities and canonical columns

Only `orders.order_id`, `orders.placed_at` and `orders.status` are required.
Every other entity and column is optional. Rules and KPIs that need a missing
input are reported as **SKIPPED / Not computed**, never faked.

| entity | canonical columns |
|---|---|
| `orders` | `order_id`*, `placed_at`*, `status`*, `customer_id`, `rider_id`, `total_amount`, `city` |
| `deliveries` | `order_id`, `rider_id`, `assigned_at`, `picked_up_at`, `delivered_at`, `status`, `distance_km` |
| `riders` | `rider_id`, `city`, `is_active` |
| `customers` | `customer_id`, `signup_date` |
| `order_items` | `order_id`, `unit_price`, `quantity` |
| `status_history` | `order_id`, `status`, `changed_at`, `seq` (tie-breaker for equal timestamps) |
| `events` | `event_id`, `order_id`, `event_type`, `event_timestamp` |

"Rider" means any courier, driver, delivery partner or agent. "City" means any
operational grouping: city, zone, hub, market or region.

Derivations applied automatically:
- `orders.rider_id` is filled from `deliveries.rider_id` when not mapped directly.
- `orders.city` is filled from the rider's city when not mapped and riders are mapped.
- Without any city, everything is reported as a single group `(all)`.

### Table spec

```json
"orders": {
  "from": "orders.csv",
  "columns": { "order_id": "id", "placed_at": "created_at", "status": "state", "city": "city" },
  "join": [
    { "from": "locations.csv", "left_on": "delivery_location_id",
      "right_on": "location_id", "columns": { "city": "city" } }
  ]
}
```

- `columns` maps **canonical name → source column name**.
- `join` (optional, repeatable) left-joins a lookup table **before** renaming.
  `columns` there maps *new column name in the left table → column in the lookup*.
  Use it when a field lives one hop away, as with city on an address table.
- For SQL sources, a `{"query": "..."}` in `from` handles anything more complex.
  Joins, filters and unions all belong in SQL.

### Timestamps

Parsed with pandas (`errors="coerce"`). Unparseable values become missing and
are counted by DQ-09. Timezone-aware values are converted to UTC and made
naive. If the source mixes local and UTC times, fix that in a `query` source
first.

## `status_map`

Buckets each raw status value into one outcome:
`delivered`, `cancelled`, `failed` or `in_progress`. Matching ignores case and
surrounding whitespace. Values not listed become `unknown`, and DQ-13 flags
them. If `status_map` is empty, a keyword heuristic is used: deliver/complete
→ delivered, cancel/reject → cancelled, fail/return → failed, anything else →
in_progress.

## `settings`

| key | default | meaning |
|---|---|---|
| `sla_minutes` | 45 | Placed → delivered target. **Ask the user; 45 is only a placeholder.** |
| `currency` | `$` | Prefix for money in reports |
| `min_rider_deliveries` | 20 | Riders below this are left out of leaderboards |
| `min_city_share_pct` | 1.0 | Cities under this share of orders are not named as best or worst in findings |
| `normalize_city` | true | Merge spelling variants (`AUSTIN`, `Austin, TX`, `Aus.`) before grouping |
| `long_delivery_factor` | 3.0 | An "abnormally long" delivery exceeds this multiple of its city's median |
| `max_reasonable_delivery_hours` | 6 | Durations above this are excluded from KPIs and flagged by DQ-12 |
| `amount_tolerance` | 0.01 | DQ-14 tolerance between the order total and the sum of its items |
| `lifecycle` | – | Ordered list of statuses for the funnel. If missing, stages are sorted by reach |
| `skip_rules` | [] | e.g. `["DQ-14"]` when totals include tax or fees by design |
