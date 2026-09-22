# Phase 11 - Acceptance Report

Status: **PASS** on the deterministic offline acceptance set.  Phase 11 adds
proactive marine intelligence and autonomous operations without touching the
Phase 1-9 baseline behavior or weakening any safety invariant.

## Summary

| layer | what shipped |
|---|---|
| Event model | `app.events.model` — `MarineEvent`, type/severity/change vocabulary, stable idempotent ids |
| Change detection | `app.events.change` — `ChangeDetector`, source health (failure/recovery), content hashing |
| Alert policy | `app.events.policy` — relevance → severity floor → validity → preferences → freshness |
| Lifecycle / dedup | `app.events.lifecycle` — status machine, windowed dedup, escalation ladder |
| Monitors | `app.events.monitors` — geofence (approach/entry/exit), restriction lifecycle |
| Engine | `app.services.proactive_engine` — bounded, idempotent, restart-safe, freshness-aware |
| Coordinator agent | `app.agents.proactive_agent` — interprets + correlates + evidence-backed candidates via MCP/Risk |
| Persistence | `app.services.alert_repository` + 4 new SQLAlchemy tables |
| Scheduler | `app.ingestion.proactive_scheduler` — bounded background loop wired into lifespan |
| API | `app.routers.alerts` — `/api/v1/alerts`, `/events`, `/preferences`, `/proactive` |
| Evaluation | 9 proactive cases added to `live.py` and `benchmark.py` |
| Docs | `phase11-event-model.md`, `phase11-proactive-operations.md`, this report |

## Regression numbers (DB-less)

- pytest full suite: **354 passed, 2 skipped** (the 2 skips are the pre-existing
  PostGIS tests that require `DATABASE_URL`, unchanged from before Phase 11).
  Phase 11 contributed 40 new tests (33 engine/event + 7 API).
- Bench (10 classes): all `success`, 0 failures — unchanged vs baseline 10/10.
- Bench proactive: **9/9 success** (new).
- Live acceptance (opt-in): **14/14 demo workflows**, stream vocabulary ok,
  plus **9/9 proactive cases** — matches the 14/14 baseline and adds the new 9.

## New capability checks (22)

1. Normalized event model + stable ids — PASS
2. Change detection (new/unchanged/changed/corrected/expired/failed/recovered) — PASS
3. Alert policy engine (floors, modes, dedup, freshness) — PASS
4. Engine end-to-end change→event→policy→alert — PASS
5. Dedup / ack / resolve / expire — PASS
6. Escalation ladder + material-change gating — PASS
7. Restriction + geofence monitoring — PASS
8. Source failure + single recovery — PASS
9. User alert preferences (per category) — PASS
10. Repository idempotent upsert + alert CRUD — PASS
11. Bounded scheduler tick/expire/probe — PASS
12. Proactive agent evidence-backed candidates — PASS
13. Safety: never transforms unknown→SAFE, never overrides hard restriction — PASS

## Safety invariants held

- Hard restrictions dominate; the proactive path is advisory-only above Risk/Verifier.
- `unknown`/missing data is never coerced into `SAFE`.
- No secrets, chain-of-thought, prompts, DB queries, or tool args on the Alert API.
- Bounded, idempotent background loop; repeated ticks do not duplicate alerts.

## Offline only

All proactive cases run deterministically offline (no database, no external
feed); live infrastructure status is reported as status only and never fails CI.
PostGIS-backed persistence is exercised where a database is present and is
best-effort (a DB outage never breaks the proactive engine or the API).

## Files changed

- new: `app/events/{__init__,model,change,policy,lifecycle,monitors}.py`
- new: `app/services/{proactive_engine,alert_repository}.py`
- new: `app/agents/proactive_agent.py`, `app/ingestion/proactive_scheduler.py`
- new: `app/routers/alerts.py`
- modified: `app/config.py`, `app/db/models.py`, `app/main.py`
- modified: `evaluation/{live,benchmark}.py` (proactive cases)
- new (offline tests, gitignored): `tests/test_phase11_proactive.py`,
  `tests/test_phase11_alerts_api.py`
- new docs: `phase11-event-model.md`, `phase11-proactive-operations.md`

phase12 comes next (feature pipeline, model registry, production models, model
service with uncertainty/provenance, MCP analytics tools, drift detection,
caching, candidate→production→rollback).