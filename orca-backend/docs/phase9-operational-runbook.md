# Phase 9 — Operational Runbook

How to operate and validate the FloatChat (ORCA) platform once it is deployed
with live sources. Every command runs from the repository root.

## 1. Prerequisites

- Python 3.11 + `pip install -r requirements.txt` (API) and `pip install -r
  evaluation/requirements.txt` (harness). On Windows/Python 3.11 use
  `asyncio.run()` — `asyncio.get_event_loop().run_until_complete()` fails there.
- PostgreSQL + PostGIS (optional but recommended) for the production
  restriction/ingestion store. Migrations live in `apps/api/migrations/`.
- `.env` from `.env.example`; set `*_enabled=true` and endpoint credentials for
  each source you intend to connect.

## 2. Source health monitoring

`apps/api/app/services/source_health.py` exposes `SourceHealthMonitor.evaluate`
which returns a verdict distinct from per-record `DataStatus`:

- `HEALTHY` — configured, connected, and the newest record is within its
  freshness window.
- `DEGRADED` — configured + connected, but repeated recent failures.
- `STALE` — configured + connected, but the newest data is older than the
  freshness threshold (do not treat as current).
- `UNAVAILABLE` — not configured, or configured but never succeeded / failed.
- `UNKNOWN` — no signal yet.

Feed it `last_successful_fetch`, `threshold_seconds`, `consecutive_failures`,
and `now` to get an ops-dashboard verdict. Wire it to `/health` or a cron probe
that records per-source `SourceHealth`.

## 3. Idempotent ingestion

Ingestion upserts on the source's natural key. Re-running the same payload
does **not** create duplicates or count as a change:

- `InMemoryDynamicRestrictionStore.upsert_many` / `PgDynamicRestrictionStore.upsert_many`
  return `{"inserted", "updated", "changed"}`.
- `updated` = record exists and differs from the stored copy.
- `changed` = records whose change-sensitive fields actually changed
  (`geometry, valid_from, valid_until, severity, description,
  restriction_type, name, status, cancelled, expired` — see
  `detect_changes` in `apps/api/app/models/dynamic_restrictions.py`).
- Identical payloads return `changed == 0`.

Guarded by tests `test_p4_repeated_ingestion_idempotent` and
`test_p7_unchanged_upsert_not_counted_as_change`.

## 4. Restriction lifecycle

Statuses: `PROPOSED → ACTIVE → CANCELLED/EXPIRED` (see
`WarningStatus` in `apps/api/app/models/warnings.py`; `CANCELLED` and
`NON_BINDING_STATUSES` added in Phase 9).

- Active restrictions are temporally validated — a restriction whose
  `valid_until` has passed is `EXPIRED` and no longer binds
  (`test_p16_restriction_expiry_reevaluated`).
- `cancelled` restrictions are excluded from `list_active`
  (`test_p16_store_cancelled_not_active`).
- `DynamicRestrictionService.refresh` reports `inserted/updated/changed` so an
  ops pipeline can surface signalled changes.
- Route planning hard-blocks when an active restriction intersects the route
  (`test_p15_active_restriction_blocks_route`).

Use `app.restriction_refresh` / `DynamicRestrictionService` to run periodic
refresh from source feeds; the migration
`apps/api/migrations/versions/f3d2c1b0a9e8_phase9_restriction_lifecycle.py`
adds `cancelled` + `updated_at` columns.

## 5. Safety overrides (cannot be weakened by ML or RAG)

- An ML "low risk" verdict never overrides an active live restriction
  (`test_p20_ml_low_risk_active_restriction_restricted`).
- RAG knowledge may describe rules but cannot override live data
  (`test_p18_rag_permitted_cannot_override_live_restriction`).
- Prompt injection cannot bypass the safety layer (see Phase 8 injection
  checks; retained green).

## 6. Validation matrix

Run everything from the repo root:

```powershell
# Unit + integration
$env:PYTHONPATH=".;apps/api"
python -m pytest tests -q

# PostGIS spatial + hard-constraint checks
$env:RUN_POSTGIS_TESTS="1"
python -m pytest tests -q -k "postgis or spatial or hard_constraint"

# Live acceptance (sources + workflows)
$env:RUN_LIVE_ACCEPTANCE="1"
python -m evaluation.live        # reports reports\live-latest.md

# Benchmark (10 classes: pfz, marine, safety, restriction, route,
# knowledge, scenario, multilingual, multi-turn, degraded)
$env:PYTHONIOENCODING="utf-8"
python -m evaluation.benchmark   # reports\bench-latest.md
```

Phase 9 acceptance gates are tracked in `docs/phase9-acceptance-report.md`.

## 7. Honesty of data

- No source is ever relabeled `LIVE` without a 2xx probe (`docs/phase9-source-matrix.md`).
- `SOURCE_UNAVAILABLE` / `DATA_STALE` propagate through Agent → Fusion → Risk →
  Verifier → Response; fixtures are labeled `REPLAY / HISTORICAL DEMONSTRATION`.
