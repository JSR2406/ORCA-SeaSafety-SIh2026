# Phase 10 - Deployment

## 1. Environment

All configuration comes from `settings` (`app/config.py`):

| Var | Default | Purpose |
|---|---|---|
| `api_host` | `0.0.0.0` | Bind address. |
| `api_port` | `8080` | Bind port. |
| `log_format` | `json` | `json` for prod, `console` for dev. |
| `log_level` | `INFO` | `DEBUG` enables OpenAPI docs + verbose logging (dev only). |
| `rate_limit_rpm` | `60` | In-memory fixed-window per client IP. |
| `cors_origins` | `["http://localhost:3000"]` | Explicit origins only (credentials enabled). |
| `database_url` | `postgis://…` | Source-of-truth PostGIS DB (Phase 9). |
| `orchestrator_max_message_chars` | `4000` | Max request length. |

## 2. Running

```bash
cd apps/api
# uvicorn (single proc / dev)
python -m uvicorn app.main:app --host $API_HOST --port $API_PORT

# production-ish single proc
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --no-access-log \
  --log-level warning --limit-concurrency 16 --timeout-keep-alive 5
```

Uvicorn is imported and configured entirely in `app/main.py`; run it through
the venv (`apps/api/venv`) whose packages are pinned by `requirements.txt`
(fastapi==0.141.1, pydantic==2.13.4, mcp>=1.2.0).

## 3. Process model & scaling

- One uvicorn process. Rate limiter and scheduler are in-memory; scale with
  multiple workers behind a session-pinned LB. **Do not** run sticky sessions
  and rely on them for `/ready`; instead pin by client IP is unnecessary
  because the limiter window is per-instance (acceptable for current scope).
- `mcp` + in-process scheduler must run in **every** worker (module import
  time `lifecycle.create_scheduler_default_policy`), so the process is
  deterministic across workers.

## 4. Reverse proxy & TLS

Terminate TLS at the proxy (Nginx/Traefik/Caddy). Required headers/filters:

```nginx
proxy_set_header X-Forwarded-For $proxy_addr;   # used for rate-limit key
proxy_set_header X-Request-ID $request_id;      # forwarded correlation spine
```

- Forwarded client IP drives rate limiting; sanitize `X-Forwarded-For` at the
  proxy (never trust raw client value directly).
- WebSocket upgrade header support is required for `/api/v1/orchestrate/stream`.

## 5. Probes

| Probe | Path | Expect |
|---|---|---|
| Liveness | `GET /api/v1/health` | `200` always (unless process dying). |
| Readiness | `GET /api/v1/ready` | `200` + `ready: true` when components healthy. |

Place both behind the LB; they are lightweight and exclude from access logs.

## 6. Production checklist

1. `log_format=json`, `log_level=INFO` (no `/docs`).
2. `cors_origins` = explicit production origin(s) only.
3. TLS at proxy; forwarded headers sanitized.
4. PostGIS reachable; `RUN_POSTGIS_TESTS=1` suite green before release.
5. Rate limit tuned for expected DAU (`rate_limit_rpm`).
6. Secrets/credentials kept out of env-dump logger config and response bodies.

## 7. Regression gate (run before release)

```bash
# venv + env
& apps\api\venv\Scripts\python.exe -m pytest tests -q            # ~278 + contract
$env:RUN_POSTGIS_TESTS="1"; $env:PYTHONIOENCODING="utf-8"
$env:POSTGIS_DATABASE_URL="<postgis://…>"
& apps\api\venv\Scripts\python.exe -m pytest -k "postgis or spatial or hard_constraint" -q
& apps\api\venv\Scripts\python.exe -m evaluation.live            # live acceptance 14/14
& apps\api\venv\Scripts\python.exe -m evaluation.benchmark       # benchmark 10/10
```

Contract regression: `python -m pytest tests/test_phase10_contract.py -q`
(36 checks: fixtures -> JSON-Schema valid, error vocabulary, rate-limit
envelope, correlation header, readiness shape, stream envelope).