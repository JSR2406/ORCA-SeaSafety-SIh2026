# Deployment Architecture

Deployment topology for everything behind the separately-hosted frontend.  The
Next.js UI (Vercel) talks only to the FastAPI gateway; every backend concern
below is owned by this repo's `apps/api` service.

> Supersedes the ARGO-era notes in `docs/architecture.md`.  `architecture.md`
> and `phase10-deployment.md` describe earlier single-process assumptions and
> are retained for history only.

## Logical flow (maps 1:1 to the system diagram)

```
Next.js UI (hosted separately: Vercel)
   |  REST + WebSocket (no business logic in UI)
   v
FastAPI request-path process (ONE container)
   REST/WS gateway
   -> Orchestrator (intent -> Planner -> Executor -> Verifier)
      -> MCP Tool Layer (tool bus + registry + run-id linkage)
      -> specialized agents (marine/weather/fisheries/safety/scenario/route/knowledge)
      -> Marine Data Fusion -> Geospatial Engine -> Risk Engine
      -> Verifier (every plan) -> Evidence & Provenance (best-effort persist)
      -> Response Synthesis (hybrid-RAG grounded, honest extractive fallback)
      -> ML inference (advisory; never overrides Risk Engine)
   -> shared Postgres pool (PostGIS + pgvector)
   -> shared object storage (read-only pull of artifacts/registry)
```

## Components

### 1. Frontend
- Host: Vercel (Next.js App Router).
- Consumes the FastAPI REST contract (`docs/api-contract.md`) and the WS channel
  (`docs/phase11-event-model.md`). Authoritative frontend↔backend reference:
  `apps/web/BACKEND_INTEGRATION.md`.
- No direct database, storage, or ML access.
- Env: `NEXT_PUBLIC_API_URL` must point at the deployed API origin
  (default `http://localhost:8000`).
- CORS: the deployed frontend origin MUST be added to `CORS_ORIGINS` on the
  backend (default allowlist is only `http://localhost:3000`); miss it and every
  browser request is blocked at the browser.
- Bootstrap: UI calls `GET /api/v1/contract` + `GET /api/v1/health` and gates
  input on `GET /api/v1/ready`.

### 2. FastAPI request-path container (the "server")
Everything that a chat turn touches lives in one well-typed process so request
scope, the tool bus request-id, and evidence runs stay consistent:

- `app/orchestration/` - intent detection, planner, executor, validator,
  orchestrator (writes one `orchestration_run` evidence row per run).
- `app/mcp/` - MCP tool layer (registry + bus); tools may declare `query_run_id`.
- `app/agents/` - specialized domain agents composing tools per intent.
- `app/fusion/` + `app/geo/` - marine data fusion, geospatial queries (PostGIS).
- `app/risk/` - Risk Engine (highest authority; ML output never overrides it).
- `app/verifier/` - attached to **every** plan; validates agent outputs.
- `app/rag/` - hybrid retrieval (FTS + embeddings) with grounded answer layer.
- `app/ml/` - ModelService (advisory), registry, drift, feature store, ledger.

The request path is kept free of long-running jobs on purpose.  Heavy work goes
to the workers container, never to a user-facing request.

### 3. Workers container (background jobs)
Shares the same codebase image, different entrypoint:

- Source ingestion / polling (INCOIS, MOSDAC, IMD, NHO, coastal fallbacks,
  mock sources) into Postgres.
- ARGO intake normalization (**supersedes the old ARGO-workers design**).
- RAG document/embedding job into pgvector.
- `scripts/train_models.py` for supervised model training -> artifacts +
  registry candidates.
- Retrain watchdog (gated on `ml_retrain_min_ground_truth` = 30 validated rows).
- `get_governance_engine()` / `get_model_registry()` singletons run here and in
  the request container; both persist state to object storage-backed files.

### 4. Managed PostgreSQL (PostgreSQL + PostGIS + pgvector)
- PostGIS for geospatial queries (fleet position, PFZ hulls, proximity).
- pgvector for RAG embeddings.
- Evidence/provenance rows, query runs, alerts, observations.
- SQL is the system of record for operational data; ML state is file-backed
  (see below).

### 5. Object storage
- ML artifacts (`data/ml/artifacts/*.joblib`).
- Registry snapshot `registry.json`.
- Ledger snapshot `ledger.json` and feature-store snapshot `feature_store.json`.
- ARGO/document uploads, advisory PDFs.

## Durable state today

| State | Where it lives | Persistence |
| --- | --- | --- |
| Operational data / evidence / runs | Postgres (SQL) | DB-backed, transactional |
| RAG chunks + embeddings | pgvector | DB-backed |
| Model registry | `data/ml/registry.json` | Snapshot file, loader singleton |
| Prediction ledger + outcomes | `data/ml/ledger.json` | Snapshot file, written on every record/match/validate |
| Feature store | `data/ml/feature_store.json` | Snapshot file, written on location-keyed puts |
| Trained model artifacts | `data/ml/artifacts/` | Fitted estimator files |

All persistence is **best-effort and never fatal**: a missing or corrupt
snapshot yields a fresh in-memory state (observed through unit tests), matching
the system's "honest states" policy.

## Scale path (documented, not yet implemented)

- Replace ledger/feature-store JSON snapshots with Postgres tables (or Redis)
  once write volume exceeds single writes per prediction.
- Add a message queue between the request container and workers so ingestion
  backpressure cannot stall a chat turn.
- Multi-instance request container behind a load balancer; WS channel stays on
  the same instance per session (sticky).

## Deployment invariants

- Never fabricate source data: unconfigured/unreachable sources report honest
  `NOT_CONFIGURED` / `UNAVAILABLE` states; TEST-MOCK sources are labelled.
- ML serving fails closed (MODEL_UNAVAILABLE / INPUT_DATA_UNAVAILABLE /
  PREDICTION_UNCERTAIN) rather than invent confidence.
- Only VALIDATED ground truth enters training data.
- Risk Engine output is never overridden by ML output.