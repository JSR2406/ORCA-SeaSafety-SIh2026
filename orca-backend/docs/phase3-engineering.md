# Phase 3 Architecture Report

Floor/extension work on top of `phase2-architecture.md`: a canonical fused
marine state (`MarineDataFusion` + `FusedMarineState`), a descriptive-only
analytics layer, a hybrid RAG retrieval layer (PostgreSQL FTS + optional
pgvector), and four new decision-support MCP tools. All additive; existing APIs
and the pre-existing test suite were preserved.  The governing rule remains the
same as Phases 1-2: **the system never fabricates marine data, ML quality
claims, or retrieval that did not actually happen.**

## 1. Fused marine state

`app/services/marine_fusion.py`:

- `FusedMarineState` — canonical view of the environment at one point and time:
  `lat/lon`, `requested_at`, `data_time`, `status`, `sources`, `variables`,
  `providers` (per-variable `{source, source_record_id, observation_time}`
  provenance), `confidence`, `missing`, `limitations`.
- `MarineDataFusion.fused_state(lat, lon, ...)` — fetches real ocean + weather
  observations from `MarineDataService` and **first-wins** merges them across
  the two expected variable sets (`OCEAN_VARIABLES`, `WEATHER_VARIABLES`).
  A variable appears in `variables` **only** when a real stored row provided it;
  otherwise it lands in `missing` and the state records which provider was
  unavailable in `limitations`.
- `status` is adjudicated from the constituent `MarineDataResult`s (live >
  recent > stale), and is `not_configured`/`unavailable`/`error` when there is
  nothing real to fuse. `confidence` averages only confidences the data layer
  actually computed.
- Singleton `get_marine_data_fusion()`; also exposed through
  `MarineCapabilityClient.fused_state()` (which adds evidence recording + the
  `available`/`error` fields for the agent seam).

## 2. Analytics (descriptive only, never predictive)

`app/services/analytics.py`:

- `descriptive_stats(rows, fields)` — count/mean/std/min/max per numeric field.
  Pure statistics of supplied rows; no forecasts, no fitted distributions.
- `favorability_index(state, target)` — fishing / transit sensitivity bands with
  a *transparent* weighted score and a per-variable `rationale`.
  If fewer than `ceil(len(bands)/2)` of the target's inputs are present in the
  fused state, `available=False` and `score=None` — a score is **never**
  invented from missing data.
- `risk_profile(state, warnings, restrictions)` — delegates to
  `RiskEngine` thresholds; active restrictions/warnings still force `elevated`
  with `HARD CONSTRAINT:` reasoning (Phase 2 rule preserved).
- `scenario_comparison(states)` — descriptive per-variable min/max/range across
  candidate scenarios.

## 3. Hybrid RAG (honest retrieval)

`app/services/knowledge_rag.py`:

- `KnowledgeChunkStore.search_fts` — PostgreSQL `to_tsquery('english', ...)`
  + `ts_rank_cd` over the FTS GIN expression index (migration `0f7e1a2b3c4d`),
  joined to document metadata; portable `ilike` fallback for other dialects.
- `KnowledgeChunkStore.search_vector` — raw SQL `1 - (embedding <=> :qvec)`
  against the `vector(1536)` column; PostgreSQL-only and guarded.
- **Embeddings are opt-in, never assumed:** `OpenAICompatibleEmbedder`
  activates only when `EMBEDDINGS_API_KEY`/`EMBEDDINGS_ENDPOINT` are set
  (new settings + `.env.example` entries). Default is
  `NotConfiguredEmbedder` → retrieval reports `mode: "fts_only"` and
  `search_vector` is never called (no fake vectors, no fake pipeline).
- `KnowledgeRagService.retrieve(query)` returns `RetrievalResult` with `mode`
  (`hybrid` when both a real embedding and real vector rows were produced,
  else `fts_only`), an honest `note`, ranked `chunks` and verbatim `citations`
  (title + source_url + text excerpt). Reranking is a **documented heuristic**
  (0.7·ts_rank + 0.3·cosine when vector real, plus a query-token coverage
  bonus) — deliberately not an unsupported ML reranker.

## 4. New MCP tools (+4 → 19 total)

| Tool | Group | Safety | Backing |
|---|---|---|---|
| `marine.get_fused_state` | marine | read-only | `MarineCapabilityClient.fused_state` |
| `knowledge.search` | knowledge | read-only | `KnowledgeRagService.retrieve` |
| `analytics.descriptive_stats` | analytics | read-only | `AnalyticsService.descriptive_stats` |
| `analytics.favorability` | analytics | decision-support | `AnalyticsService.favorability_index` over the real fused state |

Wired in `app/mcp/register.py` (`tools_decision.register(...)`). All enforce the
existing envelope/coercion/error conventions and accept `query_run_id` where an
evidence hook applies.

## 5. Unification and hygiene

- Single `AsyncSessionFactory` remains `app/db/client.py` (`get_session` +
  `async_session_maker`); both `MarineEvidenceService` and `PgChunkStore`
  default to it and accept an injected factory for tests.
- No DB engine/session factories exist outside `app/db/client.py`.

## 6. Compliance matrix (extended)

| Rule | Where enforced |
|---|---|
| Never fabricate data | Fusion records only real rows; analytics scores only when enough real inputs exist; RAG reports `fts_only` when no real embeddings configured |
| ML never overrides a hard constraint | `AnalyticsService.risk_profile` → RiskEngine hard-constraint guard |
| No invented confidence/training/accuracy | `FusedMarineState.confidence` averages owned real confidences only; RAG rerank is a documented lexical heuristic, not an ML claim |
| Additive tools only | 12 → 15 (Phase 2) → **19** with Phase 3 |
| No DB on unit tests | Fusion/analytics/RAG/decision-tool tests all DB-free (injected fakes) |

## 7. Verification

- `python -m pytest tests -q` from repo root → **135 passed, 2 skipped**.
- New suites: `tests/test_marine_fusion.py` (9), `tests/test_analytics.py`
  (15), `tests/test_knowledge_rag.py` (7), Phase 3 tool coverage in
  `tests/test_mcp_unit.py`.

## 8. Next

- Document ingestion into `knowledge_chunks`/`knowledge_documents`
  (chunker + re-embed pipeline behind an explicit admin action); FTS-only mode
  already provides value without an embeddings provider.