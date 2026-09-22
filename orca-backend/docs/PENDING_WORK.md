# Pending Work — FloatChat Backend + Frontend Integration

> Source of truth for the remaining fixes after the deployment-readiness audit (2026-09-06).
> Test suite: **468 passed / 2 skipped / 0 failed** (after fixes; baseline 446 / 2 / 0).
> Run from repo root: `$env:PYTHONPATH=resolve-path "apps/api"; python -m pytest tests/`

---

## 1. Backend — Orchestration Contract (HIGH) ✅ DONE

- ✅ `apps/api/app/contracts/orchestration.py`: optional `message`, `conversation_id`; `model_validator` requires `query` or `message` → `400 INVALID_REQUEST` otherwise
- ✅ Router resolution: `query or message`, `session_id or conversation_id`; `user_location` threaded `_run → orchestrator.run → _parse → IntentParser.parse` with priority **message coords → user_location → context resolved_location** (label `user location (SOURCE)`, merged location set)
- ✅ WS first-frame JSON protocol in `routers/orchestrate.py` `/stream`: first `receive_text()` parsed for `message/query`, `conversation_id/session_id`, `request_id`, `user_location`, `language`, `requested_outputs`, `route_request`, `scenario_request`; honest `execution.failed` with `receive_failed` / `invalid_json_frame` / `empty_message` / `message_too_long`
- ✅ `orchestration/stream.py`: `stream_orchestration` accepts + forwards `user_location`

## 2. Backend — Router Fixes (MEDIUM) ✅ DONE

| Endpoint | Fix |
|---|---|
| `GET /health` | Root alias in `app/main.py` → `/api/v1/health` (uses `async with get_session()`) |
| `POST /api/v1/chat` | `status:"unavailable"` when `get_query_planner()` raises (no LLM key); `ChatResponse` schema: `structured_query`/`evidence` Optional, `status` includes `"unavailable"` |
| `GET /api/v1/voice/providers` | Providers never raise on missing key (`_configured` flag); router calls with no key → `503`; `/providers` → 200 |
| `POST /api/v1/risk/briefing` | `origin` optional + flat `latitude`/`longitude` fallback (≥1 required) |
| `POST /api/v1/query/plan` / `/execute` | New `routers/query.py` shims wrapping `get_orchestrator_service()`; plan returns intent fields, route, scenario, needs |
| `POST /api/v1/scenarios/project` | Alias route → `/api/v1/scenarios/create` |
| `GET /api/v1/knowledge/status` | Probe `pg_extension` for `vector` first, then `pg_available_extensions` |

**Voice provider detail:** `SarvamSTT/TTS`, `ElevenLabsTTS`, `GoogleTranslation` constructors store `_configured = bool(key)` instead of raising; `get_status()` reports `configured / not_configured`; `get_voice_factory` registers all providers; endpoint calls without a key return 503. Existing unit tests updated (old tests asserted the raise; new behavior is degrade).

## 3. Frontend Alignment (HIGH) ✅ DONE

- ✅ `apps/web/src/lib/api-client.ts`: `health()` → `/api/v1/health` (dropped `demo_mode`); `projectScenario` → `/api/v1/scenarios/create`
- ✅ `packages/shared-types/src/phase6.ts`: canonical `OrchestrateRequest {query, session_id, user_location?, requested_outputs?, ...}` + optional legacy `message?` / `conversation_id?`; `RiskPayload.classification` replaces `level`
- ✅ `apps/web/src/components/chat/ChatInterface.tsx`: canonical payload, `user_location` via `getCachedPosition()`, reads `risk.classification || risk.level`; types clean for these files (`tsc --noEmit` still reports pre-existing errors in CommandCenterDashboard/EvidenceCard/FloatMap/MapLayers/shared-types index — not from this batch)

## 4. Documentation (LOW) ✅ DONE

- ✅ `docs/deployment-architecture.md` **Frontend Deployment** section: `NEXT_PUBLIC_API_URL`, `CORS_ORIGINS` must include the deployed frontend origin, healthcheck note, optional voice keys → feature flags
- ✅ `apps/web/BACKEND_INTEGRATION.md` (authoritative frontend↔backend reference)

## 5. Tests (HIGH) ✅ DONE

- ✅ `tests/test_contract_fixes.py` (~22 tests): aliases, user_location threading, WS first-frame (+ invalid/empty/oversized frames), `/health`, chat degrade, voice providers 503 + `/providers` shape, risk briefing origin fallback, query plan/execute (incl. INVALID_REQUEST body), scenarios/project alias, knowledge pgvector probe
- ✅ Updated `tests/test_unit.py` voice provider tests to assert degrade (not raise)
- ⚠️ Full-suite order note: tests that boot the app must use bare `TestClient(app)` (no `with`) like the rest of the repo. `with TestClient` triggers lifespan → `bind_alert_state` leaves a stale module-level alert repo binding that makes `test_phase11_alerts_api` list/get inconsistent when the module runs *before* it. Bare client avoids booting the proactive scheduler (also ~5× faster). This is a latent leak in `routers/alerts.py` `_app_state` (pre-existing; not in scope to refactor now).

---

## Done / Verified (Do Not Revisit)

- ✅ Ledger + feature-store persistence (`data/ml/ledger.json`, `feature_store.json`)
- ✅ Retention bug fix: `total_seconds()` in `features.py`
- ✅ Governance default load + persist on mutations
- ✅ Service persists features on location put
- ✅ 8 persistence tests in `tests/test_ml_persistence.py`
- ✅ Supabase Postgres live (PG 17.6, PostGIS 3.3.7, pgvector 0.8.2)
- ✅ `/api/v1/contract`, `/api/v1/health`, `/api/v1/ready` → 200
- ✅ `POST /api/v1/orchestrate` (canonical payload) → 200, `marine_evidence` INSERT live
- ✅ ML dashboard: pfz 1.1.0 (n=2000), 39 MCP tools
- ✅ Knowledge: 8 docs, 1829 chunks, 0 embedded (no embeddings key)
- ✅ CORS allowlist: `http://localhost:3000`
- ✅ `apps/web/BACKEND_INTEGRATION.md` written
- ✅ Items 1–5 above (full list from this audit), verified by `tests/test_contract_fixes.py` + full suite = **468 passed / 2 skipped / 0 failed**

---

## Not In This Batch (out of scope / deferred)

- Pre-existing frontend `tsc --noEmit` errors in `CommandCenterDashboard.tsx`, `EvidenceCard.tsx`, `FloatMap.tsx`, `MapLayers.tsx`, `shared-types` barrel export ambiguity — not touched by the alignment batch.
- `routers/alerts.py` module-level `_app_state` stale-binding leak on repeated app boots (latent; surfaced in test ordering only).

---

## Execution Order

1. **Backend contract + location threading** (items 1.1, 1.2) — unblocks the single UI call
2. **WS first-frame** (1.3) — parallel, same code area
3. **Router quick wins** (2: health, chat, voice, risk, scenarios) — independent
4. **Query shims + knowledge pgvector** (2) — new router + probe fix
5. **Frontend types + api-client + ChatInterface** (3) — matches 1–4
6. **Docs** (4)
7. **Tests** (5) + full suite re-run

---

## Notes

- Run all commands from **repo root** with `$env:PYTHONPATH=resolve-path "apps/api"` so the root `.env` (Supabase) is loaded.
- Single unified `.env` at repo root (merged from the old `apps/api/.env` OpenWeather block on 2026-09-07). `config.py` loads it by absolute path, so CWD does not matter anymore; `apps/api/.env` no longer exists.
- The frontend makes exactly **one** backend call: `ChatInterface.tsx:174 api.orchestrate(...)`. All other `api.*` functions are wired but currently unused.
- ML never overrides RiskEngine; only VALIDATED ground truth enters training.