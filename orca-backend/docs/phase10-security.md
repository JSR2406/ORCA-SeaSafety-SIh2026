# Phase 10 - Security

Security semantics for the FloatChat backend/frontend boundary. The frontend
cannot bypass safety decisions, and nothing sensitive leaks across the wire.

## 1. Black-box authority (can't be bypassed from the frontend)

- Risk classification, restriction status, route blocking, safety verdict and
  confidence are computed **server-side only** and merely reported through the
  contract. A frontend developer cannot accidentally bypass the Risk Engine /
  Verifier / hard constraints by reordering or omitting fields.
- Global exception handler returns a generic envelope; stack traces, module
  paths, file paths, and internal prompts are logged server-side and **never**
  surfaced to the client (`app/main.py:global_exception_handler`).

## 2. Secret & credential hygiene

- Credentials, tokens, API keys, authorization headers and cookies are never
  logged and never emitted in responses.
- Structured access logging redacts `authorization`, `cookie`, `x-api-key`,
  `proxy-authorization` (`app/middleware/correlation.py:_sanitise_headers`);
  request bodies are not logged at all.
- The streaming layer forwards only a whitelisted execution vocabulary
  (`app/orchestration/stream.py:_safe_payload`): evidence text, tool
  arguments, models/prompts and hidden reasoning are guaranteed excluded.
- No internal prompt, API key, or DB credential appears in `docs/`,
  fixtures, or shipped JSON schemas.

## 3. Transport / CORS

- CORS uses explicit `settings.cors_origins` (default `http://localhost:3000`).
  Credentials are enabled, so a wildcard `allow_origins` is **forbidden** and
  never configured.
- All traffic is TLS-terminated at the proxy in production (see deployment
  doc). `/ready` and `/health` are intended for the load balancer only.

## 4. Input protection

- Request validation at the edge binds message length
  (`orchestrator_max_message_chars: 4000`), coordinate bounds
  (`latitude -90..90`, `longitude -180..180`), waypoint cap (50), scenario
  `max_options` (1..10), and `requested_outputs` against an allow-list
  (`app/contracts/orchestration.py`).
- Malformed input returns a structured `INVALID_REQUEST` (400) - never a raw
  traceback.
- Rate limiting is a fixed in-memory window per client IP (default
  `rate_limit_rpm: 60`), returning structured `RATE_LIMITED` (429) with
  `Retry-After: 60` (`app/middleware/ratelimit.py`). It guards abusive volume
  without persisting client state.

## 5. Failure semantics

| Scenario | HTTP | `error.code` | Retryable |
|---|---|---|---|
| Bad/blank body, bad coords | 400 | `INVALID_REQUEST` | no |
| Rate limit exceeded | 429 | `RATE_LIMITED` | yes |
| Source/tool unavailable | 200 | `SOURCE_UNAVAILABLE` / `TOOL_TIMEOUT` | yes |
| Stale/expired data | 200 | `DATA_STALE` | yes (refetch) |
| Orchestration timeout | 200 | `ORCHESTRATION_TIMEOUT` | yes |
| Verifier rejected claims | 200 | `VERIFICATION_FAILED` | no (uncertainty surfaced) |
| No data returned | 200 | `NO_DATA` | no |
| Unexpected internal error | 500 | `INTERNAL_ERROR` | yes |

When a domain failure occurs mid-run (e.g. a source times out) the API still
returns `200` with `status: partial/degraded` and an honest `limitations` list;
it never fabricates data. Safety-relevant uncertainty always degrades to the
conservative `UNKNOWN`/`RESTRICTED` classification - never to `SAFE`.