# Project Status

Current, factual status of every major component as of the final audit
(2026-09-16). "Verified" means actually run/tested during this project's
work, not assumed from documentation. See `docs/FINAL_AUDIT.md` for the
full findings behind this table.

| Component | Status | Verified? |
|---|---|---|
| Order Service | Working. 23/23 tests passing. | Yes — `mvn test` re-run clean; full order-create/validate/cancel flow re-tested live via curl against the containerized service. |
| Delivery Service | Working, N+1 rider-matching bug found and fixed this pass. 24/24 tests passing. | Yes — `mvn test` re-run clean; rider assignment re-tested live against Miami's 313 real riders post-fix (8.95s cold, 0.456s warm, down from >120s). |
| Tracking Service | Working. 12/12 tests passing. | Yes — `mvn test` re-run clean; tracking history re-confirmed live via curl. |
| Kafka | Working. 7 topics, idempotent consumption confirmed. | Yes — real events re-confirmed reaching `processed_events` for orders created during this audit's own live testing. |
| Redis | Working (cache-aside). Fallback to Postgres is correct but slow under an outage (documented, unfixed). | Yes — correctness verified in an earlier phase by physically stopping the Redis container; not re-tested this pass (no code changed). |
| PostgreSQL | Working. Live schema (9 tables, 6 views) confirmed to match `schema.sql`/`views.sql` exactly. | Yes — `\dt`/`\dv` against the live container this pass. |
| SQL Analytics | Working. All 20 queries execute successfully. | Yes — all 20 files re-run directly via `psql` this pass, independent of the pytest suite. |
| Python Analytics | Working. A real bug (`localhost`/IPv6 connection flakiness) found and fixed this pass. | Yes — `run_eda.py` re-run end-to-end with the fix and no environment override; completed successfully, 6 charts regenerated. |
| Data Quality | Working. 10 rules produce the same results as every prior run (validates raw, unchanged CSVs). | Yes — `python data_quality/validate.py` re-run this pass; output unchanged from prior runs, as expected. |
| Dashboard | Working, reads live data (not hardcoded). Test-data contamination (a fake 7th city) found and cleaned this pass. | Yes — re-run via `streamlit.testing.v1.AppTest` this pass against the cleaned database; cross-checked against `run_eda.py`'s output and they matched. |
| Docker | Working. Config valid; delivery-service image actually rebuilt and redeployed this pass. | Yes — `docker compose config --quiet` passed; full 7-container stack brought up and health-checked this pass. |
| Testing | 123 automated tests, 0 failures (was 122; +1 new test added this pass for the N+1 fix). | Yes — every suite re-run clean this pass (see rows above + `docs/TESTING.md`). |
| Documentation | Restructured and numerically audited; two stale numbers found and corrected (an index count, a per-service test count). | Yes — cross-checked against live system state this pass, not re-read on faith. |

## What changed in this pass

- Fixed: rider-matching N+1 query (delivery-service) — real, measured
  before/after (see `docs/FINAL_AUDIT.md` H1).
- Fixed: `analytics/scripts/db.py`'s `localhost`/IPv6 connection flakiness
  — reproduced live, fixed, re-verified (H2).
- Fixed: test-data contamination in the live database (a fake
  "Nowhereville" city) — identified precisely, removed, re-verified (H3).
- Documented, not fixed (by design — MEDIUM/LOW, outside this pass's fix
  scope): exception-handler information disclosure, Redis-outage failover
  latency, the synthetic dataset's missing RIDER_ASSIGNED/PICKED_UP history
  stages, Docker images running as root, an unused test dependency, and
  minor repository-hygiene items — all in `docs/FINAL_AUDIT.md`.
- Repository cleaned: removed `.env`, `.pytest_cache/`, all `__pycache__/`
  directories, all three services' `target/` build directories, unrelated
  dead tooling scaffolding (`.github/modernize/`), and the large generated
  dataset (`data_generator/output/`, ~114MB — regenerable, was already
  `.gitignore`d). Added `.pytest_cache/` to `.gitignore` (was missing).
