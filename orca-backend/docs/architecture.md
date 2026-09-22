# FloatChat Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (Next.js 15)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │   Chat UI   │  │   MapLibre  │  │  Recharts/  │  │  Evidence Card   │  │
│  │  (Voice)    │  │   Map       │  │  Plotly     │  │  + Provenance    │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────────┬─────────┘  │
│         │                │                │                 │             │
│         └────────────────┼────────────────┼─────────────────┘             │
│                          ▼                ▼                               │
│              ┌─────────────────────────────────────┐                      │
│              │         API Client (React Query)    │                      │
│              └──────────────────┬──────────────────┘                      │
│                                 │                                        │
└─────────────────────────────────┼────────────────────────────────────────┘
                                  │ HTTPS/JSON
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND (FastAPI)                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐  │
│  │ Query Planner│  │Query Executor│  │  Verifier    │  │  Narrative Gen   │  │
│  │  (LLM +      │  │ (Deterministic│  │ (Proof-Carry │  │  (Structured)   │  │
│  │  Tools)      │  │  Services)   │  │  Numbers)    │  │                  │  │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └────────┬─────────┘  │
│         │                │                │                 │             │
│         └────────────────┼────────────────┼─────────────────┘             │
│                          ▼                ▼                               │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    SERVICE LAYER                                     │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────┐  │  │
│  │  │   ARGO      │  │  ERDDAP/    │  │   Cache     │  │   Voice      │  │  │
│  │  │   Client    │  │  Argovis    │  │   (Parquet) │  │   Services   │  │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └──────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                      │
│                                    ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    DATABASE (Supabase PostgreSQL + PostGIS)         │  │
│  │  argo_profiles ◄──► argo_observations ◄──► dataset_snapshots        │  │
│  │  query_runs ◄──► evidence_records ◄──► narratives                   │  │
│  │  scenario_runs                                                        │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. Text Query Flow
```
User Question (any language)
    │
    ▼
Language Detection
    │
    ▼
Intent Classification + Entity Extraction (LLM with structured output)
    │
    ▼
┌──────────────────────────────────────┐
│ Missing mandatory parameters?        │
│   YES → Clarification Question       │
│   NO  → Validated Structured Query   │
└──────────────────────────────────────┘
    │
    ▼
Tool Selection (allowlisted: search_profiles, aggregate_timeseries, etc.)
    │
    ▼
Query Executor (deterministic SQL/Parquet operations)
    │
    ▼
Raw Results + Metadata
    │
    ▼
Verifier (checks every numeric claim against results)
    │
    ▼
┌──────────────────────────────────────┐
│ Verification PASSED?                 │
│   YES → Generate Response + Evidence │
│   NO  → Safe Fallback + Log          │
└──────────────────────────────────────┘
    │
    ▼
Response: Answer + Charts + Map + Evidence Card + Confidence + Audio (if voice)
```

### 2. Voice Query Flow (Malayalam)
```
Audio Input (Malayalam)
    │
    ▼
STT Provider → Malayalam Transcript
    │
    ▼
User Reviews/Edits Transcript
    │
    ▼
Translation Provider → Canonical Intent (English internal)
    │
    ▼
[Same as Text Query Flow from Intent Classification]
    │
    ▼
Malayalam Response Generation
    │
    ▼
TTS Provider → Malayalam Audio
    │
    ▼
Frontend: Transcript + English Evidence Card + Malayalam Audio + Text
```

---

## Service Responsibilities

| Service | Responsibility | Key Functions |
|---------|---------------|---------------|
| **Query Planner** | NL → Structured Query | `plan_query()`, `classify_intent()`, `extract_entities()`, `ask_clarification()` |
| **Query Executor** | Deterministic data access | `search_profiles()`, `aggregate_timeseries()`, `depth_profile_summary()`, `compare_baseline()`, `detect_anomaly()`, `project_scenario()`, `marine_condition_briefing()` |
| **Verifier** | Proof-carrying validation | `verify_numeric_claims()`, `verify_counts()`, `verify_filters()`, `verify_narrative()` |
| **Confidence** | Transparent scoring | `calculate_confidence()`, `explain_confidence()` |
| **Narrative** | Structured storytelling | `generate_anomaly_narrative()`, `generate_scenario_narrative()`, `generate_risk_briefing()` |
| **Risk Engine** | Conservative risk assessment | `assess_risk()`, `combine_components()`, `check_data_availability()` |
| **Voice Services** | Multilingual voice I/O | `transcribe()`, `translate()`, `synthesize()` (provider interfaces) |
| **ARGO Client** | Data ingestion | `fetch_profiles()`, `normalize_netcdf()`, `apply_qc()`, `store_parquet()` |
| **Cache** | Offline/demo data | `load_cached_dataset()`, `get_dataset_manifest()` |

---

## Database Schema (Supabase + PostGIS)

### Core Tables

```sql
-- Profiles (one per ARGO cycle)
CREATE TABLE argo_profiles (
    id BIGSERIAL PRIMARY KEY,
    platform_number INTEGER NOT NULL,
    cycle_number INTEGER NOT NULL,
    profile_time TIMESTAMPTZ NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    geom GEOGRAPHY(POINT, 4326) GENERATED ALWAYS AS (
        ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
    ) STORED,
    source TEXT NOT NULL,
    source_url TEXT,
    qc_status TEXT NOT NULL DEFAULT 'recommended',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (platform_number, cycle_number)
);

CREATE INDEX idx_argo_profiles_time ON argo_profiles (profile_time);
CREATE INDEX idx_argo_profiles_geom ON argo_profiles USING GIST (geom);
CREATE INDEX idx_argo_profiles_platform ON argo_profiles (platform_number);

-- Observations (measurements at each depth)
CREATE TABLE argo_observations (
    id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES argo_profiles(id) ON DELETE CASCADE,
    pressure_dbar DOUBLE PRECISION,
    depth_m DOUBLE PRECISION,
    temperature_c DOUBLE PRECISION,
    salinity_psu DOUBLE PRECISION,
    oxygen_umol_kg DOUBLE PRECISION,
    chlorophyll DOUBLE PRECISION,
    temperature_qc SMALLINT,
    salinity_qc SMALLINT,
    oxygen_qc SMALLINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_argo_obs_profile ON argo_observations (profile_id);
CREATE INDEX idx_argo_obs_depth ON argo_observations (depth_m);
CREATE INDEX idx_argo_obs_temp ON argo_observations (temperature_c) WHERE temperature_c IS NOT NULL;

-- Dataset snapshots for reproducibility
CREATE TABLE dataset_snapshots (
    id BIGSERIAL PRIMARY KEY,
    dataset_name TEXT NOT NULL,
    region TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    source_version TEXT,
    record_count BIGINT NOT NULL,
    profile_count BIGINT NOT NULL,
    float_count BIGINT NOT NULL,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    checksum TEXT,
    status TEXT NOT NULL DEFAULT 'active'
);

-- Query execution log
CREATE TABLE query_runs (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_input TEXT NOT NULL,
    detected_language TEXT,
    normalized_intent TEXT,
    structured_query JSONB NOT NULL,
    tool_calls JSONB,
    execution_status TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_query_runs_session ON query_runs (session_id);
CREATE INDEX idx_query_runs_created ON query_runs (created_at);

-- Evidence/provenance for every answer
CREATE TABLE evidence_records (
    id BIGSERIAL PRIMARY KEY,
    query_run_id BIGINT NOT NULL REFERENCES query_runs(id) ON DELETE CASCADE,
    float_ids INTEGER[] NOT NULL,
    profile_count BIGINT NOT NULL,
    observation_count BIGINT NOT NULL,
    region JSONB NOT NULL,
    depth_range JSONB,
    time_range JSONB,
    filters JSONB,
    data_freshness JSONB,
    confidence_label TEXT NOT NULL,
    confidence_components JSONB NOT NULL,
    limitations TEXT[] NOT NULL DEFAULT '{}',
    source_identifiers JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Verified narratives
CREATE TABLE narratives (
    id BIGSERIAL PRIMARY KEY,
    query_run_id BIGINT NOT NULL REFERENCES query_runs(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    narrative_text TEXT NOT NULL,
    numeric_claims JSONB NOT NULL,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- What-if scenarios
CREATE TABLE scenario_runs (
    id BIGSERIAL PRIMARY KEY,
    query_run_id BIGINT NOT NULL REFERENCES query_runs(id) ON DELETE CASCADE,
    variable TEXT NOT NULL,
    region JSONB NOT NULL,
    baseline JSONB NOT NULL,
    trend_window JSONB NOT NULL,
    projection_horizon INTERVAL NOT NULL,
    model_name TEXT NOT NULL,
    assumptions JSONB NOT NULL,
    uncertainty_method TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## API Contracts

### Core Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| POST | `/api/v1/chat` | Main chat endpoint (text) |
| POST | `/api/v1/query/plan` | Plan query only (debug) |
| POST | `/api/v1/query/execute` | Execute structured query |
| POST | `/api/v1/voice/transcribe` | STT |
| POST | `/api/v1/voice/synthesize` | TTS |
| POST | `/api/v1/profiles/search` | Direct profile search |
| POST | `/api/v1/anomalies/detect` | Anomaly detection |
| POST | `/api/v1/scenarios/project` | Scenario projection |
| POST | `/api/v1/risk/briefing` | Marine risk briefing |
| POST | `/api/v1/exports/csv` | CSV export |
| GET | `/api/v1/datasets/status` | Dataset status |
| GET | `/api/v1/query-runs/{id}` | Query run details |

---

## Technology Stack Summary

| Layer | Technology | Version |
|-------|------------|---------|
| Frontend Framework | Next.js | 15+ |
| Language | TypeScript | 5+ |
| Styling | Tailwind CSS | 4+ |
| UI Components | shadcn/ui (Radix) | latest |
| State/Data | React Query (TanStack Query) | 5+ |
| Mapping | MapLibre GL | 4+ |
| Charts | Recharts + Plotly.js | latest |
| Audio | Web Audio API + MediaRecorder | native |
| Validation | Zod | 3+ |

| Layer | Technology | Version |
|-------|------------|---------|
| Backend Framework | FastAPI | 0.110+ |
| Language | Python | 3.11+ |
| Validation | Pydantic | 2+ |
| ASGI Server | Uvicorn | 0.29+ |
| ORM/DB | SQLAlchemy 2+ / Supabase Client | latest |
| ARGO | argopy, xarray, pandas | latest |
| Scientific | NumPy, SciPy, pyarrow | latest |
| Testing | pytest | 8+ |

| Layer | Technology |
|-------|------------|
| Database | Supabase PostgreSQL 16 + PostGIS 3 |
| Vector | pgvector 0.7+ |
| Storage | Supabase Storage |
| Auth | Supabase Auth (optional for MVP) |
| Frontend Deploy | Vercel |
| Backend Deploy | Railway / Render |
| CI/CD | GitHub Actions |

---

## Security Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                     TRUST BOUNDARIES                         │
├─────────────────────────────────────────────────────────────┤
│  USER BROWSER                                                │
│  ├─ Microphone access (explicit permission)                 │
│  ├─ Location (explicit permission, not stored)              │
│  └─ No API keys                                             │
├─────────────────────────────────────────────────────────────┤
│  FRONTEND (Vercel)                                          │
│  ├─ Calls backend API only                                  │
│  ├─ No database access                                      │
│  └─ No secrets                                              │
├─────────────────────────────────────────────────────────────┤
│  BACKEND (Railway/Render)                                   │
│  ├─ Supabase service role key (server only)                 │
│  ├─ Voice provider API keys (server only)                   │
│  ├─ LLM API key (server only)                               │
│  ├─ Parameterized SQL only                                  │
│  ├─ Request size limits                                     │
│  └─ Rate limiting                                           │
├─────────────────────────────────────────────────────────────┤
│  DATABASE (Supabase)                                        │
│  ├─ Row-Level Security on user tables                       │
│  ├─ Service role for ingestion only                         │
│  └─ Read-only roles for query executor                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Offline Demo Mode Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OFFLINE DEMO MODE                         │
├─────────────────────────────────────────────────────────────┤
│  Frontend detects: VITE_DEMO_MODE=true                      │
│       │                                                     │
│       ▼                                                     │
│  Loads /data/sample/demo_manifest.json                      │
│       │                                                     │
│       ▼                                                     │
│  Uses cached Parquet files from Supabase Storage            │
│  (or bundled in Docker image)                               │
│       │                                                     │
│       ▼                                                     │
│  Query Executor reads Parquet via pyarrow                   │
│  (no database connection needed)                            │
│       │                                                     │
│       ▼                                                     │
│  All provenance shows "demo" source + snapshot timestamp    │
└─────────────────────────────────────────────────────────────┘
```

---

## Configuration

### Environment Variables

```bash
# Frontend (.env.local)
NEXT_PUBLIC_API_URL=https://api.floatchat.example.com
NEXT_PUBLIC_DEMO_MODE=false
NEXT_PUBLIC_MAP_STYLE=light

# Backend (.env)
DATABASE_URL=postgresql://...
SUPABASE_URL=https://...
SUPABASE_SERVICE_KEY=...
SUPABASE_STORAGE_BUCKET=floatchat-data
LLM_PROVIDER=openai
LLM_API_KEY=...
LLM_MODEL=gpt-4o-mini
STT_PROVIDER=sarvam
STT_API_KEY=...
TTS_PROVIDER=sarvam
TTS_API_KEY=...
TRANSLATION_PROVIDER=google
TRANSLATION_API_KEY=...
DEMO_MODE=false
CACHED_DATA_PATH=/app/data/cached
MAX_AUDIO_SIZE_MB=10
RATE_LIMIT_RPM=60
CORS_ORIGINS=https://floatchat.example.com,http://localhost:3000
```

---

## Deployment Topology

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Vercel    │────▶│  Railway    │────▶│  Supabase   │
│  (Frontend) │     │  (Backend)  │     │  (Database) │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Supabase   │
                    │  Storage    │
                    │ (Parquet)   │
                    └─────────────┘
```

---

## CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v2
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm typecheck

  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgis/postgis:16-3.4
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r apps/api/requirements.txt
      - run: pytest apps/api/tests/

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v2
      - run: pnpm install --frozen-lockfile
      - run: pnpm test

  build:
    needs: [lint, test-backend, test-frontend]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t floatchat-api ./apps/api
      - run: docker build -t floatchat-web ./apps/web
```

---

## Observability

| Concern | Tool |
|---------|------|
| Logging | structlog (backend), console (frontend) |
| Metrics | Prometheus client (backend), Vercel Analytics (frontend) |
| Tracing | OpenTelemetry (backend) |
| Errors | Sentry (both) |
| Database | Supabase Dashboard + pg_stat_statements |