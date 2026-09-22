# Phase 10 - API Contract (v1)

Stable, versioned HTTP and WebSocket contract between FloatChat backend and
any frontend. The frontend treats the backend as a black box; this document is
the complete public surface it may rely on.

- `api_version`: `1`
- `response_schema_version`: `1.0`
- `event_schema_version`: `1.0`
- Version constants + `contract_meta()`: `apps/api/app/contracts/versions.py`
- Authoritative JSON schemas (generated from pydantic): `apps/api/app/contracts/schemas.py`, also published at `GET /api/v1/contract`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/orchestrate` | Run one orchestration turn (canonical). |
| WS | `/api/v1/orchestrate/stream` | Streamed execution metadata for one turn. |
| GET | `/api/v1/health` | Liveness (db + version). |
| GET | `/api/v1/ready` | Readiness probe (db, scheduler, orchestrator). |
| GET | `/api/v1/contract` | Publish contract versions + capabilities for discovery. |
| GET | `/api/v1/mcp/status` | Capability-layer status (compatible, unchanged). |

## 1. POST /api/v1/orchestrate

Accepts either a JSON body (`OrchestrationRequest`) or the legacy query
parameters `?message=&conversation_id=&request_id=`. A JSON body takes
precedence.

### Request body schema (JSON)

```jsonc
{
  "query": "string (required, <= 4000 chars)",
  "language": "en|hi|ta|ml|te|null",
  "session_id": "string|null",
  "user_location": {
    "latitude": 9.9,                  // -90..90
    "longitude": 76.3,                // -180..180
    "accuracy_m": 25.0,               // optional, >= 0
    "timestamp": "2026-08-31T12:00:00Z",
    "source": "USER|GPS|MAP|RESOLVED_PLACE|SYSTEM"
  },
  "context": { },                     // opaque, additive
  "requested_outputs": ["text|map|charts|alerts|route|evidence|history"],
  "route_request": {                  // optional convenience
    "origin_latitude": 9.9, "origin_longitude": 76.3,
    "destination_latitude": 12.9, "destination_longitude": 74.8,
    "waypoints": [ { "latitude": 10, "longitude": 76.5 } ]   // max 50
  },
  "scenario_request": { "description": "", "options": ["now","tomorrow"],
                        "max_options": 3 },                   // 1..10
  "request_id": "client-abc"
}
```

### Response

HTTP 200. Body is the canonical `OrchestrationResponse` (see
`apps/api/app/contracts/response.py`) with legacy fields appended additively.

Key top-level fields:

| Field | Meaning |
|---|---|
| `request_id` | Client identifier echoed back. |
| `run_id` | Server execution id — the correlation spine for this turn. |
| `session_id` / `language` | Conversation + response language. |
| `status` | Controlled vocabulary: `accepted, planning, executing, verifying, completed, needs_input, partial, degraded, failed, timeout`. |
| `schema_version` / `api_version` | Contract versions. |
| `confidence` | `{score 0..1, level, basis[]}` — deterministic rule, not model. |
| `risk` | `{classification, assessed, hard_constraint, reason}`. |
| `needs_input` | `{questions: [{id, type, question}]}` when `status == needs_input`. |
| `evidence` / `provenance` / `limitations` | Traceability for every claim. |
| `map` / `charts` / `alerts` / `route` | Rich outputs. |
| `execution` | `{intent, tool_calls, duration_ms, phase_timings, verification, freshness, notes}`. |
| `error` | Structured error (see §3) or `null`. |

`risk.classification` is the CANONICAL safety vocabulary:
`SAFE, CAUTION, HIGH_RISK, CRITICAL, RESTRICTED, UNKNOWN`. Only the backend
evaluates it. `risk.hard_constraint=true` or `classification=RESTRICTED` means
an active restriction binds the answer.

### Status semantics

| `status` | Frontend behavior |
|---|---|
| `completed` | Show `answer`, render rich outputs. |
| `needs_input` | Prompt for `needs_input.questions`, re-submit. |
| `partial` / `degraded` | Show answer with reduced-confidence styling (`confidence.level`). |
| `failed` / `timeout` | Show `error.message`, offer retry when `error.retryable`. |

## 2. Streaming events

Envelope + vocabulary defined in §6 of `docs/phase10-frontend-integration-contract.md`.
Only sanitized execution metadata is streamed.

## 3. Error contract

Every failure returns the same envelope (`ErrorResponse`):

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Please retry shortly.",
    "retryable": true,
    "http_status": 429
  }
}
```

Error codes:
`INVALID_REQUEST` (400), `NEEDS_INPUT`, `SOURCE_UNAVAILABLE`, `DATA_STALE`,
`TOOL_TIMEOUT`, `ORCHESTRATION_TIMEOUT`, `VERIFICATION_FAILED`, `NO_DATA`,
`RATE_LIMITED` (429), `INTERNAL_ERROR` (500).

- Validation failures return `400` with `INVALID_REQUEST` (see `X-Error-Code`
  header and `app/main.py:validation_exception_handler`).
- Rate limit breaches return `429` + `Retry-After: 60`.
- Internal failures return `500` with a generic envelope — no stack traces,
  file paths, credentials or internal prompts ever reach the client.

## 4. Headers

- Every response carries `X-Request-ID` (honours inbound `X-Request-ID`).
- CORS is explicit-origins only (`settings.cors_origins`); credentials are
  enabled, so wildcard origins are forbidden.

## 5. Compatibility guarantees

- `POST /api/v1/orchestrate` remains stable; the legacy query-parameter
  channel and the existing MCP endpoints are unbroken.
- The response is additive: existing Phase 4/6 fields are preserved verbatim.
- Breaking changes require `/api/v2/`; v1 is never silently mutated.