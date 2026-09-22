# Phase 14 - Runtime Audit

Date: 2026-09-01
Scope: End-to-end integration and runtime execution audit against the real repository.
Rules: No mocks/demo fallbacks claimed as live; only mark PASS when actually verified;
failures and dependency gaps are reported explicitly, never silently converted to SAFE/PASS.

## 0. Environment reality (verified, affects all DB/network rows)

| Check | Result | Evidence |
|---|---|---|
| Network egress (HTTPS/TCP 443) | **BLOCKED** | `httpx.get('https://incois.gov.in')` -> `ConnectTimeout`; `Invoke-WebRequest https://github.com` -> timeout; `https://1.1.1.1`, `https://api.supabase.com` -> timeout |
| ICMP reachability | Works | `Test-Connection 8.8.8.8` -> True (TCP egress specifically firewalled; NO_PROXY set, no HTTP(S)_PROXY) |
| Supabase DB host | **UNREACHABLE / likely paused** | `db.qkrwxhoebnrtsmxlfvsx.supabase.co` resolves to AAAA only (no A record); asyncpg -> `ConnectionRefusedError [WinError 1225]` |
| Supabase API / reactivation | **UNREACHABLE** | `https://qkrwxhoebnrtsmxlfvsx.supabase.co` and `https://api.supabase.com/v1/` -> timeout (no egress to reach management API) |
| Local PostgreSQL | **NOT INSTALLED** | no `psql`/`pg_isready`; no `C:\Program Files\PostgreSQL`; localhost:5432 closed |
| Docker Desktop engine | **BROKEN** | daemon fails: `failed to connect ... dockerDesktopLinuxEngine`; WSL2 `Class not registered / REGDB_E_CLASSNOTREG` -> WSL2 backend cannot start |
| Alternate local DB path | **CLOSED** | `winget` needs egress to download a Postgres installer -> blocked |

Conclusion: **Real PostgreSQL+PostGIS+pgvector execution, live marine-source ingestion, and
embedding/LLM calls cannot be executed in this sandbox.** These are reported as
`UNAVAILABLE`/`CONFIGURATION_REQUIRED` with the above evidence, never as fake PASS.

## 1. Component status matrix

Legend: **PASS** (actually executed/verified here) | **UNAVAILABLE** (real infra/network
dependency present but not reachable in this sandbox) | **CONFIGURATION_REQUIRED** (code
present and in default config, but feature/source is disabled until env provided) |
**DEGRADED** (executed, honest degraded state verified).

| # | Component | Status | Notes / evidence |
|---|---|---|---|
| 1 | Backend FastAPI app boot | PASS | `GET /` -> 200 (API discovery incl. version 0.1.0, api_version 1) |
| 2 | Health endpoint honesty | PASS | `/api/v1/health` -> 200 `{"status":"degraded","database":"disconnected"}` when DB down (NOT false-live) |
| 3 | Readiness probe | PASS | `/api/v1/ready` -> 200 `{"status":"not_ready","ready":false,"components":{"database":{"status":"disconnected"},"scheduler":{"status":"not_configured"},...}}` |
| 4 | API contract endpoint | PASS | `/api/v1/contract` -> 200 publishes orchestrate/stream_ws, schemas v1.0 |
| 5 | MCP tool catalog | PASS | `GET /api/v1/mcp/tools` -> 33 tools (incl. 4 `analytics_governance`) |
| 6 | MCP invoke envelope | PASS | `POST /api/v1/mcp/invoke` -> ToolCallResponse with `ok/tool/result/error`, correlation ids |
| 7 | MCP source catalog | PASS (CONFIG) | `knowledge.source_catalog` -> 200, reports configured sources (incois base_url `https://incois.gov.in`, imd `https://mausam.imd.gov.in`, mosdac) as capability descriptors |
| 8 | MCP source status honesty | PASS | `knowledge.source_status` -> **HTTP 400 `DEPENDENCY_FAILURE`** + `mcp.tool_failed` when DB unreachable (does NOT fabricate LIVE) |
| 9 | Orchestrator intent+execution | PASS | `/api/v1/orchestrate` real runs: fishing->needs_input, safety->completed, knowledge->completed, route->completed, briefing(ml)->needs_input |
| 10 | MCP-invoked tool chain | PASS | Safety journey invoked real tools with `mcp.invoke_ok`: `safety.marine_safety_check`, `restriction.dynamic_active`, `analytics.risk_profile`, `marine.get_fused_state`, `knowledge.search` (5 tools, `execution.tool_calls=5`) |
| 11 | Safety invariant (no fake SAFE) | PASS | Safety query -> `risk.classification: "UNKNOWN"`, reason "Risk could not be assessed from the available data.", `hard_constraint:false`; **not** downgraded to SAFE |
| 12 | Graceful degradation limits | PASS | `limitations` lists missing data explicitly: "17 marine variable(s) unavailable", "ocean data source(s) not configured", "weather data source(s) not configured" |
| 13 | Verifier | PASS | `execution.verification.all_verified=true, checked=4, failed_claims=[]` |
| 14 | Agent strategy | PASS | `execution.notes.strategy="capability_matrix"` |
| 15 | Freshness reporting | PASS (unknown) | `execution.freshness.overall="unknown"` when no authoritative data (honest) |
| 16 | PostgreSQL migrations | UNAVAILABLE | 7 Alembic heads present (initial_schema -> marine -> restrictions -> phase6 -> phase9 -> knowledge -> evidence/pgvector) but no DB to run them against |
| 17 | init_db / create_all | UNAVAILABLE | `app/main.py` lifespan `init_db()` gated on reachable DB -> refused here |
| 18 | PostGIS spatial queries | UNAVAILABLE | no reachable DB; no geometry execution possible in sandbox |
| 19 | pgvector execution | UNAVAILABLE | no reachable DB; vector column requires Postgres + pgvector |
| 20 | Hybrid RAG (FTS) | DEGRADED / PASS | `knowledge_rag.search_fts` uses `func.ts_rank` **only when dialect is postgresql** (app/db/marine_repository pattern); offline it catches exception (line 226 `except Exception: pass`) and returns empty rows -> `mode=fts_only, note="lexical FTS retrieval (ts_rank); no embedding provider"`; expired/inactive filtered via `_validity_filters` |
| 21 | Embeddings (hybrid) | CONFIGURATION_REQUIRED | embedder is `NotConfiguredEmbedder` (`available=False`) when `EMBEDDINGS_API_KEY/ENDPOINT` empty -> no fake vectors; note states "no embedding provider" |
| 22 | Source freshness adjudication | PASS (DB-dependent) | implements NOT_CONFIGURED when not configured (registry line 74-75); DEPENDENCY_FAILURE when DB down |
| 23 | External marine ingestion | CONFIGURATION_REQUIRED | `incois_enabled/imd_enabled/mosdac_enabled = False` (verified via config); no egress anyway -> correctly not attempted |
| 24 | LLM (translation/STT/TTS) | CONFIGURATION_REQUIRED / UNAVAILABLE | keys empty in default env; no egress (ConnectTimeout) |
| 25 | ML governance runtime | PASS | live acceptance `ml governance cases: 12 ok=12`; benchmark all 12 governance cases success |
| 26 | Proactive events / alerts | PASS | live acceptance `proactive cases: 9 ok=9`; benchmark 9 proactive cases success |
| 27 | Failure injection / degradation | PASS | health=degraded, readiness=not_ready, source_status=400 DEPENDENCY_FAILURE, risk=UNKNOWN — all verified under real DB-down conditions |
| 28 | Frontend API boundary | PASS (code-level) | `apps/web` Next.js 15 on :3000; talks only via API client using `NEXT_PUBLIC_API_URL`; no direct DB/marine source access (confirmed via explore) |
| 29 | Observability / correlation ids | PASS | logs carry `request_id` (req-*/orch-*) + `mcp.invoke`/`mcp.invoke_ok`/`mcp.tool_failed` structured events + access logs with `duration_ms` |
| 30 | Full test suite | PASS | `pytest tests` -> **406 passed, 2 skipped**, 4 warnings (Pydantic deprecation only), 15.5s |
| 31 | Phase 7 evaluation | PASS | 52/52, overall 100.0%, safety 100.0% |
| 32 | Live acceptance | PASS | 14 demo workflows ok, 9 proactive ok, 6 ml ok, 12 governance ok |
| 33 | Benchmark | PASS | 10 scenarios + 9 proactive + 6 ML + 12 governance, all `success`, 0 failures |

## 2. Environment validation (Task 2)

- Root `.env` is **git-ignored**; only `.env.example` (tracked) is committed, containing placeholders only -> **no secrets committed**.
- `.env` currently contains: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_PROJECT_REF`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_JWKS_URL`. No LLM / STT / TTS / translation / embedding / INCOIS / IMD / MOSDAC keys are set in `.env`.
- `.env.example` documents all required categories: DB (PostGIS), LLM (openrouter), STT (sarvam), TTS (elevenlabs), translation (google), ARGO GDAC/ERDDAP/Argovis, real-time marine (INCOIS/IMD/MOSDAC, default disabled, "no fake data ever"), freshness thresholds, plausibility bounds, embeddings, server, CORS, logging.
- Runtime config confirms external sources disabled by default and `SCHEDULER_ENABLED/PROACTIVE_ENABLED/ML_GOVERNANCE_ENABLED=true`.

## 3. Confirmed runtime gaps (honest)

1. **Database execution is genuinely impossible in this sandbox** (no egress, no local PG, Docker/WSL broken, Supabase unreachable). All DB/PostGIS/pgvector items are `UNAVAILABLE`, verified with connection-refused evidence.
2. `knowledge.source_status` surfaces a DB dependency as an **HTTP 400 DEPENDENCY_FAILURE** rather than a 503 "DB unavailable". Functionally honest (it fails loudly, does not fake LIVE), but the status code is a candidate improvement for a future phase (graceful 503 + explicit `reason=DB_UNAVAILABLE`).
3. Offline `knowledge.search` returns `mode=fts_only` with **empty** chunk results (exception swallowed at `knowledge_rag.py:226`); it does NOT run real PostgreSQL `ts_rank` when the DB is down. The orchestrator did not fabricate results, but an operator must not interpret the empty fts_only success as a real retrieval.

## 4. What this audit proves

- The runtime, when DB and live sources are unavailable, **degrades honestly**: health=degraded, readiness=not_ready, risk=UNKNOWN (never SAFE), limitations enumerated, source_status fails loudly. The Phase 14 safety hierarchy (never convert UNAVAILABLE -> SAFE) is satisfied.
- All offline-deterministic capabilities (orchestration, agents, MCP, ML governance, proactive events/alerts, verifier, benchmarking, multilingual, multi-turn) execute against the real code and pass.
- DB-backed and network-backed capabilities are present in code and correctly gated, but cannot be verified in this sandbox; they are reported `UNAVAILABLE`/`CONFIGURATION_REQUIRED`, never false-PASS.

---

## 5. Phase 14 follow-up (2026-09-02) - DB became reachable + TEST-MOCK + ARGO + voice

Since the initial audit, the egress/boundary state changed: the Supabase DB is now
reachable, so the DB-backed items were re-verified live, and the parallel work fronts
were advanced.

### 5.1 DB / schema / pgvector now verified live

| Check | Result | Evidence |
|---|---|---|
| Supabase DB reachable | PASS | `GET /api/v1/health` -> `healthy`/`connected`; `/api/v1/ready` -> `ready:true`, db connected, orchestrator available |
| pgvector installed | PASS | `CREATE EXTENSION vector` -> `vector 0.8.2` on the real DB |
| Schema migrated | PASS | `alembic upgrade head` -> revision `f3d2c1b0a9e8` (initial -> marine -> restrictions -> phase6 -> phase9 -> knowledge -> evidence/pgvector); fixed one migration bug (`USING embedding::vector(1536)` cast on `knowledge_chunks.embedding`) |
| `init_db()` | PASS | all 29 model tables present (31 public tables); `alerts`, `marine_events`, `restriction_lifecycle`, `user_alert_preferences` created via `create_all` |
| PostGIS spatial query | PASS | `ST_Distance` Kochi->Mumbai = 1,066,628 m; `spatial_ref_sys` 8500 rows; 3 GiST spatial indexes |
| pgvector query | PASS | cosine sim `0.00` (identical) / `1.00` (orthogonal); `knowledge_chunks.embedding` type = `vector(1536)` |
| `sources` table | CONFIG | `knowledge.source_catalog` reports `sources=0` (reads DB `sources` table, currently empty) |

### 5.2 TEST-MOCK sample data sources (approved while awaiting government API keys)

A clearly-labelled deterministic **sample-data source** (`MockMarineDataSource`) was added
so the pipeline can be demonstrated end-to-end without government keys. Hard guarantees:

- `DataStatus.TEST_MOCK` added; a mock source is **never** rendered `LIVE`.
- `is_mock` flag on the base source; `registry.status()`, `MarineDataService._source_statuses`
  and `_render` all downgrade mock-only data to `TEST_MOCK`.
- `tools_knowledge.source_catalog` hides the mock adapter while disabled (default off).
- Gated by `MOCK_MARINE_ENABLED / MOCK_WEATHER_ENABLED / MOCK_WARNINGS_ENABLED` (all default false).

Verified live on the reachable DB (Kochi 9.9, 76.3):

```
[ocean] status=success inserted=1      [weather_forecast] inserted=3
[weather_observation] inserted=1       [tides] inserted=4
[pfz] inserted=1                       [warnings] inserted=1
[read ocean/weather/tides/pfz/warnings] result_status=test_mock  rows>0
source_statuses: incois/imd/mosdac=not_configured, mock_marine=test_mock
```

This confirms the **`TEST_MOCK` (never `LIVE`)** invariant holds at both the per-source
status and the per-result-status level. Real INCOIS/IMD/MOSDAC remain `NOT_CONFIGURED`.

### 5.3 ARGO wiring (ingestion + tools)

- `ArgoClient` (existing argopy wrapper) previously had **no write path**.
- Added `db/argo_repository.py` (idempotent upsert on `platform_number, cycle_number`),
  `data/argo_persist.py` (xarray Dataset -> profile/observation rows),
  `services/argo_service.py` (search/stats/ingest_region/ingest_float),
  `mcp/tools_argo.py` (4 tools: `argo.profile_search`, `argo.stats`,
  `argo.ingest_region`, `argo.ingest_float`), wired into `build_tool_registry`.
- MCP catalog now exposes **37 tools** (33 prior + 4 argo).
- Live ARGO GDAC fetch still requires egress/key; status `CONFIGURATION_REQUIRED`

  (data-plane reads work; ingestion needs reachable GDAC).

### 5.4 Voice providers (STT/TTS/translation bodies implemented)

- Replaced the four `NotImplementedError` bodies with real `httpx` calls:
  Sarvam STT (`/v1/audio/speech-to-text`), Sarvam TTS (`/v1/audio/text-to-speech`),
  ElevenLabs TTS (`/v1/text-to-speech/{voice_id}`), Google translation (`translate/v2`).
- Providers still require keys (`STT_API_KEY`, `TTS_API_KEY`, `TRANSLATION_API_KEY`);
  constructor raises `ValueError` when absent, so no key -> `CONFIGURATION_REQUIRED`,
  honest and never a fake local synthesis.

### 5.5 Fix: marine warning ingestion missing classifier

- The pipeline's `_classify` had **no `warnings` product** entry (latent gap exposed by the
  mock warnings adapter): any warnings ingestion failed with `KeyError('warnings')`.
- Added `MarineValidationService.classify_warning` and wired `"warnings"` into the
  pipeline. Warnings now ingest successfully (verified live, inserted=1).

### 5.6 Remaining honest constraints (unchanged)

- Live INCOIS/IMD/MOSDAC ingestion still requires government API keys (approval pending).
- Live embeddings/LLM require `LLM_API_KEY` / `EMBEDDINGS_API_KEY` (not present in `.env`).
- ARGO GDAC fetch needs reachable network egress from the runtime.
- These remain `CONFIGURATION_REQUIRED`/`UNAVAILABLE`, never silent `PASS`/`LIVE`.

### 5.7 Suite after additions

- `pytest tests` -> **415 passed, 2 skipped** (was 406; +9 new Phase 14 unit tests).
- `python -m evaluation` -> **52/52**, overall 100%, safety 100%.