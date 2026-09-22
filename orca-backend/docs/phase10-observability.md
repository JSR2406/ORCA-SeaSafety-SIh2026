# Phase 10 - Observability

How FloatChat logs, correlates, and exposes health so operators and the
frontend can reason about a single user turn end-to-end.

## 1. Correlation spine

One request produces one correlation spine:

```
request_id -> run_id -> task_id -> tool_call_id
```

- HTTP: `CorrelationMiddleware` assigns `request_id` (honours inbound
  `X-Request-ID`) and stamps every response with `X-Request-ID`
  (`app/middleware/correlation.py`).
- Orchestration: the run uses `run_id` (= the orchestrator rid), which flows
  through plan tasks and tool calls.
- Streaming: every WS event carries `run_id` + `request_id` +
  `event_schema_version`.
- The response returns `request_id` and `run_id` so the frontend can attach
  support tickets to a single turn.

## 2. Structured logging

- `app/logging_config.py` bootstraps structlog. `log_format` defaults to
  `json` (ISO UTC timestamps, level, event); `console` is available for dev.
- Every log line within a request is pre-bound with `request_id`
  (structlog contextvars).
- An access log event is emitted per request: method, path, status,
  duration_ms, client_ip, request_id (`event: "access"`).
- Existing stdlib logging call sites are chained through the same stream - no
  code changes required.

### Never logged

Credentials, tokens, API keys, authorization headers, cookies, request
bodies, internal prompts, and hidden reasoning.

## 3. Health & readiness

| Endpoint | Purpose | Behavior |
|---|---|---|
| `GET /api/v1/health` | Liveness | `status: healthy\|degraded`, `database`, `version`, `timestamp`. |
| `GET /api/v1/ready` | Readiness | `ready: true/false` + per-component status for `database`, `scheduler`, `orchestrator`. Lightweight, no external calls per poll. |

> v1.0 audio/data caution: readiness only reflects in-process components, not
> the full source-feeding chain; see `docs/phase9-source-matrix.md` for source
> health details (monitored by the Phase 9 SourceHealthMonitor).

## 4. Metrics

The Phase 10 boundary exposes the timing/verification shape that operational
dashboards key off, without adding a metrics dependency (architecture frozen):
`execution.duration_ms`, `execution.phase_timings`, `execution.verification`,
and `confidence.score`. These are reported per response and also streamed via
`execution.timings` on the WS channel. Rate-limit counters are in-memory.

## 5. Debugging a single turn

1. Frontend receives `request_id`/`run_id`; SSO/support can grep logs by
   `request_id`.
2. Backend logs correlate through `run_id` across plan/task/tool boundaries.
3. WS stream events give a live, sanitized trace of the same run.

## 6. Ops guardrails

- Access logs omit sensitive payloads by construction (redaction + no bodies).
- Health/ready/contract endpoints are excluded from access-log noise.
- In `DEBUG` (`log_level`), `/docs` + `/redoc` are enabled for development
  only; production uses `INFO`+ and no doc routes.