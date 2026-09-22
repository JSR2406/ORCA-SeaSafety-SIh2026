# Phase 11 - Event Model, Change Detection & Rules

This document defines the normalized marine event model, the idempotent change
detection layer, and the deterministic alert-policy rules that sit behind
FloatChat's proactive alerting.  It is the reference for the `app.events`
package and for how alerts are (and are not) raised.

## 1. The MarineEvent record

A `MarineEvent` is the atomic record of a *meaningful* change in the marine /
weather / safety picture:

| field | meaning |
|---|---|
| `event_id` | stable id — same physical event always yields the same id |
| `event_type` | one of the vocabulary below |
| `source` | provenance (e.g. `incois`, `imd`, `nho`, `geofence.monitor`) |
| `timestamp` | when the event occurred (UTC) |
| `location` / `geometry` | `{lat, lon}` and optional GeoJSON geometry |
| `severity` | `info \| caution \| warning \| high \| critical` |
| `previous_state` / `current_state` | the physical values that changed |
| `validity` | `{valid_from, valid_until, freshness}` |
| `metadata` | `stable_key`, title/description, extra nuance (never secrets) |
| `change_state` | `new \| changed \| unchanged \| corrected \| expired \| failed \| recovered` |

### 1.1 Event type vocabulary

`NEW_OBSERVATION`, `DATA_CHANGED`, `DATA_CORRECTED`, `WEATHER_HAZARD`,
`LIGHTNING`, `CYCLONE`, `HIGH_WAVE`, `HIGH_WIND`, `RESTRICTION_ACTIVATED`,
`RESTRICTION_UPDATED`, `RESTRICTION_EXPIRED`, `GEOFENCE_APPROACH`,
`GEOFENCE_ENTRY`, `GEOFENCE_EXIT`, `PFZ_UPDATE`, `FORECAST_CHANGE`,
`SOURCE_FAILURE`, `SOURCE_RECOVERY`.

### 1.2 Idempotence by construction

`stable_event_id(type, source, stable_key, current_state)` is a SHA-1 of the
physical change (key ordering is not significant).  Re-emission of an unchanged
message always produces the same id, so replaying a source never forks an event
family or creates a duplicate alert.  `previous_state` is deliberately excluded
so a re-emit that only shifts the timestamp does not fork the id.

Timestamps that are pure metadata churn (e.g. `ingested_at`) are excluded from
`content_hash()`, so they never trigger a spurious `CHANGED`.

## 2. Change detection

`ChangeDetector` keeps, per `(source, stable_key)`, the last-seen state hash and
past availability.  On each evaluation it classifies the transition:

| observation | classification | event |
|---|---|---|
| never seen | `NEW` | yes |
| identical hash | `UNCHANGED` | no (deduped) |
| different hash | `CHANGED` | yes |
| explicit correction | `CORRECTED` | yes (`DATA_CORRECTED`) |
| validity ended | `EXPIRED` | yes (`RESTRICTION_EXPIRED`) |
| ≥ `failure_threshold` consecutive failures | `FAILED` | yes (`SOURCE_FAILURE`) |
| healthy for `recovery_ticks` after a failure | `RECOVERED` | yes (`SOURCE_RECOVERY`) |

Idempotence rule: calling `classify_data()` twice with the same JSON yields
`UNCHANGED` the second time and emits no event.

### 2.1 Source health state machine

- Failure: `consecutive_failures >= failure_threshold` fires exactly one
  `SOURCE_FAILURE` per outage (no repeat alerts while the source stays down).
- Recovery: after a failure, only once the source has been healthy for
  `recovery_ticks` consecutive ticks does exactly one `SOURCE_RECOVERY` fire.
  Until then the tick is `UNCHANGED`; the availability flag is **not** flipped
  early (a premature flip would suppress the recovery alert).

Configuration knobs (from `app.config`): `source_failure_threshold`,
`source_recovery_ticks`, each surfaced through the scheduler.

## 3. Alert policy engine

`AlertPolicyEngine` turns a `MarineEvent` into an `AlertCandidate` only when it
survives a deterministic gate:

```
EVENT -> RELEVANCE -> SEVERITY FLOOR -> VALIDITY -> USER PREFERENCES -> FRESHNESS NOTE
```

1. **Relevance** — events without a location are always relevant; a configured
   watch point may bound the search radius.
2. **Severity floor** — each event type has a floor (e.g. `HIGH_WAVE` requires
   ≥ `WARNING`).  Below-floor events never alert.
3. **Validity** — an event whose `valid_until` has already passed cannot become a
   live alert (its expiry is a separate `RESTRICTION_EXPIRED` notice).
4. **User preferences** — per-category delivery mode:
   - `immediate`: always alert.
   - `important_only`: alert only for safety-relevant categories
     (`cyclone, lightning, waves, weather, restrictions, geofence`).
   - `digest`: still collected; a separate publisher gates delivery.
   - `disabled`: never alert for that category.
5. **Freshness note** — `stale`/`unavailable` source events are still surfaced but
   carry an explicit "verification is limited" suffix, never a fabricated value.

### 3.1 Preference categories

`cyclone`, `lightning`, `waves`, `weather`, `restrictions`, `geofence`, `pfz`,
`sources`, `data` — each maps one or more event types and is independently
configurable per user via `POST /api/v1/alerts/preferences`.

## 4. Deduplication

Two layers:

- **Event layer** — identical stable `event_id`s are dropped by the engine
  (`ChangeState.UNCHANGED`).
- **Alert layer** — `AlertDeduplicator` remembers `dedupe_key`s within
  `alert_dedupe_window_seconds` (default 3600 s) and suppresses a second alert
  for the same physical event.

Deduping never deletes history; the first alert remains and is re-readable.

## 5. Freshness

The engine labels each alert `live | fresh | recent | stale | unavailable`.
`unavailable`/`stale` alerts are retained but explicitly limit verification.

## 6. What this layer cannot do

- It never overrides a **hard restriction** — those are owned by the risk /
  verifier rule layers.
- It never transforms `unknown`/missing data into `SAFE`.
- It never emits an alert that is not backed by at least event-source evidence.
- It never exposes chain-of-thought, prompts, DB queries, credentials, or raw
  tool arguments (the alert model stores *evidence*, not internals).