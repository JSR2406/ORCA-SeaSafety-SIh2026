# Phase 5 Architecture Report - Production Marine Intelligence + Safety + Geospatial Execution

Phase 5 layers production marine intel, deterministic safety and geospatial
execution on top of the Phase 4 orchestrator - it does not rebuild it. The MCP
tool layer remains the capability boundary, LLMs only plan/synthesize, and every
safety-critical decision is made by deterministic, verifier-traced code.

Pipeline (unchanged): **Message -> Intent -> Plan -> Validate -> Execute (DAG)
-> Verify -> Synthesize**, now extended with nearest-PFZ, trans-RESTRICTED
safe-route scoring, live dynamic restrictions, static geofences, fisheries
productivity and map/chart/alert outputs.

## 1. Data contracts (`app/models/`)

| Module | Responsibility |
|---|---|
| `marine_contract.py` | `MarineObservation` + `DataClass` (observation/forecast/advisory/model_prediction) + `DataFreshness` (FRESH/AGING/STALE/EXPIRED/UNKNOWN) |
| `dynamic_restrictions.py` | `DynamicRestriction` (natural key (source, source_record_id), `distance_to()`, `status(at)`) |
| `db/models.py` | `DynamicRestriction` ORM: geometry via `geoalchemy2.Geometry` (PostGIS) or `Text` fallback, `postgresql_nulls_not_distinct` unique constraint |
| `orchestration/models.py` | `IntentName.PFZ` / `IntentName.PRODUCTIVITY`, Intent `offset`/`route` fields |

Migration head is unchanged (`1a2b3c4d5e6f`); new migration
`c5a7e9f1b2d3_dynamic_restrictions` (down_revision `1a2b3c4d5e6f`) follows the
existing style: `_is_postgresql()` guard, gist spatial index only under PostGIS.

## 2. Dynamic restrictions (official, time-boxed, self-expiring)

| Module | Responsibility |
|---|---|
| `services/dynamic_restriction_store.py` | Store seam: idempotent upsert, active-window listing, `expire_unrefreshed` |
| `services/restriction_refresh.py` | `RestrictionSourceAdapter` protocol; `NavareaAdvisoryAdapter` + `TemporaryClosureAdapter` feeds; `DynamicRestrictionService` (refresh / `active_at` / `active_near_route` / `static_geofence_hits` / `list_active`) |
| `services/geofence_catalog.py` | Static geofences (EEZ, IMBL, MPA, marine boundary) + `hits()` |
| `services/pg_dynamic_store.py` | Postgres store (ST_ ops for distance), `InMemoryDynamicRestrictionStore` for tests/demos |

Rules: a restriction is ACTIVE only inside `[valid_from, valid_until)` **and**
not expired; a source that stops refreshing has its records expired within the
grace window, so expired restrictions never linger in the active view;
official `expire_unrefreshed` is called on every refresh.

## 3. Safety-critical evaluation

| Module | Responsibility |
|---|---|
| `services/route_evaluator.py` | `RouteIntersection`/`RouteEvaluation`, `route_length_km`, transparent `ROUTE_SCORE`; **a hard geospatial constraint forces `blocked=True, score=0`** regardless of favourable scores |
| `services/risk_engine.py` | Composite `assess()`; levels RESTRICTED / UNKNOWN / CRITICAL / HIGH_RISK / CAUTION / SAFE; **RESTRICTED is authoritative - no score may downgrade it**; UNKNOWN when mandatory evidence is missing (never guesses) |
| `mcp/tools_restriction.py` | `restriction.dynamic_active`: refreshes the service per call, returns `active_dynamic` + `static_geofence_hits` + `restricted` flag |
| `mcp/tools_marine.py` | `marine.pfz_nearest`: deterministic rank of advisory zones by distance with `distance_km`/`inside` |

The ML/prediction layer never enforces safety: `analytics.fishing_potential`
and `analytics.productivity` (satellite-inferred) are advisory only and carry
an explicit caveat.

## 4. Analytics + evidence

| Module | Responsibility |
|---|---|
| `services/analytics.py` | `fishing_potential` with `_potential_label`, `rank_candidates`, `productivity` with `PRODUCTIVITY_BANDS`; missing inputs -> `None`, never a guess |
| `services/marine_fusion.py` | Per-source `freshness` on `FusedMarineState` (`_compute_freshness`, `evaluate_freshness`) |
| `services/freshness.py` | FRESH/AGING/STALE thresholds, EXPIRED/UNKNOWN window handling |
| `services/evidence_graph.py` | `EvidenceNode`/`EvidenceGraph`: numeric claims with source + freshness, merged nodes/sources |
| `mcp/tools_decision.py` | `analytics.fishing_potential`, `analytics.productivity` (+ shared `_state_from_payload`) |

## 5. Orchestrator extensions (additive to Phase 4)

| Module | Change |
|---|---|
| `intent.py` | PFZ/PRODUCTIVITY keywords; tie-break order KNOWLEDGE(4) < PFZ(5) < BRIEFING(6) < PRODUCTIVITY(7) so "What are the PFZ rules?" stays KNOWLEDGE; `_parse_offset`/`_apply_offset` for "20 km south of Mumbai"; `from X to Y` waypoints |
| `agents.py` | `pfz_intelligence`, `productivity_intelligence` specs; `restriction.dynamic_active` wired into `maritime_safety`/`route_intelligence` handlers (non-fatal if unavailable); new handlers |
| `planner.py` | PFZ/PRODUCTIVITY capabilities mapped to `marine.pfz_nearest`/`analytics.productivity` tools |
| `executor.py` | unchanged - new handlers run through the existing DAG/verifier path |
| `synthesis.py` | Response keys `outputs` (maps/charts/alerts), `evidence_graph` (verified numeric claims), `freshness`; PFZ/PRODUCTIVITY branches; deeper claim collection |
| `orchestrator.py` | Phase timings `intent_ms`/`plan_ms`/`execute_ms`/`synthesize_ms` in `notes` + `phase_metrics` tracer event |

End-to-end PFZ turn: `find the nearest PFZ near Goa` -> PFZ intent with offset
support -> `pfz_intelligence` (nearest zone) -> zone-state + satellite
potential -> fusion freshness -> evidence graph -> map + chart outputs.

## 6. Response contract additions

Phase 4 fields are unchanged. New keys on `200`:

- `outputs`: `{maps: [], charts: [], alerts: []}` - machine-consumable artifacts
  derived only from evidence.
- `evidence_graph`: `{nodes: [], sources: []}` - every numeric claim traced to a
  tool output; best-effort and never fatal.
- `freshness`: `{overall, threshold_seconds, per_source}` from the fused state.
- `notes.phase_timings`: `{intent_ms, plan_ms, execute_ms, synthesize_ms}`.

## 7. Tests

`tests/test_phase5.py` (26 tests) is DB/network-free. Coverage: freshness
labels + window classes; idempotent dynamic refresh; geometry-filtered
`active_at`; source-drop expiry (expired restrictions never linger); static
geofence hits; RESTRICTED/UNKNOWN/SAFE/CAUTION assess() levels; the hard
constraint over-riding a favourable ROUTE_SCORE; fishing potential +
productivity (incl. missing-input honesty); evidence graph claims/sources;
PFZ/PRODUCTIVITY intent classification and offset parsing; full PFZ
orchestration through a fake registry with map/chart/evidence-graph outputs;
phase timing surface.

**Regression:** `python -m pytest tests -q` = **220 passed, 2 skipped**
(Phase 4 baseline 194; +20 MCP tool/build wiring, +26 Phase 5 tests).
PostGIS/`RUN_POSTGIS_TESTS` tests remain environment-skipped; the
`test_canonical_hash_stable` order-flake is pre-existing and passes in isolation.

## 8. Compliance matrix

| Guardrail | Where enforced |
|---|---|
| Hard constraints override optimization scores | `route_evaluator.evaluate_route` forces `blocked=True, score=0`; `risk_engine.assess` never downgrades RESTRICTED |
| No fabricated data | analytics return `None` on missing inputs; freshness `UNKNOWN` when undeterminable |
| Expired restrictions never active | `expire_unrefreshed` on every refresh; `status(at)` window check in both stores |
| ML predicts, never enforces safety | satellite potential is advisory, caveated; risk/route use only deterministic evidence |
| Safety-critical code stays deterministic | all new evaluation is pure Python services, unit-tested |
| MCP remains the capability boundary | new tools are registered on `ToolRegistry`; agents call only via `ToolBus` |
| Phase 4 intact | all Phase 5 changes are additive; 32 orchestration tests still green |