# Phase 9 — Real-Source Matrix

Status: **operational baseline**. This matrix describes every data source FloatChat
can consume, its driver, and its **adjudicated status at the time the Phase 9
acceptance harness ran** (see `reports/live-latest.md`).

> Rule enforced across Phase 9: a source row is never marked `CONNECTED` unless
> an endpoint probe returned 2xx. No fixture or synthetic data is ever relabeled
> `LIVE`. `REPLAY / HISTORICAL DEMONSTRATION` data is always labeled as such.

## Adjudication vocabulary

| status | meaning |
|---|---|
| `CONNECTED` | probe returned 2xx and data was consumed from the live feed |
| `CONFIGURATION_REQUIRED` | adapter exists but no live credentials / toggle are set; driver is fallback-only |
| `UNAVAILABLE` | configured but probe failed or returned an error |
| `NOT_SUPPORTED` | no adapter / no legal feed for this source |
| `NOT_TESTED` | adapter exists but not exercised in this run |

## Source matrix (Phase 9 baseline)

| source | name | kind | driver | status | detail |
|---|---|---|---|---|---|
| `incois` | INCOIS | ocean observations (SST, currents, PFZ) | HTTP adapter | `CONFIGURATION_REQUIRED` | `incois_enabled` is disabled; no live probe |
| `imd` | IMD | weather observations / forecasts | HTTP adapter | `CONFIGURATION_REQUIRED` | `imd_enabled` is disabled; no live probe |
| `mosdac` | MOSDAC | satellite ocean / meteorological products | HTTP adapter | `CONFIGURATION_REQUIRED` | `mosdac_enabled` is disabled; no live probe |
| `nho` | NHO | charting / harbour restrictions | deterministic `TemporaryClosureAdapter` | `CONFIGURATION_REQUIRED` | no live feed configured; current driver is deterministic |
| `navarea-viii` | NAVAREA VIII | navigational warnings | deterministic `NavareaAdvisoryAdapter` | `CONFIGURATION_REQUIRED` | no live feed configured; current driver is deterministic |
| `navtex` | NAVTEX | broadcast safety messages | no registered adapter (fed via NHO/NAVAREA) | `CONFIGURATION_REQUIRED` | no live feed configured |

True HTTP adapters: `apps/api/app/datasources/{incois,imd,mosdac}.py`
(registered in `apps/api/app/datasources/registry.py`). NHO / NAVAREA / NAVTEX
are services-layer sources that resolve against the active restriction/warning
store; they are deterministic until a live capability flag is set. Source
health is evaluated per record by `apps/api/app/services/source_health.py`
(`HEALTHY / DEGRADED / UNAVAILABLE / STALE / UNKNOWN`).

To bring any source to `CONNECTED`, set its `*_enabled=true` plus its endpoint
credentials in `.env` (see `.env.example`), restart, and re-probe with the
live acceptance harness.

## Honesty rules (Phase 9 hard requirements)

- Never fabricate a live weather/PFZ/restriction value or timestamp.
- Never silently substitute mock data or label fixtures as real.
- When a source is not connected, propagate `SOURCE_UNAVAILABLE` (and
  `DATA_STALE` when an observed record is outside its freshness window) through
  the full chain: Agent → Fusion → Risk → Verifier → Response.
- Replays and offline fixture data carry the `REPLAY / HISTORICAL DEMONSTRATION`
  label end-to-end.
