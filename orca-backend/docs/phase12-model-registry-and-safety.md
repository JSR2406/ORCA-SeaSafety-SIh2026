# Phase 12 — Model Registry & Safety

## 1. Model lifecycle (`app/ml/registry.py`)

`ModelRegistry` manages versions through explicit stages so a production model is always identifiable, promotable only after validation, and rollback-able to the last known good.

Stages (`ModelStage`):

| Stage         | Meaning                                           |
|---------------|---------------------------------------------------|
| `CANDIDATE`   | Registered, not yet validated                     |
| `VALIDATED`   | Passed an explicit validation gate (coverage etc.)|
| `PRODUCTION`  | Currently selected for live inference (one per name)|
| `DEPRECATED`  | Superseded or evicted; kept for provenance        |

Operations:

- `register(name, version, card)` — adds a candidate.
- `validate(name, version, metrics)` — moves candidate → validated; **required before promotion** (promoting an unvalidated model raises `ValueError`).
- `promote(name, version)` — validates then sets the production model; records `previous_production` for rollback.
- `rollback(name)` — restores the previous production model.
- `deprecate(name, version)` — moves a model to `DEPRECATED`.
- `list / production_version` — introspection.

**Bounded candidate window**: `model_registry_max_candidates` caps how many candidates are retained; brands evicted oldest candidates `DEPRECATED` rather than silently dropping provenance.

Default production models are seeded by `ModelService.seed_registry()` (register → validate → promote), gated on `settings.ml_enabled`:

| Model name     | Version | Stage          |
|----------------|---------|----------------|
| `pfz`          | `1.0.0` | PRODUCTION     |
| `risk`         | `1.0.0` | PRODUCTION     |
| `productivity` | `1.0.0` | PRODUCTION     |
| `forecast`     | `1.0.0` | PRODUCTION     |

## 2. Model service (`app/ml/service.py`)

`ModelService` binds the feature store, registry, drift detector, and a bounded TTL cache, and is the single entry point for predictions.

### 2.1 Failure modes (transitive, never mis-labeled as confident)

Every `predict()` returns a `ModelResult` with a status:

| Status                   | Meaning                                                  |
|--------------------------|----------------------------------------------------------|
| `OK`                     | Confident, within uncertainty budget                     |
| `MODEL_UNAVAILABLE`      | No production model for the requested name               |
| `INPUT_DATA_UNAVAILABLE` | Required features missing → value is `None`              |
| `PREDICTION_UNCERTAIN`   | Uncertainty exceeds `ml_uncertain_confidence_threshold`  |

`MODEL_UNAVAILABLE` and `INPUT_DATA_UNAVAILABLE` always carry a `None` value; they never fabricate.

### 2.2 Provenance

Every result carries `provenance` with at least the `model` name, `model_version`, and feature `version`, so the exact pipeline that produced a value is reconstructable.

### 2.3 Bounded caching

- `cache_ttl_seconds` (300) / `cache_max_entries` (256) bound the cache; LRU-style eviction under a hard cap.
- A cached hit is flagged `from_cache`; `force=True` bypasses. Cached results are live/stale-stamped, never the source of truth for safety.

### 2.4 Drift detection

`DriftDetector` (`app/ml/drift.py`) computes a PSI-style comparison over feature distributions:

- **Warmup-gated**: only once `ml_drift_warmup_samples` (50) are observed per model does drift reporting begin.
- **Threshold-based**: drift past `ml_drift_threshold` (0.30) records an alarm in a bounded ring buffer (`recent_alarms`, `alarm_count`).
- **Never reactive**: drift alarms inform `status()`; they do not silently change safety verdicts.

## 3. Safety hierarchy (immutable)

```
LIVE HARD CONSTRAINT  (highest)
  > RISK ENGINE
  > VERIFIER
  > ML  (advisory, THIS phase)
  > RAG / KNOWLEDGE
  > LLM SYNTHESIS  (lowest)
```

- ML never transforms UNKNOWN into SAFE.
- ML never overrides a hard restriction or Risk Engine verdict.
- ML outputs are advisory decision-support; the Risk Engine remains authoritative.

## 4. MCP surface (`app/mcp/tools_analytics_model.py`)

Registered in `build_tool_registry()` (group `analytics_model`, READ_ONLY):

| Tool                          | Purpose                                        |
|-------------------------------|------------------------------------------------|
| `analytics.pfz_predict`       | PFZ favorability 0..1 + uncertainty + provenance|
| `analytics.risk_predict`      | Adversarial environmental risk proxy 0..1      |
| `analytics.productivity_predict` | SRP productivity proxy 0..1                 |
| `analytics.forecast_predict`  | Bounded scenario series (horizon, widening uncertainty)|
| `analytics.model_registry`    | Registry / feature-store / drift / cache status |

Every tool returns the transitive failure status so callers can never mistake an unavailable or uncertain result for a confident one. Tool fns accept `lat`/`lon` structurally but feed only `variables` to the service.

## 5. Configuration (`app/config.py`)

Added: `features_cache_hours`, `ml_enabled`, `model_registry_max_candidates`, `ml_cache_ttl_seconds`, `ml_cache_max_entries`, `ml_forecast_horizon_days`, `ml_drift_warmup_samples`, `ml_drift_threshold`, `ml_drift_ttl_seconds`, `ml_default_confidence`, `ml_uncertain_confidence_threshold`. Pydantic `protected_namespaces` set to `("settings_",)` so `model_*` fields are first-class.

## 6. Files

- `apps/api/app/ml/registry.py`, `service.py`, `drift.py`, `features.py`, `models.py`, `__init__.py`
- `apps/api/app/mcp/tools_analytics_model.py`, `apps/api/app/mcp/register.py`
- `apps/api/app/config.py`