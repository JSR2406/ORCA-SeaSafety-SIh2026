# Phase 14 - Runtime Startup Procedure

This document records the exact, current startup sequence for the full
FloatChat/ORCA stack, in the required order:

`DATABASE -> DATA SOURCES -> INGESTION -> MCP -> API -> AGENTS -> ORCHESTRATOR -> ML -> EVENTS -> ALERTS -> FRONTEND`

All commands assume a Windows shell, repo root `E:\CODING\Floatchat`, a single
unified venv at `venv\Scripts\python.exe` and a single unified env file at repo
root `.env` (config.py resolves it by absolute path, so CWD no longer matters).
Runtime facts below were verified on 2026-09-01 (env/venv unified 2026-09-07).

## 0. Prerequisites / environment

- Create `.env` from `.env.example` (root). `.env` is git-ignored; no secrets committed.
- Required categories to populate before a LIVE run (all placeholders in `.env.example`):
  - `DATABASE_URL` (PostgreSQL + PostGIS + pgvector)
  - `INCOIS_BASE_URL/API_KEY/ENABLED`, `IMD_*`, `MOSDAC_*` (marine sources)
  - `EMBEDDINGS_API_KEY/ENDPOINT/MODEL` (hybrid RAG; empty -> FTS-only)
  - `LLM_*`, `STT_*`, `TTS_*`, `TRANSLATION_*` (LLM/voice/translation)
  - `SCHEDULER_ENABLED`, `PROACTIVE_ENABLED`, `ML_GOVERNANCE_ENABLED`
  - `NEXT_PUBLIC_API_URL` (frontend -> default `http://localhost:8000`)
- Database must be PostgreSQL 16+ with PostGIS 3 and pgvector extensions installed.

## 1. DATABASE

```
# apply schema (7 Alembic heads: initial -> marine -> restrictions -> phase6 -> phase9 -> knowledge -> evidence/pgvector)
$env:PYTHONPATH = "apps\api"
venv\Scripts\python.exe -m alembic upgrade head
# (app.main lifespan init_db() also runs Base.metadata.create_all at boot)
```

## 2. DATA SOURCES  (configure + enable)

- Set `INCOIS_ENABLED=true` (+ key), optionally `IMD_ENABLED`, `MOSDAC_ENABLED`.
- `app.datasources` registry (incois / imd / mosdac) reads these settings; a source
  with empty key reports NOT_CONFIGURED and never emits fake data.

## 3. INGESTION  /  MCP

- Ingestion runs on the polling scheduler (`SCHEDULER_ENABLED=true`) plus per-source retry/backoff.
- MCP layer boots with the API process; 33 tools, including 4 `analytics_governance`.
  - `GET /api/v1/mcp/tools` (catalog), `GET /api/v1/mcp/status`, `POST /api/v1/mcp/invoke`.

## 4. API

```
$env:PYTHONPATH = "apps\api"
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verified availability: uvicorn 0.52.4, sqlalchemy 2.0.30, alembic 1.13.1.
Lifespan starts: `init_db()` -> source polling scheduler -> proactive engine -> ML governance loop.

## 5. AGENTS + ORCHESTRATOR  (inside API process)

- Orchestrator (`POST /api/v1/orchestrate`) selects agents via `capability_matrix`
  (verified), invokes them through the MCP tool layer only (no direct DB/source bypass).
- Agents available: pfz, marine, weather, safety, route, restrictions, knowledge,
  analytics/ML, scenarios, briefing.
- `POST /api/v1/orchestrate/stream` (WebSocket) for streaming responses.

## 6. ML                      ## events + alerts

- ML runtime + governance loop start with the app when `ML_GOVERNANCE_ENABLED=true`.
- Provenance/ledger: `GET /api/v1/ml/*` (7 read-only routes).
- Event bus emits proactive/alerts; alert dedup + escalation run in the events layer.

## 7. FRONTEND

```
cd apps\web
npm install          # once
npm run dev          # Next.js on http://localhost:3000 (dev)
# or: npm run build && npm start
```

- `apps/web/next.config.js` rewrites `/api/backend/:path*` -> `NEXT_PUBLIC_API_URL`
  (default `http://localhost:8000`). The frontend never touches the DB or marine
  sources directly.

## 8. Verification commands (from repo root)

```
$env:PYTHONPATH = "apps\api"
$env:POSTGIS_DATABASE_URL=""    # for non-DB tests only
venv\Scripts\python.exe -m pytest tests -q          # 468 passed, 2 skipped
venv\Scripts\python.exe -m evaluation               # Phase 7: 52/52
venv\Scripts\python.exe -m evaluation.live          # RUN_LIVE_ACCEPTANCE=1 -> 14 demos/9 proactive/6 ML/12 governance
venv\Scripts\python.exe -m evaluation.benchmark     # 10 scenarios + 9 + 6 + 12 governance
```

## 9. Status interpretation (verified honesty rules)

- `/api/v1/health`: `status=degraded` + `database=disconnected` when DB down (never false-live).
- `/api/v1/ready`: `ready=false` / `not_ready` until DB reachable + sources configured.
- Safety: with no authoritative data, risk is `UNKNOWN` (never silently SAFE).
- Source status: DB unreachable -> `knowledge.source_status` returns 400 `DEPENDENCY_FAILURE`
  (fails loudly; does not fabricate LIVE).

## 10. Current-sandbox caveat

In the 2026-09-01 sandbox there was no outbound egress, no reachable PostgreSQL
(hosted Supabase refused connection; no local PG; Docker/WSL2 engine unavailable),
so steps 1-3 DB/ingestion could not be exercised live. Those are reported
`UNAVAILABLE` / `CONFIGURATION_REQUIRED` in `docs/phase14-runtime-audit.md` and
`docs/phase14-e2e-acceptance-report.md`; all offline-runnable steps above were
executed and verified.

### 10.1 Follow-up (2026-09-02): DB live + TEST-MOCK demo path

The Supabase DB became reachable. `alembic upgrade head` -> `f3d2c1b0a9e8` applied;
pgvector `0.8.2` present; `init_db()` created the 29 model tables. Health now reports
healthy/connected; readiness reports ready. The pipeline was exercised end-to-end with
**TEST-MOCK** sample data (`MOCK_*_ENABLED=true`) which ingests/reads with
`result_status=test_mock` (never `LIVE`); real INCOIS/IMD/MOSDAC remain
`not_configured`. ARGO now has a write path + 4 MCP tools (37 total); voice
STT/TTS/translation bodies implemented. Full updated matrix in
`docs/phase14-runtime-audit.md` section 5 and `docs/phase14-e2e-acceptance-report.md`
section 5.1. Live government-source/LLM/embedding/voice calls still require API keys +
egress (`CONFIGURATION_REQUIRED`).