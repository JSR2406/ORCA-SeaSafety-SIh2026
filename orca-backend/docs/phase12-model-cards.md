# Model Cards — Phase 12 Production ML Models

All Phase 12 models are **deterministic, threshold/documentation-driven**, requiring no external training infrastructure. Each returns a `Prediction` with a point `value`, `uncertainty` (0..1), `provenance`, `missing_inputs`, and an honest status. They are **advisory only** and never override the Risk Engine or hard restrictions.

## 1. `pfz` — Potential Fishing Zone favorability

| Field | Value |
|-------|-------|
| Version | `1.0.0` (PRODUCTION) |
| Inputs | `sst_c`, `chlorophyll` (both required) |
| Output | Favorability score 0..1 (higher = more favorable) |
| Urgency | Rule/domain-driven |
| Uncertainty | Coverage- and conflict-derived; rises when SST/pigment disagree |
| Failure | `INPUT_DATA_UNAVAILABLE` if either input missing → value `None` |
| Safety | **Not a catch forecast.** Satellite-inferred habitat favorability only. |

Reference: warm SST + elevated chlorophyll → higher PFZ favorability, with `_edge_penalty` dampening extreme/near-bound values and `_bounded_01` clamping output.

## 2. `risk` — Environmental risk proxy

| Field | Value |
|-------|-------|
| Version | `1.0.0` (PRODUCTION) |
| Inputs | `wave_height_m`, `wind_speed_ms` (both required); `current_speed_ms` augments confidence |
| Output | Risk proxy 0..1 (higher = riskier) |
| Adversarial | **Max** of wave and wind components (and current when present), never averaged down |
| Urgency | High when any component is extreme |
| Failure | `INPUT_DATA_UNAVAILABLE` if wave or wind missing |
| Safety | **Advisory only.** The Risk Engine is authoritative; this never lowers a hard restriction. An extreme proxy cannot appear as a "safe" verdict. |

## 3. `productivity` — SRP (Surface Related Production) proxy

| Field | Value |
|-------|-------|
| Version | `1.0.0` (PRODUCTION) |
| Inputs | `sst_c`, `chlorophyll` (both required) |
| Output | Productivity proxy 0..1 |
| Urgency | Biological-activity derivation |
| Failure | `INPUT_DATA_UNAVAILABLE` if either input missing |
| Safety | Satellite-inferred proxy; **not a catch forecast**. |

## 4. `forecast` — Bounded scenario forecast

| Field | Value |
|-------|-------|
| Version | `1.0.0` (PRODUCTION) |
| Inputs | `sst_c`, `chlorophyll` (baseline) |
| Output | Series over `ml_forecast_horizon_days` (7) at `STEP_HOURS` (6) steps |
| Uncertainty | **Honestly widens per step** — later horizon steps carry growing uncertainty, so the model is explicitly less certain far from the baseline |
| Failure | `INPUT_DATA_UNAVAILABLE` if baseline missing |
| Safety | Scenario/bounded; not authoritative for any live decision. |

## 5. Shared guarantees

- **Provenance** on every prediction: model name, model version, feature version.
- **Never impute** a missing feature; produce `None` + `INPUT_DATA_UNAVAILABLE` instead.
- **Never auto-propagate** to live/alarm state; the proactive engine's material-change gate (Phase 11 `ingest_ml_score`) decides alert churn independently.
- All outputs pass `_clamp01` / `_bounded_01`; out-of-range inputs are clamped, not extrapolated.