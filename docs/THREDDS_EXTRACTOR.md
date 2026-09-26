# INCOIS THREDDS Deep Extractor (open-source, keyless)

`ml/data_pipeline/scrapers/incois_thredds.py` pulls authoritative forecast grids
straight from INCOIS's public THREDDS catalog — no API key, no browser, no paid tool.

## How it was found
OSF WebGIS (`osfforecast.jsp`) is a Leaflet/WMS map: its HTML holds only region
dropdowns. Its JS references per-timestamp JSON + a public THREDDS catalog at
`https://incois.gov.in/thredds/catalog/osf/{wave,winds,currents,sst,chl}/` with
daily NetCDFs and `NetcdfSubset` (NCSS) point-query access. GeoServer `/geoserver/ows`
is 403 from outside; THREDDS is open.

## Coverage (verified 2026-09-26)
| Group | File pattern | Vars | Status |
|---|---|---|---|
| wave | `WAVES_coast_YYYYMMDD.nc` | SWH, SWP, WP | live |
| winds | `WINDS_YYYYMMDD.nc` | WSM, WSXM/WSYM → dir | live |
| currents | `CURRENTS_NIO_YYYYMMDD.nc` | CURRENT/U/V | sparse near coast |
| sst | `SST_NIO_YYYYMMDD.nc` | SST | live |
| chl | VIIRS rolling composite | chlor_a | NCSS 400 (swath format gap) |

Coastal land-mask: nearest grid cells return NaN, so the extractor steps seaward
(0.15°/step, 6 steps) until a wet cell hits, recording `sea_steps`.

## Gateway tier
`INCOIS (JSON API, unconfigured)` → **`INCOIS-THREDDS` (this)** → `OPEN_METEO`
(gaps only: currents/visibility/rain) → constants fallback. Every field labeled.

## Snapshot for datasets
`snapshot(lat, lon)` writes `ml/data/raw/incois_thredds_*.json` — feed these into
`ml/fishing/collect.py` rows for real training labels/features (chlorophyll still
needs a satellite composite source; Open-Meteo has none).
