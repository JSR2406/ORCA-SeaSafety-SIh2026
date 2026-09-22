# Phase 6 Architecture Report - Operational Intelligence Experience

Phase 6 turns the Phase 4/5 backend into a complete operational experience:
one verified execution runs the whole answer, and the response carries the
chat text *and* the machine-consumable maps, charts and alerts plus a live
execution stream and persistent multi-turn memory.  Nothing is recomputed from
user text a second time, and there is no second orchestration system or
database: `outputs` are derived only from the same evidence synthesis already
rendered, in **one** language frame (requirement #36).

Pipeline (unchanged): **Message -> Intent (multi-turn-aware) -> Plan ->
Validate -> Execute (DAG) -> Verify -> Synthesize**, now producing the Phase 6
response frame and streaming the run live over WebSocket.

## 1. Response contract (`200` on `/api/v1/orchestrate`)

Phase 4/5 keys are unchanged. New top-level keys:

| Key | Type | Meaning |
|---|---|---|
| `answer` | string | chat answer (mirrors `message`) |
| `confidence` | object | deterministic `{score, label, basis}` |
| `risk` | object | `{level, hard_constraint, assessed}` from the Risk Engine |
| `outputs` | object | `{maps, charts, alerts, route}` - one source of truth |
| `evidence` | list | verified claim summary `{claim, source}` |
| `provenance` | object | `{generated_at, sources, freshness, verification, dynamic_layer}` |
| `limitations` | list | explicit caveats (missing variables, stale data, unassessed risk) |
| `phase_timings` | object | mirror of `notes.phase_timings` (`intent/plan/execute/synthesize_ms`) |

`confidence` is fully deterministic (`synthesis._compute_confidence`): base
1.0, minus verifier/evidence/failure penalties and a freshness penalty per
`fresh|recent|aging|stale|unknown|expired`, clamped to `[0.05, 0.98]`.  It is
never LLM-assigned.

`outputs` shape:

- `maps`: GeoJSON `FeatureCollection` (`map_payload.py`) - query point, risk
  point, PFZ zone, safety geofence, route line/waypoints.
- `charts`: observation + model_prediction series, every point
  `{timestamp, value, unit, source, status}` (`chart_payload.py`); a chart is
  only emitted for a variable the tools actually returned.
- `alerts`: `alert_model.py` - `{alert_id, type, severity, title, message,
  location, geometry, valid_from, valid_until, source, status, evidence}`.
  Severity comes from deterministic warning/risk mapping (never the LLM,
  requirement #41); ids are stable SHA-1 hex so the same source record always
  dedupes to one alert (`stable_alert_id` / `dedupe_alerts`, #42/#43); time
  windows classify ACTIVE / UPCOMING / EXPIRED so an expired window can never
  render active (#43).
- `route`: `{kind, waypoints, status, risk_score, recommended, length_km,
  intersections, basis}` from the Phase 5 `route_evaluator` (hard constraint
  => `blocked`, score 1.0).

## 2. WebSocket execution stream (`/api/v1/orchestrate/stream`)

`orchestration/stream.py` maps internal trace events onto a sanitized public
vocabulary (`EVENT_NAMES`) via `StreamTracer`; each record is the safe set
`{event, request_id, conversation_id, plan_id, task_id, timestamp, status,
data}` where `data` is a per-kind whitelist (`_safe_payload`):

```
execution.started -> intent.detected -> plan.created
  -> task.started -> tool.started -> tool.completed -> task.completed   (xN)
  -> verification.started -> verification.completed
  -> execution.completed -> execution.timings -> response.ready
```

- Evidence payloads, tool arguments, error text and any hidden LLM reasoning
  are never streamed (requirement #49).
- `execution.needs_input` / `execution.rejected` fire for the clarification
  and validation paths; `execution.failed` (empty `data`) covers aborts.
- The router sink swallows send errors and sets a `disconnected` flag so a
  dropped socket never aborts the run; the empty-message edge case emits
  `execution.failed {reason: empty_message}`.

## 3. Persistent multi-turn context (`orchestration/context.py`)

`StoredContext` now carries `resolved_location`, `language`, **`resolved_time`**
and **`last_intent`** plus the message `history` (bounded, capped at 40 turns).

- `InMemoryContextRepository` - tests and single-process dev; now also records
  `update_time`/`update_intent`.
- `PgContextRepository` - production store on the `conversation_contexts` row,
  using `app.db.client.get_session()`; every DB operation falls back to the
  in-memory mirror on any database error so a live turn is never lost to a
  connectivity blip (requirement #45).  The `history` JSON column is the new
  migration `e9a8f7c6b5d4` (down_revision `c5a7e9f1b2d3`).

`_record_turn` writes the turn, resolved location, language, resolved time
(`{label, at}`) and the last intent on every completed run.

## 4. Multi-turn intent (`orchestration/intent.py`)

- **Bare offsets**: `"20 km south."` with no anchor resolves against the
  context location *after* the context merge, so `20 km south of Kochi coast`
  anchors correctly (offset application was moved after merge so a bare
  follow-up can anchor).
- **Operation inheritance**: a turn with zero intent keywords is BRIEFING as
  before, but when the conversation's `last_intent` is an operational intent
  (safety/fishing/route/scenario/pfz/productivity) the turn inherits it, so
  *"what about there?"* stays a fishing question.
- **Resolved-time merge**: an explicit time word wins; a bare follow-up
  inherits the last resolved `time` label (e.g. a follow-up after a
  "tomorrow" question stays on tomorrow).
- Language detection extended to **te-IN** (Telugu) and **kn-IN** (Kannada);
  Marathi shares Devanagari with Hindi (detected hi-IN).

## 5. Multilingual (requirement #21)

`services/localization.py` is a deterministic phrase catalog for en-IN, hi-IN,
ml-IN, ta-IN, te-IN, kn-IN, mr-IN. `localize_response` post-passes the fixed
operational frame: known section titles, line templates and cataloged alert
titles.  Numbers, units, source ids and timestamps are never translated and
en-IN passes through unchanged (existing English assertions stay green).
Charts/alerts pick their titles via `t(language, key)` at build time.

## 6. Dynamic restrictions enrichment (`mcp/tools_restriction.py`)

`restriction.dynamic_active` per-item adds `geometry` (GeoJSON),
`valid_from`, `issued_at` and `refreshed_at` alongside `valid_until`, so the
frontend can render restriction shapes and validity windows directly (WS5).

## 7. Tests

`tests/test_phase6.py` (20 tests) is DB/network-free and repeats the Phase 4
style FakeRegistry. Coverage: contract keys on success / `needs_input` /
validation-failure paths; `phase_timings` mirror both places; GeoJSON maps
(query/risk points); chart series shape; route object; alert id determinism
+ dedupe; ACTIVE/EXPIRED/UPCOMING window classification; warnings -> risk
alert severity; stream event order + sanitization (no arguments/reasoning/
evidence in payloads); bare-offset anchoring on context; operation
inheritance; resolved-time inheritance; fresh per-turn evidence;
hi-IN localization of answer/sections/alerts.

**Regression:** `python -m pytest tests -q` = **240 passed, 2 skipped**
(Phase 5 baseline 220; +20 Phase 6 tests).  PostGIS / `RUN_POSTGIS_TESTS`
and the pre-existing `test_canonical_hash_stable` order-flake behave as before.
A PG-backed context test is environment-gated behind the PostGIS flag.

## 8. Compliance matrix

| Guardrail | Where enforced |
|---|---|
| Never rebuild Phases 1-5 | all Phase 6 changes are additive; `/api/v1/orchestrate`, `/api/v1/mcp/*` untouched; 220 prior tests still green |
| Single source of truth (#36) | `outputs` built in `synthesis._outputs` from execution evidence only; no second orchestration system or DB |
| Chat/map/chart/alert from one result | `answer` == `message`; `sections`, `outputs`, `evidence`, `alerts` all derive from the same executed evidence |
| Safety requires Risk Engine + Verifier | synthesis never prints SAFE without verified risk assessment; UNKNOWN/UNABLE paths say "do not assume a safe condition" |
| Deterministic severity (#41) | `severity_from_warning` / `severity_from_risk` maps; hard constraint => CRITICAL; never LLM-scored |
| Stable alert ids + dedupe (#42) | `stable_alert_id` (SHA-1), `dedupe_alerts` keeps first; route/dynamic/quality alerts included |
| Expired never active (#43) | `classify_status` window check on every alert; expired windows render EXPIRED |
| Context survives (#45) | PG store with in-memory fallback; DB outage never fails a turn |
| No secrets/reasoning in stream (#49) | `_safe_payload` whitelist; evidence/args/error text dropped before emit |
| Offline-first (`RUN_POSTGIS_TESTS`) | env-gated PG tests skipped; DB-free CI kept green |