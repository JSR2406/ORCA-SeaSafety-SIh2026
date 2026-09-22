# Phase 14 - End-to-End Acceptance Report

Date: 2026-09-01
Purpose: Document the result of running the entire FloatChat/ORCA platform end-to-end.
Policy: only PASS when actually verified in this run; DB/network-backed capabilities that
cannot execute in this sandbox are reported as UNAVAILABLE / CONFIGURATION_REQUIRED and are
**not** marked PASS. No real integration was replaced with a mock or demo/offline fallback.
The safety hierarchy (LIVE HARD RESTRICTION > RISK ENGINE > ML > RAG > LLM) was preserved.

## 1. Environment

- Host: Windows, PowerShell 5.1, Python 3.11 venv (`apps/api/venv`).
- **No outbound TCP/HTTPS egress** (HTTPS to incois.gov.in, github.com, supabase.com, 1.1.1.1 all time out; ICMP reaches 8.8.8.8).
- **No reachable database**: Supabase `db.qkrwxhoebnrtsmxlfvsx.supabase.co` -> ConnectionRefused (WinError 1225); AAAA-only DNS = project likely paused; no local PostgreSQL; Docker Desktop engine fails to start (WSL2 REGDB_E_CLASSNOTREG).
- Real marine sources (INCOIS) blocked; configure `INCOIS_ENABLED=true` + key once egress exists.
- `DATABASE_URL=postgresql+asyncpg://postgres:***@db.qkrwxhoebnrtsmxlfvsx.supabase.co:5432/postgres` (password masked; user confirmed attempting to enable Supabase, which is unreachable from this sandbox).

## 2. What was executed for real (offline-deterministic, against the actual app)

| Requirement | Result |
|---|---|
| API boots (FastAPI app lifespan + middleware + routers) | PASS - `GET /` 200, api_version 1 |
| Health honesty on DB down | PASS - `/api/v1/health` -> `degraded` / `database.disconnected` |
| Readiness | PASS - `/api/v1/ready` -> `not_ready`, database disconnected, scheduler not_configured |
| API contract | PASS - `/api/v1/contract` 200 (orchestrate, stream_ws, schema v1.0) |
| MCP catalog 33 tools | PASS - 33 descriptors incl. 4 analytics_governance |
| MCP invoke envelope + correlation ids | PASS - `mcp.invoke`/`mcp.invoke_ok`/`mcp.tool_failed` structured logs |
| Orchestrator intent detection | PASS - fishing/safety/knowledge/route/briefing(ml) correctly classified |
| Canonical safety journey | PASS - 5 real MCP tools invoked, intent=safety, verification all_verified=true |
| Safety invariant (no fake SAFE/UNSAFE) | PASS - `risk.classification=UNKNOWN`, reason "Risk could not be assessed from the available data.", hard_constraint=false |
| Degradation explicit | PASS - `limitations` lists unavailable variables/sources |
| Agents strategy | PASS - `notes.strategy=capability_matrix` |
| Full regression suite | PASS - 406 passed, 2 skipped (15.5s) |
| Phase 7 evaluation | PASS - 52/52 (overall 100.0%, safety 100.0%) |
| Live acceptance | PASS - 14 demo workflows, 9 proactive, 6 ML, 12 governance all OK |
| Execution benchmark | PASS - 10 scenario classes + 9 proactive + 6 ML + 12 governance all `success`, 0 failures |

## 3. Component status matrix (only PASS when verified)

| Component | Status | Evidence |
|---|---|---|
| FastAPI runtime / middleware / routers | PASS | boots; health/ready/contract probe responses captured |
| Health / readiness / contract API | PASS | degraded/not_ready under DB-down, contract 200 |
| MCP server (33 tools), invoke, status | PASS | /tools 33; /invoke real tool chain; status errors fail loudly |
| Orchestrator + planner + agents | PASS | intents resolved; capability_matrix; real tool calls |
| Risk engine (safety, no fake SAFE) | PASS | UNKNOWN preserved; not downgraded |
| Verifier | PASS | checked=4, failed_claims=[] |
| Events / alerts / proactive | PASS | 9 proactive + live acceptance OK |
| ML runtime + governance + provenance | PASS | 6 ML + 12 governance cases OK; 7 /api/v1/ml routes |
| Multilingual (ml-IN etc.) | PASS | multilingual-query success in benchmark; ML language = ml-IN |
| Multi-turn | PASS | multi-turn-query success in benchmark |
| Observability (correlation ids, duration) | PASS | req-/orch- request_ids, invoke_ok, access duration_ms in logs |
| Failure injection / graceful degradation | PASS | health degraded, readiness not_ready, source_status DEPENDENCY_FAILURE, RAG degrades empty+FTS note |
| PostgreSQL / migrations | UNAVAILABLE | no reachable DB; 7 Alembic heads present, cannot run |
| PostGIS spatial queries | UNAVAILABLE | no DB |
| pgvector vector queries | UNAVAILABLE | no DB |
| Live marine ingestion (INCOIS/IMD/MOSDAC) | CONFIGURATION_REQUIRED | `*_ENABLED=false` in default env; egress blocked |
| Hybrid RAG embedding path | CONFIGURATION_REQUIRED | embedder NotConfigured (no EMBEDDINGS key); FTS-only note when no embedding provider |
| LLM STT/TTS/translation | CONFIGURATION_REQUIRED | keys absent; no egress |
| Frontend (Next.js) | PASS (code-level) | API-wrapper only, no direct DB/source access; :3000 |

## 4. Known limitations (honest, not PASS)

1. **DB execution could not be performed** in this sandbox (no egress / local PG / Docker / reachable Supabase). All database, PostGIS, and pgvector acceptance items remain unverified at runtime; the audit marks them UNAVAILABLE with connection-refused evidence, pending a reachable environment.
2. `knowledge.source_status` returns **400 DEPENDENCY_FAILURE** (loud, honest) rather than a 503 "DB unavailable"; recommended future improvement.
3. Offline `knowledge.search` returns `fts_only` with empty chunk rows (exception swallowed in `app/services/knowledge_rag.py:226`); operators should not read offline empty FTS as real retrieval.
4. Live source freshest/threshold behavior is code-verified but not data-verified (no real source data).

## 5. Definition of Done (Phase 14) checklist

- [x] Runtime audit written (`docs/phase14-runtime-audit.md`) with component status matrix.
- [x] Environment validation: `.env` git-ignored, `.env.example` tracked with placeholders, no secrets committed, required categories documented.
- [x] Source health honesty: `source_catalog` reports configured capability; `source_status` fails loudly (DEPENDENCY_FAILURE) rather than faking LIVE.
- [x] Safety invariants preserved: high PFZ + active restricted zone must return RESTRICTED/UNSAFE, never SAFE; UNAVAILABLE never silently converted to SAFE (verified: risk stays UNKNOWN).
- [x] All offline-deterministic requirements executed and passed (API, MCP, agents, orchestrator, journeys, safety-critical, restrictions, multilingual, multi-turn, ML governance, proactive events, alerts, observability, failure injection).
- [x] Full test suite passed initially (406 pass / 2 skipped; Phase 7 eval 52/52; live acceptance all OK; benchmark all success); refreshed below to 415 pass after Phase 14 additions.
- [x] No real integration replaced with a mock; no demo/offline fallback mislabeled as live.
- [x] DB/PostGIS/pgvector runtime execution — **validated live** in the follow-up (2026-09-02) once the Supabase DB became reachable.
- [ ] Live government-source ingestion (single real fetch) — **NOT COMPLETED** (awaits government API key approval; `*_ENABLED=false`).

### 5.1 Phase 14 follow-up (2026-09-02): DB reachable + TEST-MOCK + ARGO + voice

The boundary state changed after the initial report: the Supabase DB became reachable and the
DB-backed items were verified live, and the code-only work fronts were advanced. See
`docs/phase14-runtime-audit.md` section 5 for full, cumulative evidence. Summary:

- **DB / migrations / PostGIS / pgvector now PASS (live).** pgvector `0.8.2` installed; `alembic
  upgrade head` -> `f3d2c1b0a9e8`; 29 model tables present; `ST_Distance` verified; `embedding`
  type `vector(1536)`; cosine distance verified.
- **TEST-MOCK sample marine source added (evaluation only).** `MockMarineDataSource` emits
  deterministic sample data gated by `MOCK_*_ENABLED` (default off), is hard-labelled
  `TEST_MOCK` (never `LIVE`) at both per-source and per-result status. Verified live:
  all six products ingest and read back with `result_status=test_mock` while real
  INCOIS/IMD/MOSDAC remain `not_configured`. This is **sample/demo data**, not real
  government-source ingestion.
- **ARGO wired for ingestion + tools.** `argo_repository`, `argo_persist` (Dataset->rows),
  `ArgoService`, and 4 `argo.*` MCP tools; MCP catalog now 37 tools. Live GDAC fetch still needs
  egress -> `CONFIGURATION_REQUIRED`.
- **Voice STT/TTS/translation bodies implemented** (real `httpx` calls for Sarvam STT/TTS,
  ElevenLabs TTS, Google translate). Requires keys; absent key -> `ValueError` at construction
  -> `CONFIGURATION_REQUIRED`, never a fake local synthesis.
- **Fix:** `MarineValidationService.classify_warning` added + wired into the pipeline, fixing a
  latent `KeyError('warnings')` that blocked warnings ingestion.
- **Suites after additions:** `pytest tests` -> **415 passed, 2 skipped** (+9 new unit tests);
  `python -m evaluation` -> **52/52** (overall 100%, safety 100%).

**DoD deltas from this follow-up:**
- [x] DB / PostGIS / pgvector runtime execution — **now PASS (live)** on the reachable Supabase DB.
- [x] Pipeline exercised end-to-end with a real DB — **via clearly-labelled TEST-MOCK sample data**
  (not fabricated as live; the mock status invariant was verified).
- [ ] Live government-source ingestion (single real INCOIS/IMD/MOSDAC fetch) — **still NOT
  COMPLETED** (awaits government API key approval + reachable egress). ARGO GDAC live fetch and
  live voice/LLM calls likewise remain `CONFIGURATION_REQUIRED` until keys/egress exist.

## 6. Recommended next step to complete remaining checks

The DB/PostGIS/pgvector row is now **PASS** (verified live on the reachable Supabase DB;
see section 5.1). The only remaining checks are the live data-plane integrations:

1. Obtain real government API keys (INCOIS, IMD, MOSDAC) and set `INCOIS_ENABLED/IMD_ENABLED/
   MOSDAC_ENABLED=true` with keys — this moves live marine-source ingestion to PASS
   (currently `CONFIGURATION_REQUIRED`).
2. Ensure runtime network egress and set `LLM_API_KEY` / `EMBEDDINGS_API_KEY` /
   `STT_API_KEY` / `TTS_API_KEY` / `TRANSLATION_API_KEY` for live LLM/embedding/voice calls.
3. ARGO GDAC fetch (`argo.ingest_region/float`) needs reachable egress to the GDAC; until
   then ARGO remains `CONFIGURATION_REQUIRED` (reads work once rows are persisted).
4. Re-run `python -m evaluation.benchmark`, `python -m evaluation.live`, and `pytest` after
   enabling any of these to confirm the newly-live rows move to PASS with evidence.