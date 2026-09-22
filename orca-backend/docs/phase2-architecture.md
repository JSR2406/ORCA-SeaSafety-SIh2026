# Phase 2 Architecture Report

Floor/extension work done on top of `phase1-2-engineering.md`: MCP observability
(request/run tracing), the `restriction.*` tool group, the
`MarineCapabilityClient` seam that connects the legacy ORCA agents to the live
marine data layer, the RiskEngine **hard-constraint guard**, the knowledge +
marine-evidence schema (pgvector + PostgreSQL FTS), and durable evidence
persistence. All changes are additive; existing APIs and tests were preserved.

## 1. MCP observability (request_id / conversation_id)

- `app/mcp/schema.py` — `ToolCallRequest`/`ToolCallResponse` now carry
  `request_id` and `conversation_id` (optional, opaque strings).
- `app/mcp/registry.py` — `ToolRegistry.invoke(..., request_id=, conversation_id=)`
  threads them into `ContextLogger` (`.bind(context, request_id=,
  conversation_id=)`); internal log lines and raised `MCPToolError`s include the
  ids so failures can be correlated end-to-end.
- `app/mcp/router.py` passes the ids from HTTP headers/body into every invoke.

## 2. `restriction.*` tool group (3 tools)

| Tool | Purpose |
|---|---|
| `restriction.check_point` | Decision-support: active restricted areas + active warnings for a point, folded into a single availability envelope |
| `restriction.distance` | Distance from a point to the nearest restricted area |
| `restriction.near_route` | Restricted areas **and** warnings intersecting a route polyline |

- Implemented in `app/mcp/tools_restriction.py`; `GeospatialService` gained
  `warnings_near_route()` (mirrors `restrictions_near_route`). Wired in
  `app/mcp/register.py`.
- Funnels through the same `_merge` worst-status-wins convention as the safety
  group; unconfigured sources report `not_configured`/`SOURCE_UNAVAILABLE` and
  never fabricate zones.
- Tool count is now **15**.

## 3. MarineCapabilityClient — the agent seam

`app/services/marine_capability_client.py`:

- Lazy singleton (`get_marine_capability_client()`), owns the data services,
  and normalizes **every** result into a never-raise envelope:
  `{"available", "status", "sources", "data", "error"}`.
- Methods: `ocean_conditions`, `weather_at`, `active_restrictions_at`,
  `active_warnings_at`, `restrictions_near_route`, `warnings_near_route`,
  `pfz_at`. Each takes an optional `query_run_id` for evidence recording.
- `available=False` → the caller falls back to its own deterministic estimates
  and records a limitation. Facts are never invented.

### Agents wired
- `route_agent` — `_detect_hazards` / `_check_geofences` now use live warnings
  and restricted areas; `_assess_environmental_conditions` samples live ocean +
  weather along the route (deterministic seasonal baseline when unconfigured);
  `_calculate_risk` feeds active restrictions/warnings into the risk engine as
  **hard constraints**; `_get_limitations` is an instance method and reports
  source availability honestly.
- `geofence_agent` — live restricted areas checked first; demo geofences remain
  an explicit fallback, never mixed with live data. Fixed a latent schema bug
  (`violation_type` must be `enter|exit|pass`, previously `entry`).
- `scenario_agent` (both `app/agents/` and `app/services/` copies, kept
  byte-identical) — resolves live conditions once per scenario via
  `_resolve_live_conditions` and uses them as the baseline, else seasonal.

## 4. RiskEngine hard-constraint guard

`app/services/risk_engine.py`:

- `assess_risk(..., hard_constraints=...)` — backward-compatible keyword.
- `_evaluate_hard_constraints` treats **active restricted areas** and
  **active high/critical warnings** as authoritative. If any are present the
  final level becomes `elevated` (score clamped to >= 0.75) and the reasoning
  is prefixed with `HARD CONSTRAINT:` plus the specific area/warning details.
  Machine/ML estimates can never lower it.
- Weights (sum = 1.0): wave 0.35, wind 0.30, current 0.15, hazard 0.13,
  geofence 0.02, hard_constraint 0.05 — chosen so that pre-existing risk tests
  (`>= 0.7` elevated) remain green while reserving weight for the guard.

## 5. Schema: knowledge base + marine evidence (migration `0f7e1a2b3c4d`)

- `CREATE EXTENSION IF NOT EXISTS vector` (PostgreSQL only).
- `knowledge_documents` / `knowledge_chunks` — curated knowledge (regulations,
  safety manuals, operational guides). `knowledge_chunks.embedding` is
  `vector(1536)` on PostgreSQL (created via `ALTER ... TYPE vector(1536)`
  because the pgvector SDK is **not** a dependency); an **HNSW** index
  (`vector_cosine_ops`) and an **FTS GIN expression index**
  (`to_tsvector('english', coalesce(content,''))`) are created there. SQLite
  keeps the Text column so the model stays portable.
- `marine_evidence` — durable evidence for every fact an agent asserts:
  `query_run_id`, `agent_name`, `tool_name`, `evidence_type`, `source`, coord,
  severity, confidence, JSON payload.
- Models in `app/db/models.py` (`KnowledgeDocument`, `KnowledgeChunk`,
  `MarineEvidence`). New head verified with `alembic heads`.

## 6. Evidence persistence (no-fabrication rule enforced)

`app/services/evidence_service.py`:

- `MarineEvidenceService.record(...)` — inserts one row from **real** fetched
  data only; best-effort (returns `-1` on failure, never raises into the
  response path). `list_for_run` / `count` for observability.
- `ToolRegistry.invoke` writes one evidence row per live `MarineDataResult`
  (when a registry-level evidence service is injected **and** `request_id` is
  present and real data was returned). The failure case is swallowed: evidence
  can never break a tool response.
- `MarineCapabilityClient` passes real rows to the service when `query_run_id`
  is provided (payloads strip `raw_payload` blobs).

## 7. Compliance matrix

| Rule | Where enforced |
|---|---|
| **Never fabricate data** | Adapters `not_configured`; agents fall back to clearly-labeled deterministic estimates + limitations; tools return `SOURCE_UNAVAILABLE` |
| **ML never overrides a hard constraint** | RiskEngine `_evaluate_hard_constraints` (level forced to `elevated`) |
| **No invented confidence/training/accuracy** | `confidence` records what the data layer actually computed / was stored |
| **Evidence = real rows only** | `MarineEvidenceService` writes what the services actually returned |
| **Additive tools only** | Existing 12 tools preserved; `restriction.*` added → 15 total |
| **No DB on unit tests** | All tests DB-free; DB-dependent flows use injected fakes |

## 8. Verification

- `python -m pytest tests -q` from repo root → **98 passed, 2 skipped**.
- New: `tests/test_marine_capability.py` (risk hard constraints, capability
  normalization, route/geofence/scenario live wiring), `tests/test_evidence.py`
  (evidence CRUD + invoke hook).

## 9. Next

- `MarineDataFusion` + canonical `MarineState`, analytics, hybrid RAG
  (pgvector `1 - cosine_sim` + FTS + rerank + citation), `marine.get_fused_state`,
  `knowledge.search`, `analytics.*` MCP tools (Phase 3).