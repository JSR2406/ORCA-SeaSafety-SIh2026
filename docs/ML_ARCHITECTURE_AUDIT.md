# ORCA ML Architecture Audit

> Generated: 2026-09-26. Read-only audit — no production code modified.
> Goal: extend existing ORCA architecture toward specialized ML + Deterministic Risk Engine, per approved design (XGBoost fishing/risk, Isolation Forest anomaly, A* route, PostGIS geofence, SHAP evidence).

## 1. Frontend architecture (`orca-frontend/src/`)

- Next.js App Router (`src/app/*/page.jsx`): `dashboard, fishing, safety, routes, scenarios, marine-map, ml-governance, analytics, ai-copilot, alerts, knowledge, system-health, workflow`.
- Views layer (`src/views/*.jsx`): `FishingIntelligencePage, SafetyCenterPage, RoutePlannerPage, ScenarioLabPage, MLGovernancePage` — primary ML consumers.
- Service layer (`src/services/apiClient.js`): single gateway. Consumes `ml_scores` from `/api/v1/chat` (line ~152), mocks fallback for `risk/briefing`, `route/analyze`, `ml/dashboard`, `marine/pfz`, `scenarios/create`. `forecastEntries` currently defaults to `[]` — **ForecastModel output not wired**.
- Reuse: keep `apiClient.js` as the only fetch layer; add new callers (`/ml/fishing/predict`, `/ml/risk/predict`, `/route/optimize`, `/risk/evaluate`) here later.

## 2. FastAPI backend (`orca-backend/`)

- Entry: `main.py` → `api/server.py` (FastAPI + CORS) → `api/routes.py` (all endpoints, prefix `/api/v1`).
- Existing endpoints (all live in `api/routes.py`):
  - `POST /query`, `POST /chat` — **only endpoint that touches real ML** (via LangGraph). Rest are static mocks.
  - `GET /marine/ocean|weather-forecast|tides|pfz`, `GET /alerts`, `GET /datasets/status`, `GET /ml/dashboard`
  - `POST /risk/briefing` (hardcoded `0.42`), `POST /route/analyze` (hardcoded `route-b`), `POST /scenarios/create` (hardcoded `0.92`)
- Config: `core/config.py` (pydantic-settings, `.env`: Supabase + OpenRouter + LangSmith). No ML registry/env vars yet.
- Reuse: extend `api/routes.py` additively; add `core/config.py` fields for model paths/versions later.

## 3. Database schema (`database/`)

- `database/client.py`: Supabase client from settings. `database/postgis.py::check_spatial_risk(lat,lon)` — **mocked** (`lat>20 → 0.8 else 0.1`, RPC commented out).
- No tables created by backend code; no migrations folder. RAG RPC `match_documents` and spatial RPC `calculate_spatial_risk` are commented-out stubs.
- Missing (per spec §37): `marine_observations, marine_forecasts, pfz_advisories, weather_alerts, geofences, protected_areas, model_predictions, model_versions, risk_decisions, route_results, evidence_records`.
- Files to reuse: `database/client.py`, `database/postgis.py` (replace mock with real `ST_Contains/ST_Intersects/ST_DWithin` queries).

## 4. Existing agents (`agents/` + `graph/`)

- LangGraph workflow (`graph/workflow.py`): `START → router_node → [live_data|rag|geospatial] → ml_node → generation_node → END`. Simple intent skips to generation.
- `agents/router.py`: heuristic + Nemotron LLM fallback (OpenRouter). Keep.
- `graph/nodes.py::live_data_node`: **hardcoded** `wind 8.4kts / wave 1.4m / sst 28.4`. No INCOIS/IMD/Open-Meteo fetch.
- `graph/nodes.py::ml_node`: **real integration point** — converts knots→m/s, injects `chlorophyll 0.88`, calls `predict_marine_models()`, maps risk→`Risk`, pfz→`FishingSuitability`, uncertainty→`RiskEscalation`. Discards `productivity` + `forecast` outputs.
- `agents/geospatial.py` → mocked PostGIS. `agents/rag.py` → mocked single IMD doc, embedding step TODO. `agents/generator.py` → Nemotron generation + `synthesize_marine_knowledge()` fallback that reads `state.risk/fishing/ocean/weather`.
- Reuse all nodes; add `risk_engine` decision step between `ml_node` and `generation_node` later.

## 5. Existing RAG implementation

- `agents/rag.py`: direct query passthrough, Supabase `match_documents` RPC commented out, returns mock doc only when `intent==complex`. No embeddings, no chunking, no pgvector table.
- Target (spec §45): RAG = advisories/rules evidence only; never risk prediction. Needs `documents/chunks/embeddings → pgvector → evidence` pipeline. Keep file, implement retrieval for real.

## 6. PostGIS / pgvector usage

- PostGIS: only `check_spatial_risk()` mock. No polygons loaded (EEZ/MPA/restricted zones per spec §17-18: Marine Regions + Protected Planet → GeoJSON → PostGIS).
- pgvector: dependency present (`requirements.txt`), no table/RPC live.
- Files to reuse: `database/postgis.py`; create `ml/risk_engine/geofence.py` as rule wrapper around it.

## 7. Existing data ingestion

- None. `live_data_node` static; `/datasets/status` claims `live` for INCOIS/IMD/Open-Meteo/NAVAREA/MOSDAC but performs no fetch. No scheduler, cache, or `data_pipeline/` folder.
- Target (spec §19/27/38): `data_pipeline/{incois.py, imd.py, pfz.py, weather.py}` adapters with timeout/retry/validation + normalized schema (`source, retrieval_time, valid_time, lat, lon, quality`), scheduler → Postgres → cache → API. Open-Meteo = dev fallback only, always labeled.

## 8. Existing ML code (`ml/`)

- `ml/models.py` (217 lines): `PFZModel, RiskModel, ProductivityModel, ForecastModel` (all `_Model v1.2.0`, deterministic threshold math) + `Prediction` dataclass + `predict_marine_models()`. This is the **deterministic baseline**, not trained XGBoost.
- `ml/__init__.py`: empty. `ml/README.md`: claims XGBoost/LightGBM/GeoPandas/joblib — aspirational, not implemented.
- `requirements.txt` already lists `xgboost, lightgbm, geopandas, scikit-learn, joblib, httpx` — no `pandas, numpy, shap, xarray` yet.
- Status per component:

| Spec component | Current | Missing |
|---|---|---|
| Fishing XGBoost | PFZ threshold stub | dataset, train, benchmark, SHAP, registry |
| Risk XGBoost | wave/wind/current stub | dataset, train, calibration, thresholds |
| Anomaly (Isolation Forest) | absent | module + features |
| Route A*/Dijkstra | hardcoded route-b | `ml/route/` optimizer + cost |
| Deterministic Risk Engine | `RiskEscalation` trend only | `ml/risk_engine/` HARD_RESTRICTION…UNKNOWN + overrides |
| SHAP evidence | absent | per-prediction drivers |
| Cyclone/lightning models | correctly absent (use IMD/official feeds) | feed adapters only |
| Geofence | mock | real polygons + queries |

## 9. Existing API endpoints — reuse vs create

- Reuse (extend to call real ML): `/chat`, `/risk/briefing`, `/route/analyze`, `/marine/*`, `/ml/dashboard`, `/scenarios/create`.
- Create (spec §35): `POST /ml/fishing/predict`, `POST /ml/risk/predict`, `POST /route/optimize`, `POST /risk/evaluate` — thin wrappers over `ml/*/predict.py` + `risk_engine/decision.py`, returning prediction + SHAP drivers + evidence.
- `OrcaState` (`schemas/state.py`) needs additive fields: `productivity, forecast_horizon, risk_decision, evidence` — keep `fishing/risk/risk_escalation/route` names stable for frontend.

## 10. Environment variables

- Present: `SUPABASE_URL, SUPABASE_SERVICE_KEY, OPENROUTER_API_KEY, ORCA_ROUTER_MODEL, ORCA_GENERATOR_MODEL, LANGCHAIN_*`.
- Missing: `INCOIS_*`, `IMD_API_KEY/BASE`, `OPENMETEO_BASE` (fallback flag), `ML_MODEL_DIR, FISHING_MODEL_VERSION, RISK_MODEL_VERSION`, `POSTGIS_*` (if separate), scheduler toggles. All new vars must be optional with safe defaults.

## 11. Deployment

- Backend: `uvicorn main:app --reload` port 8000. Frontend: Next.js port 3000, `supervisor.conf`. No Dockerfiles, no CI, no model-artifact storage. `verify_all_endpoints.py` hits 12 endpoints (expects 200s).
- Plan: local-first training (`ml/*/train.py` → `models/<domain>/vN/`), artifacts git-ignored except `metadata.json`/`features.json`; registry table `model_versions` in Supabase.

## 12. Files to reuse vs create (foundation step only)

- Reuse untouched: `ml/models.py` (baseline), `graph/nodes.py`, `api/routes.py`, `schemas/state.py`, `database/*`, `agents/*`.
- Create now (no training, schemas + tests only):
  - `ml/common/{schemas.py,metrics.py}` — `MarineObservation, MarineForecast, FishingFeatureVector, RiskFeatureVector, ModelPrediction, EvidenceRecord`
  - `ml/fishing/{features.py,predict.py,train.py,evaluate.py}` + `ml/risk/*` (stubs w/ time-split + metric contract)
  - `ml/route/{graph.py,cost.py,optimizer.py,constraints.py}`, `ml/risk_engine/{rules.py,decision.py,geofence.py}`
  - `ml/anomaly/{features.py,predict.py}` (Isolation Forest stub)
  - `data_pipeline/{base.py,incois.py,imd.py,pfz.py,weather.py}` (adapter contract: timeout/retry/validate/normalize + source labels)
  - `ml/data/{raw,processed,features}/.gitkeep`, `models/{fishing,risk}/.gitkeep`, `reports/.gitkeep`
  - `tests/test_ml_schemas.py`, `docs/FISHING_DATASET.md` (placeholder contract)
- Do NOT yet: retrain on live data, random-split validation, hardcoded ensemble weights, neural route planner, custom cyclone model, silent fallback substitution.
