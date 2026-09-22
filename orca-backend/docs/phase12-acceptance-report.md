# Phase 12 — Acceptance Report: Production ML, Forecasting & MLOps

## 1. Scope delivered

Brings the platform's ML/MLOps layer to production parity with the Phases 1–11 services:

- **Feature pipeline** — `FeatureStore`: deterministic, versioned `_NORM` normalisation; missing values never imputed; bounded/LRU store with provenance.
- **Model registry** — `ModelRegistry` + `ModelStage`: candidate → validated → production → rollback → deprecated; bounded candidate window; promotion gated on validation.
- **ML models** — `PFZModel`, `RiskModel` (adversarial max), `ProductivityModel`, `ForecastModel` (widening per-step uncertainty); `Prediction` dataclass with `value / label / uncertainty / provenance / missing_inputs / meta`.
- **Model service** — `ModelService`: auto-seed of production registry (gated on `ml_enabled`), transitive failure modes, bounded TTL cache, drift recording, `status()`; `reset_model_singletons` for test isolation.
- **Drift detection** — `DriftDetector`: PSI-style, warmup-gated, threshold-based, bounded alarm log.
- **MCP surface** — 5 READ_ONLY `analytics.*` tools (`pfz_predict`, `risk_predict`, `productivity_predict`, `forecast_predict`, `model_registry`) registered by `build_tool_registry()`.
- **Config** — full Phase 12 settings block; Pydantic `protected_namespaces` fixed for `model_*` fields.

## 2. Honesty & safety invariants (verified)

- [x] ML never overrides the Risk Engine or hard restrictions.
- [x] Insufficient inputs → `None` value + `INPUT_DATA_UNAVAILABLE`, never fabricated.
- [x] No production model → `MODEL_UNAVAILABLE`, never a guess.
- [x] Uncertainty above threshold → `PREDICTION_UNCERTAIN` surfaced, not hidden.
- [x] Cached results are live/stale-stamped (`from_cache`), never the safety source of truth.
- [x] Adversarial risk uses max, never averages risk components down.
- [x] Forecast uncertainty honestly widens with horizon.

## 3. Verification evidence

- **Unit/behavior tests**: `tests/test_phase12_ml.py` — **22 passed** (feature store, registry lifecycle/rollback/bound, models, service failure modes, cache, drift, MCP registration + invoke, Phase 11–12 `ingest_ml_score` material-change gate).
- **Import/seed smoke test**: model service seeds all 4 production models; `pfz`/`forecast`/`risk` predict `OK` with real values.
- **App boot**: `app.main` imports cleanly; tool registry builds **29 tools** including the 5 `analytics_model`; `analytics.model_registry` invoke returns live status.

### Status taxonomy observed

| Status | Trigger exercised |
|--------|-------------------|
| `OK` | valid inputs, uncertainty in budget |
| `INPUT_DATA_UNAVAILABLE` | missing chlorophyll → pfz value `None` |
| `MODEL_UNAVAILABLE` | unseeded dedicated registry |
| `PREDICTION_UNCERTAIN` | uncertainty threshold forced tight |

## 4. Files added/changed

**New**: `app/ml/{features,registry,models,drift,service}.py`, `app/ml/__init__.py`, `app/mcp/tools_analytics_model.py`, `tests/test_phase12_ml.py`, `docs/phase12-{feature-pipeline,model-registry-and-safety,model-cards,acceptance-report}.md`.

**Changed**: `app/mcp/register.py` (register analytics_model tools), `app/config.py` (Phase 12 settings + `protected_namespaces`).

## 5. Notes & follow-ups

- Models are intentionally deterministic (no runtime training infra); a future phase may layer learned models onto the same registry/service seam.
- `ModelRegistry` shared singleton is auto-seeded on first `get_model_service()` access when `ml_enabled`; tests use dedicated registries for isolation.
- Next: full Phase 12 regression (pytest + eval harness), regenerate reports, then commit/push.