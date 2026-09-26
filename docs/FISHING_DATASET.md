# FISHING DATASET (Phase 4)

Binary target first: `0 = unsuitable`, `1 = potentially suitable` (suitability = predicted probability, never "fish definitely here").

## Inputs
INCOIS PFZ advisories (primary labels: lat/lon/depth/distance/sector) + SST + chlorophyll + wind + currents + waves + bathymetry + location + time/season. Global Fishing Watch = optional activity context, never ground truth.

## Pipeline
`collect.py` (labels + gateway features, FEATURE TIME ≤ LABEL TIME) → `preprocess.py` (drop rows missing both sst+chlorophyll, coord rounding, dedup, median impute + `_imputed` flags) → `dataset.py` (background negatives ≥0.5° buffer, time split, parquet + manifest).

## Splits (no random-only validation)
Default: train 2019–2023, valid 2024, test 2025. Demo flag allows small ranges. Rationale: neighbors/dates correlate; future prediction is the real test. Spatial grouping recommended for tight coastal grids.

## Features (must match `FishingFeatureVector` exactly)
`lat, lon, sst_c, chlorophyll, wind_speed_ms, wind_direction_deg, current_speed_ms, current_direction_deg, wave_height_m, depth_m, distance_from_coast_km, month, season_idx, hour` → `target`.

## Outputs
`ml/data/processed/fishing_training_{train,valid,test}.parquet` (CSV fallback) + `manifest.json` (counts, files, guards). Artifacts git-ignored except manifest.

## Leakage guards
1. No PFZ-derived feature in inputs. 2. No future observations. 3. Negatives buffered, never adjacent cells. 4. Time split + spatial grouping. 5. Every row carries `label__source` + per-field `__source` + `_provenance`.
