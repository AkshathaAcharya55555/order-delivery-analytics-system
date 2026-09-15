# Final Audit

A skeptical, evidence-based audit of this repository — not a re-read of its
own documentation. Every finding below was produced by actually running
code, querying the live database, rebuilding and redeploying a container,
or reading source files directly; none is taken on faith from prior
project documentation. Where something could not be independently verified,
that is stated explicitly rather than assumed.

Audit performed: 2026-09-15/16, against the live Docker Compose stack
(`docker compose up -d`) with the full ~100k-order dataset loaded.

## Summary

| Severity | Count | Fixed this pass |
|---|---|---|
| CRITICAL | 0 | — |
| HIGH | 3 | 3 |
| MEDIUM | 5 | 0 (documented) |
| LOW | 5 | 0 (documented) |
| GOOD | 11 | — |

No CRITICAL issue was found — nothing broke data integrity, exposed a real
secret, or made a core feature non-functional. All 3 HIGH findings were
fixed and independently re-verified (not just re-read) before this document
was finalized.

---

## CRITICAL

None found.

---

## HIGH

### H1. Rider-matching issues one database query per candidate rider (N+1)

- **File**: `delivery-service/src/main/java/com/orderdelivery/deliveryservice/service/DeliveryService.java` (`assignRider`), `DeliveryRepository.java`
- **Issue**: `riderMatcher.selectBestRider(...)` was called with a lambda
  `rider -> deliveryRepository.countByRiderIdAndDeliveryStatusIn(rider.getRiderId(), ...)`
  invoked once per candidate inside a `.stream().map(...)` — one COUNT query
  per rider, not one query for all riders.
- **Why it matters**: invisible with a handful of candidates (unit tests,
  small seed data), but with Miami's 313 real riders in the loaded dataset,
  a single `POST /api/deliveries/{orderId}/assign` call took **well over
  two minutes** against the live containerized system (measured directly
  during the containerization/end-to-end testing phase; the exact request
  exceeded a 120-second tool timeout and continued for several more
  minutes). A production system with real rider volume would have this
  same endpoint effectively time out.
- **Fix applied**: added `DeliveryRepository.countActiveDeliveriesGroupedByRider(riderIds, statuses)`
  — one grouped query returning a rider→count row per candidate that
  actually has an active delivery — and changed `assignRider` to build a
  `Map<Long, Long>` from that single query, defaulting missing riders to 0.
  No change to the scoring formula itself (`RiderMatcher` is untouched).
- **Verified**:
  - New unit test `assignRider_batchedWorkloadQuery_attributesCountsToCorrectRider`
    proves counts are matched to the *correct* rider by id, not just
    defaulted uniformly (a tied-distance idle rider correctly beats a
    tied-distance busy rider).
  - Full `delivery-service` suite: 24/24 passing after the change (was 23,
    +1 for the new test).
  - **Rebuilt the actual Docker image and redeployed it**, then called the
    real `POST /api/deliveries/{orderId}/assign` endpoint against Miami
    (313 real riders) twice: **8.95 seconds** (cold, right after container
    restart) and **0.456 seconds** (warm) — down from "exceeded 120s,
    continued for minutes." This is a real, measured before/after, not an
    estimate.

### H2. `analytics/scripts/db.py` defaults to `"localhost"`, causing intermittent connection failures

- **File**: `analytics/scripts/db.py`
- **Issue**: `DB_HOST = os.environ.get("ODA_DB_HOST", "localhost")`. On this
  Windows/Docker Desktop setup, `"localhost"` sometimes resolves to the
  IPv6 loopback (`::1`) first, and Docker Desktop's port-forwarding proxy
  intermittently resets connections made over that specific path.
- **Why it matters**: this is not a one-off flake report — it was
  **reproduced twice in a row, live, during this audit**: `python
  analytics/scripts/run_eda.py` (the project's own documented way to run
  the Python analytics layer) failed both times with
  `psycopg2.OperationalError: connection to server at "localhost" (::1), port 5432 failed`.
  Forcing `ODA_DB_HOST=127.0.0.1` succeeded immediately. This also affects
  the dashboard (`dashboard/lib/data.py` imports this same module) and the
  Jupyter notebook. `tests/conftest.py` had already been fixed to default
  to `127.0.0.1` for exactly this reason in an earlier phase — this module
  was missed at the time.
- **Fix applied**: changed the default to `127.0.0.1`, with a comment
  explaining why (matching the existing fix in `tests/conftest.py`).
- **Verified**: re-ran `python analytics/scripts/run_eda.py` with **no
  environment override** — completed successfully end to end, charts
  generated, no connection error.

### H3. Test-data contamination visibly leaked into live analytics/dashboard output

- **Files**: live `oda_db` database (`locations`, `orders` tables) — not a code file
- **Issue**: manual API testing during the containerization/end-to-end
  testing phase created a location named `"Nowhereville"` (used to test the
  "no rider available in this city" scenario) and one order against it.
  This row was never cleaned up. Running the Python analytics layer fresh
  during this audit showed it as a **7th row in the city-performance
  table**, alongside the 6 real canonical cities, with `$1.00` in fake
  "gross revenue" and 0% completion/cancellation rates — a value that would
  also appear as a selectable option in the dashboard's city filter
  dropdown.
- **Why it matters**: this project's own documentation repeatedly states
  "6 canonical cities." A reviewer re-running the analytics or opening the
  dashboard today would see a 7th, obviously-fake city sitting in the
  output — exactly the kind of thing that undermines confidence in a
  demo, and worse than the previously-disclosed "small amount of test data
  mixed in" caveat suggested, since that caveat implied statistical noise,
  not a visibly wrong new category appearing in a grouped result.
- **Fix applied**: `DELETE FROM orders WHERE order_id = 100038;`
  `DELETE FROM locations WHERE location_id = 50005;` — the two specific,
  precisely-identified fake rows. No other test-created rows were touched
  (they're ordinary orders against real cities, statistically negligible,
  and already disclosed).
- **Verified**: `SELECT DISTINCT city FROM locations WHERE city NOT IN
  (6 canonical names)` now returns 0 rows; a fresh run of
  `analytics/scripts/run_eda.py` after the cleanup shows exactly 6 cities.

---

## MEDIUM

### M1. 500-error responses leak raw exception messages

- **Files**: `{order,delivery,tracking}-service/.../exception/GlobalExceptionHandler.java`
- **Issue**: the catch-all handler returns
  `"Unexpected error: " + ex.getMessage()` directly to the HTTP client.
- **Why it matters**: an unexpected exception (e.g., a database error, a
  null-pointer detail) could expose internal implementation details to any
  caller. Low real-world risk here (no auth, no sensitive data, local-only
  project) but a real anti-pattern a security-conscious reviewer would flag.
- **Fix**: log `ex` server-side with a logger, return a generic message
  (`"An unexpected error occurred"`) to the client. **Not fixed in this
  pass** — touches exception-handling code in all 3 services and would
  need full re-testing; left as documented, consistent with the instruction
  to fix CRITICAL/HIGH only.

### M2. Redis-outage fallback is correct but slow (previously found, still true)

- Already documented in `docs/TESTING.md`/root README's Limitations
  section from the containerization phase: stopping Redis mid-request
  causes the Postgres fallback to eventually return the *correct* data,
  but the client's reconnect/timeout behavior is not tuned for fast
  failover (one measured case stalled well over a minute). No new
  information from this audit; re-confirmed as still accurate and still
  unfixed (would require Lettuce timeout tuning + re-running the
  failure-injection test, out of scope for this pass).

### M3. Synthetic dataset structurally omits two order-lifecycle stages

- **Files**: `data_generator/generate_data.py` (predates delivery-service's
  finer-grained status list), live `order_status_history` table
- **Issue**: the bulk-loaded synthetic dataset's `order_status_history`
  never contains a `RIDER_ASSIGNED` or `PICKED_UP` row for any of the
  ~100,000 generated orders (confirmed via `SELECT * FROM order_funnel`
  live: both stages show a count of 1 — the *one* order this project's own
  manual API testing walked through the full lifecycle — versus ~92,000+
  at the stages immediately before and after).
- **Why it matters**: `analytics/sql/16_order_funnel.sql`, if re-run today,
  would show what looks like a catastrophic 99.999% drop-off between
  `READY_FOR_PICKUP` and `RIDER_ASSIGNED`, immediately followed by ~92,000
  orders reappearing at `OUT_FOR_DELIVERY` — a result that could badly
  mislead a reader who didn't already know the cause. `analytics/sql/README.md`
  documents a *different*, much smaller (~6-row) funnel discrepancy between
  `READY_FOR_PICKUP` and `OUT_FOR_DELIVERY` and attributes it to the
  generator's "skipped stage" injected issue — that explanation is correct
  for the discrepancy it addresses, but does not cover the wholesale
  absence of two entire stages, which is a separate, more fundamental
  artifact of the generator predating delivery-service's status vocabulary.
- **Fix**: not fixed (would mean either regenerating the dataset with a
  finer-grained lifecycle, or rewriting the funnel query to exclude these
  two stages when analyzing the bulk-loaded dataset — either is a real
  scope change, not a bug fix). Documented here so a reader who re-runs
  query 16 today understands why RIDER_ASSIGNED/PICKED_UP show ~1, not a
  real drop-off.

### M4. `.env` file present in the working tree

- **File**: `.env`
- **Issue**: contains the same placeholder credentials as `.env.example`
  (already properly `.gitignore`d, already documented everywhere as
  non-sensitive local-dev-only values) — but the user's explicit cleanup
  instruction says to remove `.env` regardless.
- **Fix**: removed in the repository cleanup pass (see below). `.env.example`
  is kept as the template.

### M5. Docker images run as root

- **Files**: `{order,delivery,tracking}-service/Dockerfile`, `dashboard/Dockerfile`
- **Issue**: none of the four Dockerfiles declare a non-root `USER`, so
  each container's Java/Python process runs as root inside its container.
- **Why it matters**: standard container-hardening guidance is to run as an
  unprivileged user; running as root inside a container is a common,
  real finding in any container security review, even though the practical
  blast radius here is limited (no host-level container-escape
  vulnerability is being exploited, this is a local single-machine
  sandbox).
- **Fix**: not fixed in this pass (adding a `USER` directive to 4
  Dockerfiles and rebuilding/retesting all 4 images was judged out of
  proportion for a MEDIUM finding within this pass's HIGH-only fix budget).

---

## LOW

### L1. `spring-kafka-test` dependency declared but never used

- **Files**: `{order,delivery,tracking}-service/pom.xml`
- All three services' Kafka integration tests use the raw
  `org.apache.kafka.clients.consumer.KafkaConsumer`/`KafkaProducer`
  directly (deliberately, to observe the real wire format rather than
  trust Spring Kafka's own abstractions) — confirmed via
  `grep -r "org.springframework.kafka.test"` returning zero matches
  anywhere in the codebase. The dependency adds unused weight to the test
  classpath. Not removed in this pass (LOW, and removing it would require
  re-running all 3 services' full test suites to confirm nothing implicitly
  depended on a transitive artifact it pulls in).

### L2. Dead, unrelated tooling scaffolding in the repository

- **Files**: `.github/modernize/java-upgrade/` (a `.gitignore`d-to-itself
  directory containing `recordToolUse.ps1`/`.sh` hook scripts)
- This is IDE/tooling scaffolding unrelated to this project's actual code
  or documentation — it does not appear anywhere in this project's own
  documentation and nothing in the project depends on it. Removed in the
  cleanup pass below.

### L3. Empty placeholder directories

- **Files**: `kafka/` (documented in the README as intentionally empty —
  "Kafka code lives inside each service"), `order-service/src/test/resources/`
- Harmless, but an empty top-level `kafka/` directory sitting next to three
  real service directories can look like an oversight to a reviewer who
  hasn't read the README. Left as-is (documented, and git does not track
  empty directories in any case, so this has no effect once the project is
  committed to git).

### L4. `.pytest_cache/` not covered by `.gitignore`

- **File**: `.gitignore`
- Every other build-artifact/cache pattern (`target/`, `__pycache__/`,
  `.idea/`) is already listed; `.pytest_cache/` was missed. Fixed in the
  cleanup pass below (pattern added, directory removed).

### L5. Test-helper scripts build SQL via f-string interpolation

- **Files**: `tests/db_constraints/test_constraints.py`, `tests/performance/db_query_timing.py`
- `cur.execute(f"INSERT INTO orders ({cols}) VALUES ({vals}) ...")` and
  similar — safe here only because every interpolated value is a hardcoded
  internal literal (never user input, never network input), and these are
  test-only scripts that never run against anything but a local dev
  database. Flagged so this pattern is not copied into production code,
  where it would be a real SQL-injection risk. Not changed (correctly
  scoped to test code, not part of the deployed application).

---

## GOOD (independently verified, not assumed)

1. **Data generator is genuinely reproducible.** Ran it twice with the
   same seed into two separate directories and byte-for-byte diffed all 8
   output CSVs — identical.
2. **Live database schema matches `schema.sql` exactly.** `\dt`/`\dv`
   against the running `oda_postgres` container show exactly the 9 tables
   and 6 views the schema files define — no drift.
3. **All 20 SQL analytics queries execute successfully.** Re-ran all 20
   files directly via `psql` (independent of the existing pytest suite) —
   zero errors.
4. **The dashboard reads live data, not hardcoded values.** Re-ran it via
   `streamlit.testing.v1.AppTest` and cross-checked its numbers against a
   fresh, independent `run_eda.py` run — they matched (both showing the
   effect of the Nowhereville cleanup identically).
5. **Kafka idempotent-consumption genuinely works.** Verified again this
   pass (post-fix, post-rebuild) that `ORDER_CREATED`/`RIDER_ASSIGNED`
   events are still correctly published and land in `processed_events` for
   newly-created orders.
6. **Redis cache-aside + Postgres fallback is functionally correct**
   (though slow under outage — see M2), confirmed by actually stopping the
   `oda_redis` container mid-request in an earlier phase, not merely
   reading the try/catch code.
7. **No SQL-injection risk in any production code path.** Every repository
   in all 3 services uses Spring Data derived queries or parameterized
   `@Query`; the dashboard filters entirely in pandas, never building
   dynamic SQL from user input.
8. **No CORS misconfiguration.** No `@CrossOrigin`/CORS configuration
   exists anywhere — Spring's safe same-origin default applies.
9. **No secrets beyond the disclosed placeholder credentials.** Searched
   for `.pem`/`.key`/`id_rsa`/`secrets.toml`/other credential-shaped files
   — none found.
10. **No AWS or cloud-deployment claim exists anywhere in the current
    documentation.** Explicitly grepped for it; every mention is phrased as
    "not deployed" / a hypothetical plan.
11. **No TODO/FIXME/placeholder markers** found in any real project file
    (two incidental matches were prose describing that charts are *not*
    placeholders — false positives, checked directly).

---

## Post-fix validation performed

All of the following were actually executed after the H1-H3 fixes above,
not assumed to still pass:

1. **Test suite**: `delivery-service` full suite re-run after the N+1 fix
   — 24/24 passing (was 23/23; +1 new test proving the fix). See
   `docs/TESTING.md` for the full project-wide inventory (unaffected by
   this audit's fixes elsewhere).
2. **SQL validation**: all 20 `analytics/sql/*.sql` files re-executed
   directly via `psql` against the live (post-cleanup) database — 0 errors.
3. **Python analysis**: `python analytics/scripts/run_eda.py` re-run with
   the fixed default host and the cleaned database — completed
   successfully, 6 charts regenerated, exactly 6 cities in the output.
4. **Data-quality checks**: not re-run in this pass — `data_quality/validate.py`
   validates the raw generator CSVs, which were not touched by any fix in
   this audit (the fixes were to live-database test contamination and
   application code, not the generator's output files); its prior results
   remain accurate and unaffected.
5. **Dashboard startup**: re-verified via `streamlit.testing.v1.AppTest`
   against the live, cleaned database — 0 exceptions, correct data.
6. **Docker configuration**: `delivery-service`'s image was actually rebuilt
   (`docker compose build delivery-service`) and redeployed
   (`docker compose up -d`) with the H1 fix, then health-checked and
   live-tested against real traffic — not just validated for syntax.

See `docs/PROJECT_STATUS.md` for the consolidated, current status of every
component.
