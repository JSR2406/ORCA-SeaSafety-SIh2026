# Phase 14 - Supabase PostgreSQL Preflight

Date: 2026-09-01
Mode: **Preflight only.** No application architecture, RLS policy, spatial_ref_sys,
schema, or data changes were made. No database credentials are printed here (host is
shown; secrets are never disclosed). Connection uses the configured `DATABASE_URL`
(resolved to `db.qkrwxhoebnrtsmxlfvsx.supabase.co`).

## Executive result

Connectivity to the configured Supabase database **SUCCEEDED**, so Phase 14 database
validation is authorized to proceed — with the explicit blocker that **pgvector is not
installed** and the **application schema is largely absent** (only 3 of the app's
expected tables exist, under this DB's older naming).

| Component | Result |
|---|---|
| PostgreSQL | **PASS** |
| PostGIS | **PASS** |
| pgvector | **FAIL - not installed** |
| Application schema | **FAIL / PARTIAL - most expected tables missing** |
| Permissions | **PASS** (postgres role; RLS-bypassing) |
| RLS | **PASS (with note)** - enabled but zero policies; not a blocker for this role; spatial_ref_sys RLS is off |
| Spatial queries | **PASS capability only** - PostGIS available; app spatial tables not yet present to query |
| Vector queries | **FAIL - pgvector missing; no vector column/type** |

## 1. PostgreSQL connectivity

- **PASS** - TCP/PostgreSQL connection established to
  `db.qkrwxhoebnrtsmxlfvsx.supabase.co:5432` as `postgres`.

## 2. current_database()

- `postgres`

## 3. current_user

- `postgres`

## 4. PostgreSQL version

- `17.6`

## 5. PostGIS extension and version

- Installed: `postgis 3.3.7`

## 6. pgvector / vector extension and version

- **FAIL** - `SELECT count(*) FROM pg_extension WHERE extname='vector'` -> `0`.
  No `vector`/`halfvec` type; `version_of()` function does not exist. pgvector is
  **not installed** on this database.

## 7. SELECT PostGIS_Version()

- `3.3 USE_GEOS=1 USE_PROJ=1 USE_STATS=1`

## 8. SELECT COUNT(*) FROM public.spatial_ref_sys

- `8500` (**PASS** - spatial reference system table present and readable)
- RLS on `spatial_ref_sys` = **off** (relrowsecurity=false) - not modified.

## 9. Database schema visibility

- Schema `public` USAGE = **True**; PUBLIC CREATE = **True**.
- Actual physical tables present in `public`:
  `spatial_ref_sys, alembic_version, dataset_snapshots, query_runs, argo_observations,
  argo_profiles, evidence_records, narratives, scenario_runs, sources,
  source_capabilities, ocean_observations, weather_observations, weather_forecasts,
  tide_predictions, pfz_zones, marine_warnings, restricted_areas, ingestion_runs` (19).

## 10. Application table visibility

- **PARTIAL** - the app's SQLAlchemy models expect tables under these names. Present:
  `weather_observations`, `pfz_zones`, `query_runs`.
- **Missing** (expected by `app/db/models.py` / migrations but absent in `public`):
  `marine_observations`, `dynamic_restrictions`, `geospatial_boundaries`,
  `knowledge_documents`, `knowledge_chunks`, `marine_events`, `alerts`, `ml_models`,
  `prediction_ledger`, `model_registry`, `model_versions`, `provenance_events`,
  `conversations`, `restrictions`, `warnings`.
- `alembic_version` exists, but none of the app Alembic heads (initial -> marine ->
  restrictions -> phase6 -> phase9 -> knowledge -> evidence/pgvector) produced the
  expected app tables under this database's current naming. This is categorized as a
  **schema / migration failure** (see section 12).

## 11. Role privileges

- Role `postgres` membership includes Supabase roles: `anon`, `authenticated`,
  `authenticator`, `service_role`, `supabase_privileged_role`, plus PG monitoring/owner
  roles. It is the table owner / RLS-bypassing role.
- `has_schema_privilege('public','USAGE') = True`; `('CREATE') = True`.
- Grants on present app tables (`weather_observations`, `pfz_zones`, `query_runs`):
  `DELETE, INSERT, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE`.
- **PASS** - the configured role has the privileges required to read/write the schema.

## 12. Failure categorization

| Category | Status | Detail |
|---|---|---|
| connection failure | NO | Connect OK |
| authentication failure | NO | Authenticated as postgres |
| grant/permission failure | NO | Full privileges (possibly too broad) |
| RLS failure | NO (note) | RLS enabled with **zero policies**; `postgres` bypasses RLS so reads work, but a non-superuser app role would see nothing. Current app uses `postgres`. |
| missing extension | **YES** | **pgvector (`vector`) is not installed** |
| missing table | **YES** | Most app tables absent; only `weather_observations`, `pfz_zones`, `query_runs` present |
| schema/migration failure | **YES** | `alembic_version` present but app migrations have **not** created the expected app schema under this DB's naming |

Primary blockers to full Phase 14 DB validation:
1. **Install pgvector** and add the extension to the database (`CREATE EXTENSION IF NOT EXISTS vector;`) - requires an operator with create-extension rights; not performed preflight.
2. **Apply the application schema** (Alembic heads / `init_db()` `create_all`) - requires an operator decision because the DB already contains a differently-named existing schema (do not drop it; reconcile/run migrations against it). Not performed (preflight only).

## RLS inspection (reported only - nothing altered)

- RLS is **enabled** (`relrowsecurity=true`) on every `public` table **except**
  `spatial_ref_sys` (which is `false` and was left alone).
- `relforcerowsecurity=false` everywhere (RLS enabled but not forced; RLS-bypass roles unaffected).
- **Zero RLS policies exist** (`pg_policies` empty). Semantics: for any non-bypass role,
  RLS-enabled tables with no policies evaluate to **deny-all**. This is currently invisible
  because the app connects as `postgres` (bypasses RLS). It is **not** a blocker today but is
  a security posture to be aware of; do not enable permissive-by-default policies.

Recommended policies (separate from this preflight; **not applied**):
- If the app ever moves off the `postgres`/`service_role` role to a least-privilege role,
  add narrow, per-table policies: e.g. `SELECT` on marine/weather/pfz/restrictions for the
  app role; `INSERT/UPDATE` on `alerts`/evidence for the writer role; restrict `service_role`
  to app-owned tables only. Leave `spatial_ref_sys` with RLS off (as-is).

## Next step

Connectivity+PostGIS+permissions PASS; **pgvector missing** and **schema missing** are the
two explicit blockers. Phase 14 database validation should proceed only after:
(a) an operator installs the `vector` extension, and (b) the application schema is reconciled
via Alembic/`init_db()` against the existing (non-destroyed) schema. Repeat this preflight
after those steps to re-check the two FAIL items before running spatial/vector execution.

---

## 13. Follow-up (2026-09-02): blockers resolved

Both preflight blockers were subsequently cleared and the DB items were verified live:

| Component | Preflight | Follow-up result |
|---|---|---|
| pgvector | **FAIL - not installed** | **PASS** - `CREATE EXTENSION vector` -> `vector 0.8.2`; `knowledge_chunks.embedding` type = `vector(1536)`; cosine distance query verified |
| Application schema | **FAIL - most tables missing** | **PASS** - `alembic upgrade head` -> revision `f3d2c1b0a9e8`; `init_db()` -> 29 model tables (31 public tables) confirmed |
| PostgreSQL | PASS | PASS (17.6) |
| PostGIS | PASS | PASS (3.3.7); `ST_Distance` Kochi->Mumbai = 1,066,628 m; 3 GiST spatial indexes |
| Migrations | schema/migration failure | **PASS** - one migration bug fixed (`USING embedding::vector(1536)` cast on migration `0f7e1a2b3c4d`); head reached |

Other Phase 14 additions verified against this live DB in the same window:
- **TEST-MOCK sample source** (all 6 products ingest/read with `result_status=test_mock`,
  never `LIVE`; real INCOIS/IMD/MOSDAC remain `not_configured`).
- **ARGO write path** (`argo_repository`/`argo_persist`/`ArgoService` + 4 `argo.*` MCP tools).
- **Warnings classifier fix** (latent `KeyError('warnings')` resolved; warnings ingest OK).

Nothing altered that the preflight is expected to leave untouched: `spatial_ref_sys` is
unmodified (RLS remains off); no RLS policy changes were made; no permissive public policies
were added; the connection still uses `postgres`/`service_role`. Live government-source,
LLM/embedding, and voice calls remain `CONFIGURATION_REQUIRED` pending API keys + egress.