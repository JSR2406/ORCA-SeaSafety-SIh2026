# Phase 12 — Production ML, Forecasting & MLOps (Feature Pipeline)

## 1. Context

Phase 11 delivered real-time proactive marine intelligence and autonomous alerting by fusing live observations. Phase 12 productionizes the ML/forecasting side of the platform: a deterministic, honest, bounded feature pipeline feeding an MLOps-grade model lifecycle — registry, stage promotion, rollback, drift detection, and bounded caching — exposed as advisory-only `analytics.*` MCP tools.

Design constraints honoured throughout:

- **ML is advisory, never authoritative.** Predictions cannot override the Risk Engine, the Verifier, or LIVE HARD CONSTRAINTS.
- **Never fabricate.** Insufficient inputs produce a `None` value plus an explicit failure status, not a made-up number.
- **No external training infra.** Models are deterministic, threshold/documentation-driven with a bounded skill ceiling, so the system is reproducible and auditable offline.
- **Preserve phases 1–10.** This adds a new `app/ml/` package and tool group; no existing module is rewritten.

## 2. Feature pipeline (`app/ml/features.py`)

`FeatureStore` is the single boundary between raw observation variables and models. It is **versioned**, **bounded**, and **deterministic**.

### 2.1 Extraction (`extract`)

- Applies `_NORM` — a per-feature deterministic min–max normaliser into `[0, 1]` — producing a `normalized` dict.
- Records `present` (features that had a non-`None` value), `missing` (absent/`None`), and `version`.
- **Never imputes.** A missing feature is reported as missing; models must gate on it.

### 2.2 Store (`put` / `get` / `stats`)

- `put` snapshots a feature row keyed by caller, stamped with the current feature `version`, so a stored row is always traceable to the normalisation version that produced it.
- LRU-style eviction enforces a hard `max_entries` cap; `stats()` reports `rows`, `total_present_features`, `retention_hours`, and `version`.

### 2.3 Versioning

- `FEATURES_V1 = "1.0.0"` is the active normalisation contract.
- Changing the normalisation bumps the version; stale stored rows remain readable but are tagged with their original version (provenance preserved).

## 3. Feature contract

| Feature         | Required by models              | Notes                                  |
|-----------------|---------------------------------|----------------------------------------|
| `sst_c`         | pfz, productivity, forecast     | satellite/in-situ sea-surface temp     |
| `chlorophyll`   | pfz, productivity, forecast     | pigment proxy for biological activity  |
| `wave_height_m` | risk                            | significant wave height                |
| `wind_speed_ms` | risk                            | surface wind speed                      |
| `current_speed_ms` | risk (augments)              | adds confidence when present            |

## 4. Honesty and safety

- Deterministic min–max bounds are static and documented; out-of-range inputs are **clamped**, not extrapolated (see model pipeline).
- Missing inputs are surfaced as `missing_inputs` on every prediction so callers know exactly why a value may be absent.
- Normalisation is stateless per call — no hidden corpus, no leaky global state.

## 5. Files

- `apps/api/app/ml/features.py` — `FeatureStore`, `get_feature_store()`, `reset_model_singletons`.
- `apps/api/app/ml/__init__.py` — package exports.