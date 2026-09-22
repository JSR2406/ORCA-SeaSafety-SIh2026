# FloatChat Frontend ↔ Backend Integration

Authoritative reference for the `apps/web` UI talking to the FastAPI backend (`apps/api`).

## 1. Environment & Connectivity

| Variable | Default | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Trailing slash not required. Set to the deployed API origin. |
| CORS | `http://localhost:3000` only | Backend `app/config.py` / `main.py` allowlist. **A non-local frontend origin MUST be added to `CORS_ORIGINS` before it can call the API.** |

- Healthchecks: `GET /api/v1/health`, `GET /api/v1/ready` (load balancer / orchestrator probes).
- The frontend never touches the database directly; all reads go through the API.
- If the API cannot be reached, the UI shows a connection error and **never fabricates a reply**.

## 2. Bootstrap

On startup, the UI should call, in order:

1. `GET /api/v1/contract` → assert `api_version` compatibility; read `capabilities`.
2. `GET /api/v1/health` → `{status, version, demo_mode, database, timestamp}`.
3. `GET /api/v1/ready` → `{ready: true}` gate before enabling the input box.

If any probe fails, show the environment, not a fake conversation.

## 3. Main Loop — Orchestrate (single source of truth)

Everything the UI needs for one user turn is produced by one call:

```
POST /api/v1/orchestrate
```

### 3.1 Request (canonical)

```jsonc
{
  // REQUIRED (canonical)
  "query": "Is it safe to sail from Kochi to Lakshadweep tomorrow?",
  // REQUIRED (canonical) — stable across a conversation
  "session_id": "conv_abc123",
  // OPTIONAL
  "request_id": "ui-generated-correlation-id",
  "language": "en",                       // en | ml | ta | mr | gu | hi
  "user_location": {                      // OPTIONAL but strongly recommended
    "latitude": 9.9,
    "longitude": 76.3,
    "accuracy_m": 100,                    // OPTIONAL
    "source": "GPS",                      // USER | GPS | MAP | RESOLVED_PLACE | SYSTEM
    "timestamp": "2026-09-06T08:00:00Z"   // OPTIONAL
  },
  "requested_outputs": ["text", "map", "charts", "alerts", "route", "evidence", "history"],
  "route_request": null,                  // OPTIONAL — bypasses intent detection when set
  "scenario_request": null                // OPTIONAL
}
```

**Legacy aliases (accepted; do not use in new code):** `message` = `query`, `conversation_id` = `session_id`. The server resolves `query = payload.query ?? payload.message` and `session_id = payload.session_id ?? payload.conversation_id`.

**Error if neither `query` nor `message` is present** → `400 INVALID_REQUEST`.

### 3.2 Response

```jsonc
{
  "request_id": "ui-generated-correlation-id",
  "run_id": "urn:...",                    // links query-runs, provenance, exports
  "conversation_id": "conv_abc123",
  "session_id": "conv_abc123",
  "status": "completed",                  // completed | needs_input | failed | invalid | unavailable
  "language": "en",
  "answer": "Plain-language answer for the user...",
  "message": "Same as answer (legacy alias; read `answer`)",
  "sections": [],                         // optional rich sections
  "confidence": {                         // NEVER a hard trust statement
    "score": 0.87,
    "level": "HIGH",
    "basis": "PT+RF (2000) on 310 validated"
  },
  "risk": {
    "classification": "MODERATE",         // SAFE | LOW | MODERATE | HIGH | UNKNOWN — see 3.4
    "reason": "...",
    "hard_constraint": false,
    "assessed": true
  },
  "needs_input": { "questions": [] },     // populated when status == needs_input
  "outputs": {
    "maps": [], "charts": [], "alerts": [], "route": null
  },
  "evidence": [],
  "verification": { "all_verified": true, "checked": 3 },
  "provenance": [],
  "limitations": [],
  "evidence_graph": { "nodes": [], "sources": [] },
  "tool_calls": [],
  "duration_ms": 1234,
  "phase_timings": {},
  "schema_version": "phase6",
  "api_version": "...",
  "execution": { "status": "...", "events": [] }   // legacy surface; prefer WS
}
```

### 3.3 Clarification flow (`needs_input`)

When `status == needs_input`:

1. Render `needs_input.questions` (each a `{question, param}`).
2. Let the user answer.
3. Resubmit a new `POST /api/v1/orchestrate` with the **same `session_id`** and the answer folded into `query` (and, if the question was about location, into `user_location`).

Do not synthesize answers on the client when `needs_input` is returned.

### 3.4 Risk is the backend's sole authority

- Read `risk.classification` (`"SAFE" | "LOW" | "MODERATE" | "HIGH" | "UNKNOWN"`). The legacy field `risk.level` is **not** part of the contract.
- When the pipeline has no authoritative data the backend returns `classification: "UNKNOWN"` and `assessed: false`. The UI must surface that honestly — e.g. "no verified marine data for this area" — and **never** map UNKNOWN to SAFE.
- ML outputs never override `RiskEngine`. If a model predicts, say, SAFE but the engine says HIGH, the engine wins.

### 3.5 Honest data-state vocabulary

Data-state words reused across payloads:

| State | Meaning for the UI |
|---|---|
| `configured` | Provider/source key present, endpoint validated |
| `not_configured` | Key/env missing — feature disabled, no silent fallback |
| `live` / `connected` | Healthcheck OK; **not** proof data is flowing |
| `unavailable` / `no_data` | No authoritative data for the scope — answer honestly |
| `demo` / `TEST-MOCK` | Mock data path — UI must label results as demo, never as real |

## 4. WebSocket: `POST /api/v1/orchestrate/stream`

Live event stream for the same run surface.

- URL: `ws(s)://<api-host>/api/v1/orchestrate/stream`
- **Protocol: send the request payload as the first JSON text frame** (same shape as §3.1) as soon as the socket opens. The server will not read it from query params.
- Server then streams sanitized events, ending with a terminal event:

```jsonc
// all frames look like:
{
  "type": "execution.started | tool.started | tool.completed | data.loaded | risk.assessed | response.ready | execution.completed | execution.failed | error",
  "run_id": "urn:...", "session_id": "...", "timestamp": "...",
  "data": { "...": "per-type payload" },     // optional
  "error": { "code": "...", "message": "..." } // terminal `execution.failed` / `error`
}
```

- On the terminal event, the client should fall back to `GET /api/v1/query-runs/{run_id}` for the full `OrchestrateResponse`.
- Malformed/unknown frames are ignored (the run still completes server-side). Do not derive the final answer from events alone.

## 5. Endpoint Reference (api-client.ts → backend)

| Method | Endpoint | Notes |
|---|---|---|
| `api.health()` | `GET /api/v1/health` | **Not** `/health`. |
| `api.contract()` | `GET /api/v1/contract` | Capabilities + `api_version`. |
| `api.orchestrate()` | `POST /api/v1/orchestrate` | Primary turn loop (§3). |
| `api.orchestrateStream()` | `WS /api/v1/orchestrate/stream` | First-frame JSON (§4). |
| `api.getQueryRun(runId)` | `GET /api/v1/query-runs/{run_id}` | Full result + `GET .../provenance` for traceability. |
| `api.exportCSV(runId, format)` | `POST /api/v1/exports/csv` | Blob download. |
| `api.datasetStatus()` | `GET /api/v1/datasets/status` | Read-only. |
| `api.riskBriefing({origin, destination?, language?})` | `POST /api/v1/risk/briefing` | Accepts `{origin: {lat, lon}}`; `lat`/`lon` top-level fallback. |
| `api.projectScenario(params)` | `POST /api/v1/scenarios/create` | Alias `POST /api/v1/scenarios/project`. |
| `api.planQuery/executeQuery` | `POST /api/v1/query/plan`, `POST /api/v1/query/execute` | Legacy shims over the orchestrator; prefer `orchestrate`. |
| `api.chat(...)` | `POST /api/v1/chat` | Legacy; `status: unavailable` (not a 500) when no LLM key. |
| `api.transcribe/synthesize` | `POST /api/v1/voice/...` | 503 `not_configured` without STT/TTS keys. |
| `api.searchProfiles/detectAnomaly` | `POST /api/v1/profiles/search`, `/api/v1/anomalies/detect` | Optional feature modules. |

## 6. Error Vocabulary

All non-2xx responses from the API use a stable envelope where possible:

```jsonc
{ "error": { "code": "INVALID_REQUEST | NOT_FOUND | NOT_CONFIGURED | UNAVAILABLE | RATE_LIMITED | INTERNAL", "message": "…", "retryable": false, "http_status": 400 } }
```

| HTTP | Code | UI behaviour |
|---|---|---|
| `400` | `INVALID_REQUEST` | Fix payload; never retry blindly. |
| `404` | `NOT_FOUND` | Route/run missing. |
| `405` | — | Wrong method — check endpoint table above. |
| `424` | `UNAVAILABLE` | Honest missing-data/unverified state — show reason, no fallback. |
| `503` | `NOT_CONFIGURED` | Feature disabled (missing key) — show "not configured". |
| `429` | `RATE_LIMITED` | Backoff, offer retry. |
| `500` | `INTERNAL` | Report correlation `request_id`; never show a fake answer. |

Always send a stable `session_id` on writes so the server can correlate; a 500 never means "retry the same payload in a loop".

## 7. Voice & Media (optional module)

- Without `STT_API_KEY` / `TTS_API_KEY`, `GET /api/v1/voice/providers` reports `status: not_configured` and transcribe/synthesize return `503` — the UI must hide or disable the mic/speaker buttons instead of showing errors.
- `GET /api/v1/voice/providers` returns `{stt: {...}, tts: {...}, translation: {...}}` keyed by provider with `status`, `supported_languages`, `latency_ms`.

## 8. Type-Safety

Keep `packages/shared-types/src/phase6.ts` and `apps/web/src/lib/api-client.ts` aligned with this doc (`OrchestrateRequest` = `{query, session_id, ...}` + legacy optional aliases; `OrchestrateResponse.risk.classification`). CI type-checks the web app against those types — if the shape drifts the build fails, which is the intended safety net.