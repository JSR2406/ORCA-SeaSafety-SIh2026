# Phase 1 + Phase 2 Engineering Report

Real-Time Marine Data Foundation (Phase 1) and MCP Capability/Tool Layer (Phase 2)
for the FloatChat → Agentic Marine Intelligence Platform.

## 1. Phase 1 — Real-Time Marine Data Foundation

### 1.1 Schema & model layer
- Canonical contracts in `app/models/`: `OceanConditions`, `WeatherObservation`,
  `WeatherForecast`, `TidePrediction`, `PFZZone`, `MarineWarning`, `RestrictedArea`,
  all source-agnostic with a shared `QualityStatus` and `utcnow()` (timezone-aware).
- `app/db/models.py` maps them to PostGIS tables. Every geographic table uses a
  `Geometry`/`Geography` SRID-4326 column plus an explicit gist index.
  `metadata` is **reserved** by pydantic — DB uses `metadata_json`.
- Idempotency: every product table has a unique `(source, source_record_id)`
  constraint (`postgresql_nulls_not_distinct=True`); marine warnings/restricted
  areas use `warning_id`/`area_id`.

### 1.2 Migrations (applied to live Supabase)
- `729be30b0cb2_initial_schema` (core + argo) and `8f51d7a9c3b2_marine_data_infrastructure`.
- `alembic_version = 8f51d7a9c3b2`. Verified on Supabase: all marine tables, 8 gist
  indexes, and geo columns present.
- **Gotcha fixed**: geoalchemy2 0.20.0 defaults `spatial_index=True`, which
  auto-creates `idx_<table>_<col>` inside `op.create_table` and collides with the
  explicit `op.create_index`. Both migrations pass `spatial_index=False` on geo
  columns. Any future migration that creates a geo column must do the same.
- `migrations/env.py` supports a `DATABASE_URL` override and `%`-escapes `%40`.

### 1.3 Data sources & acquisition
- `app/datasources/` — `HTTPDataTransport` (bounded retry/backoff, timeouts:
  retry on 5xx/429/transport/timeout, fail fast on permanent 4xx and non-JSON)
  and adapters `INCOISAdapter`, `IMDAdapter`, `MOSDACAdapter`
  (`app/datasources/incois.py|imd.py|mosdac.py`).
- **No mock/offline fallback.** With no `_API_KEY`/`_ENABLED`, an adapter
  `is_configured=False` and reports `NOT_CONFIGURED`; tools return
  `SOURCE_UNAVAILABLE` rather than fabricated data.
- `app/ingestion/` — pipeline = fetch → validate → normalize → dedup → store →
  track, plus a minimal asyncio `SourcePollingScheduler` wired into the app
  lifespan (`settings.scheduler_enabled`, `data_poll_interval_seconds`,
  per-source `source_poll_interval_seconds`). Dedup: durable
  `source_record_id` honored, else canonical SHA-256 content hash (`hash:` prefix).
  Ingestion runs are recorded in `ingestion_runs`.
- `app/ingestion/validation.py` — bounds-driven quality classification
  (VALID/SUSPICIOUS/INVALID/MISSING) against configurable physical bounds and
  geometry validity. Temporal fields are presence-checked (datetime is not
  numerically coercible).

### 1.4 Read facade
- `app/services/marine_data_service.py` — `MarineDataService`, the single
  read-side facade returning the uniform `MarineDataResult` envelope
  (status/sources/timestamps/freshness/provenance/confidence) for ocean, weather,
  tides, PFZ, warnings, restrictions. Status is derived from freshness thresholds;
  confidence decays with staleness. `sources_status()` adjudicates per-source
  freshness from tracked ingestion state.
- `app/services/geospatial_service.py` — containment/distance/route checks over
  stored geometries (shapely helpers are DB-free and unit-testable).
- `app/geo_utils.py` — GeoJSON ↔ shapely ↔ WKB helpers (`geojson_to_wkb`,
  `wkb_to_geojson`, `normalize_multipolygon`, …).
- `app/routers/marine.py` — `/api/v1/marine/*` HTTP surface.

### 1.5 Fixes found while hardening (this session)
- Upgraded shapely 2.0.4 → **2.1.2**: shapely 2.0.x is incompatible with numpy 2.x;
  `MultiPolygon` construction (used by `normalize_multipolygon` in ingestion)
  crashed at runtime.
- `marine_repository` used generic `sqlalchemy.insert()` which has **no**
  `on_conflict_do_nothing/on_conflict_do_update` — PostgreSQL idempotent inserts
  and `upsert_source` would have failed on the live DB. Now uses
  `sqlalchemy.dialects.postgresql.insert as pg_insert`.
- `MarineValidationService._num` marked every record INVALID because
  `float(datetime)` raises; temporal fields are now presence-checked.

## 2. Phase 2 — MCP Capability/Tool Layer

### 2.1 Package layout (`app/mcp/`)
| File | Responsibility |
|---|---|
| `registry.py` | `ToolDefinition` + `ToolRegistry`: register/get/list, Pydantic input-model coercion, error mapping, envelope normalization |
| `errors.py` | Stable `MCPErrorCode` set + `MCPToolError` |
| `schema.py` | `ToolCallRequest/Response`, `ToolDescriptor`, `marine_envelope()` |
| `context.py` | `ContextLogger`: structlog always, MCP `Context` logging when present |
| `tools_marine.py` | ocean conditions, tides, PFZ |
| `tools_weather.py` | weather forecast, observation |
| `tools_geospatial.py` | PFZ containment, restricted-area containment/distance, route intersection |
| `tools_safety.py` | advisory `marine_safety_check` (merged status, `_merge` worst-status-wins) |
| `tools_knowledge.py` | `source_catalog`, `source_status` |
| `server.py` | Native MCP SDK `MCPServer` (`floatchat-marine` v0.2.0) from the same registry |
| `register.py` | `build_mcp_component()` — single source of truth assembling services + registry |
| `router.py` | FastAPI `/api/v1/mcp/tools`, `/invoke`, `/status` |

`app/routers/mcp.py` re-exports the router; `app/main.py` includes it.

### 2.2 Tool contract
A tool is a plain typed async callable (optional trailing `ctx: Context | None =
None` for MCP SDK injection). Every tool:
1. is **bounded to a Phase 1 service method** — never an external API directly;
2. declares a Pydantic input model used to `model_validate` raw args
   (`ValidationError` → `INVALID_INPUT`);
3. returns the **structured envelope** or a plain dict (`{"status":"live",…}`).

12 tools, grouped `marine` / `weather` / `geospatial` / `safety` / `knowledge`;
safety classes `READ_ONLY`, `SPATIAL_ANALYSIS`, `DECISION_SUPPORT`.

### 2.3 Envelope + error-code semantics
`marine_envelope()` always renders `status` **and** `code` so agents can branch on
expected outcomes without exceptions:

| DataStatus | code |
|---|---|
| live / recent | `null` |
| stale | `SOURCE_STALE` |
| unavailable | `DATA_NOT_FOUND` |
| not_configured | `SOURCE_UNAVAILABLE` |
| error | `DEPENDENCY_FAILURE` |

Exceptions (via `MCPToolError`) are reserved for genuinely broken invocations:
`INVALID_INPUT`, `DEPENDENCY_FAILURE`, plus reserved `GEOMETRY_INVALID`,
`TIME_OUT_OF_RANGE`, `RATE_LIMITED`, `INTERNAL_ERROR`. `ValueError` →
`INVALID_INPUT`; anything else at the boundary → `DEPENDENCY_FAILURE` with
details. `metadata`/`ctx` never leak into the payload.

### 2.4 Provenance & temporal handling
Rows carry `source`, `source_record_id`, `observation_time`/`valid_time`/
`issued_at`, `source_timestamp`, `ingested_at` (UTC-aware). Query responses show
`timestamps` (requested/data/source/retrieved), `freshness`
(threshold/age/is_within_threshold), per-row `provenance`, and decayed
`confidence`.

## 3. Verification (all run on live Supabase)

- `python -m pytest tests -q` from repo root → **61 passed, 2 skipped**.
  New files: `tests/test_marine_unit.py` (geo utils, validation, dedup, HTTP
  transport retry/backoff, render freshness/envelope), `tests/test_mcp_unit.py`
  (registry, coercion, error mapping, envelope codes, safety merge, real
  assembly), `tests/conftest.py` (env + sys.path so ordering is stable).
- `RUN_POSTGIS_TESTS=1 python -m pytest tests/test_marine_postgis.py -q` →
  **2 passed**: real insert → near/far ST_DWithin query with GeoJSON round-trip →
  idempotent dedup; warning window/status + geometry binding. Self-cleans rows.
- HTTP boundary (TestClient, full lifespan): `/api/v1/mcp/tools` 200 (12 tools),
  `/api/v1/mcp/status` 200, `knowledge.source_catalog` live, unconfigured
  `marine.ocean_conditions` → `not_configured`/`SOURCE_UNAVAILABLE`, bad lat →
  HTTP 400 `INVALID_INPUT`. `app.main` imports; scheduler starts/shuts down cleanly.

## 4. Phase 3 integration points
- Enable sources (`*_ENABLED=true` + API keys) to start real ingestion; scheduler
  then polls, writes observations, and tools transition out of `not_configured`.
- `app/mcp/server.py` exposes the same tools over the native MCP transport for
  the agent runtime; the HTTP boundary stays for chores/smoke tests.
- pgvector/RAG, full Knowledge Agent, ML and multilingual phases plug in behind
  `MarineDataService` without touching the tool surface.

## 5. Known open items
- No INCOIS/IMD/MOSDAC credentials → real-time adapters intentionally
  `not_configured`; live-data tools report `SOURCE_UNAVAILABLE` by design.
- Pre-existing, unrelated: frontend build failures (ChatInterface props, ESLint),
  several pip conflicts (elevenlabs/pydantic, langchain, streamlit, playwright).
- FastAPI was bumped 0.110.1 → 0.141.1 to unblock starlette 1.6.0 import break.