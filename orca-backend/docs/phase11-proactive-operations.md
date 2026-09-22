# Phase 11 - Proactive Operations, Alerting & Autonomy

This document is the runbook for FloatChat's proactive marine intelligence and
autonomous alerting.  It describes the alert lifecycle, the bounded background
scheduler, the monitoring layers (geofence + restrictions), source health
handling, and the realtime path — plus the operational invariants that must not
be breached.

## 1. Proactive pipeline

```
live data / source health
   -> ChangeDetector (idempotent)
   -> MarineEvent (normalized, stability-keyed)
   -> AlertPolicyEngine (relevance -> severity -> validity -> preferences)
   -> AlertDeduplicator (windowed)
   -> ProactiveMarineEngine (emit ActiveAlert, persist, lifecycle)
   -> AlertRepository (Postgres/PostGIS or in-memory)
```

The agentic coordinator is `ProactiveMarineAgent`: it *interprets* an event,
determines affected geography, correlates marine/weather/safety state through the
MCP tool bus, and prepares evidence-backed `AlertCandidateEnvelope`s.  It routes
through the Risk Engine for the authoritative risk verdict and never overrides a
hard constraint or the verifier.

## 2. Alert lifecycle

```
CREATED -> ACTIVE -> [ACKNOWLEDGED | ESCALATED] -> EXPIRED / RESOLVED / DISMISSED
```

- **Never delete history** — an expired alert becomes `EXPIRED`, it is not removed.
- **Acknowledge** via `POST /api/v1/alerts/{id}/acknowledge` (idempotent).
- **Resolve** and **dismiss** are interior engine transitions.
- **Expiry** is driven by the scheduler every tick over each alert's `valid_until`
  window; once expired it stays expired.
- **Escalation** only on a *material* severity jump one rung up the ladder
  `info -> caution -> warning -> high -> critical`, respecting
  `alert_max_escalations` and `alert_escalation_step_seconds`.  A materially
  escalated severity is itself recorded as a new `DATA_CHANGED` event.

## 3. Bounded scheduler

`ProactiveScheduler` (in `app.ingestion.proactive_scheduler`) is a bounded,
restart-safe, observable loop:

- configurable tick (`proactive_tick_seconds`) and source refresh cadence
  (`proactive_source_refresh_seconds`);
- a fixed worker queue (`proactive_worker_queue_size`) — no unbounded growth;
- engine + detector state are rehydrated on restart;
- `tick()` = expire due alerts + `stats()`; source refresh is fed in via
  `refresh_sources([{source, ok}, ...])` so the loop never blocks on I/O;
- `probe()` exposes ticks/last error/queue/stats for observability;
- wrapped up in `main.py` lifespan next to the existing `SourcePollingScheduler`,
  gated by `proactive_enabled`.

## 4. Monitoring layers

### 4.1 Geofence monitor

Tracks each `(vessel, geofence)` through a state machine
`OUTSIDE -> APPROACHING -> INSIDE -> EXITED`, computed from the PostGIS (or
offline catalog) geometry with `point_in_polygon` / `point_to_polygon_distance_m`.
Events: `GEOFENCE_APPROACH` (≤ `geofence_approach_km`), `GEOFENCE_ENTRY`,
`GEOFENCE_EXIT`.  No repeat alert while the state is unchanged.  Track count is
bounded by `geofence_max_active`.

### 4.2 Restriction monitor

Tracks restriction lifecycle `scheduled -> activated -> updated -> extended ->
expired -> cancelled` per `(source, restriction_id)`, and converts each material
transition into `RESTRICTION_ACTIVATED / UPDATED / EXPIRED` events.  It respects
`valid_from / valid_until` and a configured `status`.  Bounded by
`restriction_max_active`.

## 5. Source failure & recovery

- `observe_source(name, ok)` drives the detector; failures fire
  `SOURCE_FAILURE` once per outage, recovery fires `SOURCE_RECOVERY` exactly once.
- Every such event is **tracked** in `recent_events()` even when it does not
  produce a user-facing alert (e.g. `sources` category is `digest`/`disabled`).

## 6. API surface

| method | path | purpose |
|---|---|---|
| GET | `/api/v1/alerts` | list (status/severity/type filters) |
| GET | `/api/v1/alerts/{id}` | fetch one alert |
| POST | `/api/v1/alerts/{id}/acknowledge` | acknowledge |
| GET | `/api/v1/events` | recent normalized events |
| POST | `/api/v1/alerts/preferences` | per-category modes |
| GET | `/api/v1/proactive` | engine state bus |

The router never exposes chain-of-thought, prompts, DB queries, credentials, or
raw tool arguments.  Realtime lifecycle events (`alert.created`, `escalated`,
`acknowledged`, `expired`, `resolved`) ride the existing orchestrate stream
surface when a frontend is attached.

## 7. Safety invariants (do not break these)

1. **Hard restrictions dominate** — the proactive engine and agent never weaken a
   restriction raised by the risk/rule layer.
2. **Unknown is not SAFE** — no proactive/ML path may convert missing data into a
   safety verdict.
3. **Risk Engine > Verifier > proactive** — escalation/candidates are advisory;
   the authoritative verdict remains Risk Engine + Verifier.
4. **Bounded & idempotent** — repeated ticks must not multiply alerts or grow
   state without bound.
5. **No secrets on the wire** — evidence/events carry no credentials.

## 8. Restart & shutdown

- `reset_proactive_singletons()` clears the engine/agent singletons (test/restart).
- `reset_scheduler_singleton()` clears the bounded scheduler.
- The lifespan cancel path awaits scheduler tasks and closes the DB after both
  the ingestion and proactive schedulers have stopped.

## 9. Configuration reference (new in Phase 11)

`proactive_enabled`, `proactive_worker_queue_size`, `proactive_tick_seconds`,
`proactive_source_refresh_seconds`, `geofence_approach_km`,
`geofence_refresh_seconds`, `geofence_max_active`,
`restriction_scan_seconds`, `restriction_max_active`,
`alert_dedupe_window_seconds`, `alert_default_ttl_seconds`,
`alert_max_escalations`, `alert_escalation_step_seconds`,
`alert_ml_material_change`, `source_failure_threshold`,
`source_recovery_ticks`, `alert_default_mode`.