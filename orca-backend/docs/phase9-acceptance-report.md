# Phase 9 — Acceptance Report (Real-World Integration + Operational Validation)

Date: 2026-08-31 · Scope: bring the ORCA platform from "production-ready
architecture" to an "operationally validated marine intelligence platform".

## Acceptance criteria — evidence

| # | criterion | evidence | result |
|---|---|---|---|
| 1 | real source matrix exists | `docs/phase9-source-matrix.md` + `reports/live-latest.md` (6 sources) | PASS |
| 2 | source health monitor exists | `SourceHealthMonitor` in `apps/api/app/services/source_health.py`, verdicts HEALTHY/DEGRADED/UNAVAILABLE/STALE/UNKNOWN; `test_p2_*` | PASS |
| 3 | source failure handled honestly | `ocean_error_world` → honest failure propagated (live acceptance degrades, no relabel as LIVE); `SOURCE_UNAVAILABLE` path respected | PASS |
| 4 | stale data surfaced | `DATA_STALE` ≡ the SourceHealth `STALE` verdict (freshness window); `test_p2_source_health_stale_versus_available` | PASS |
| 5 | ingestion idempotent | `upsert_many` returns `{inserted, updated, changed}`; `test_p4_repeated_ingestion_idempotent`, `test_p7_unchanged_upsert_not_counted_as_change` | PASS |
| 6 | change detection | `detect_changes` over `CHANGE_SENSITIVE_FIELDS` (geometry/validity/severity/description/type/name/status/cancelled/expired); `test_p7_*` | PASS |
| 7 | freshness enforced | temporal validity of restrictions (expiry → EXPIRED not active); `test_p16_*` | PASS |
| 8 | dynamic restrictions temporally valid | `restriction-expiry-reevaluated`, store `list_active` excludes cancelled/expired | PASS |
| 9 | PostGIS spatial checks work | `RUN_POSTGIS_TESTS=1` `-k "postgis or spatial or hard_constraint"` → 6 passed. The 2 DB-backed integration tests (`test_marine_postgis.py::TestPostGISOcean::test_insert_query_dedup_and_cleanup`, `test_restricted_area_window_status`) require a live PostGIS `DATABASE_URL`; without a provisioned DB they are `skip` in the baseline (no DB available in this environment). Spatial query *logic* checks pass. | PASS (logic) · needs live DB for DB-backed integration |
| 10 | route hard constraints work | active restriction blocks route; `test_p15_active_restriction_blocks_route` | PASS |
| 11 | ML cannot override safety | `test_p20_ml_low_risk_active_restriction_restricted` | PASS |
| 12 | RAG cannot replace live data | `test_p18_rag_permitted_cannot_override_live_restriction` | PASS |
| 13 | prompt injection cannot bypass safety | retained Phase 8 injection checks (still green) | PASS |
| 14 | provenance survives end-to-end | live chain `user → orchestrator → agent → MCP tool → marine service → adapter → source`; replay labels preserved | PASS |
| 15 | structured map/chart/alert outputs | Phase 8 structured outputs retained; `evaluation.live` workflow output verified | PASS |
| 16 | multilingual + multi-turn flows | benchmark classes `multilingual` (ml-IN) and `multiturn` (twoturn) → success | PASS |
| 17 | MCP tool budgets enforced | `tool_budget`/`run_bounds` checks retained green + live acceptance | PASS |
| 18 | benchmark results exist | `reports/bench-latest.md` — 10 classes, avg/P50/P95 per phase, failure rate, tool calls, agent count | PASS |
| 19 | runbook exists | `docs/phase9-operational-runbook.md` | PASS |
| 20 | acceptance report exists | this document | PASS |
| 21 | all existing tests remain green | full `pytest tests` → 278 passed / 2 skipped (the 2 skipped are DB-backed PostGIS tests awaiting a live DB); `-k "postgis or spatial"` logic tests → PASS | PASS |

## CANCELLED lifecycle (Parts 5–6)

- `WarningStatus.CANCELLED = "cancelled"` and `NON_BINDING_STATUSES` added to
  `apps/api/app/models/warnings.py`; `DynamicRestriction.cancelled`
  + `updated_at`; ORM columns + migration
  `f3d2c1b0a9e8_phase9_restriction_lifecycle.py`.
- Transition test `test_p6_lifecycle_transitions`; `test_p5_cancelled_never_active`,
  `test_p16_store_cancelled_not_active`.
- Change detection compares resolved `.status(at)` values (avoids comparing the
  bound method object).

## Benchmark summary (10 classes)

`pfz, marine, safety, restriction, route, knowledge, scenario, multilingual,
multi-turn, degraded-source`. All 10 return `success` at 0.0 failure rate with
`multilingual` detected as `ml-IN`. Latency P95 reflects the offline fixture
world (sub-ms for most paths); live network latency requires live sources.
Agent count and tool-call counts are recorded per class (Part 33 efficiency):
e.g. safety 3 agents / 5 tools, pfz 2 agents / 3 tools.

## Source honesty

Every source in the matrix is `CONFIGURATION_REQUIRED` until a 2xx probe
succeeds. No source row is marked `CONNECTED`, and no fixture is relabeled
`LIVE`. Replays carry `REPLAY / HISTORICAL DEMONSTRATION`.
