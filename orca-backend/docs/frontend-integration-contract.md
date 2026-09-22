# Frontend Integration Contract

The frontend integrates with FloatChat purely through the versioned HTTP/WS
contract. It never reads backend internals. The three documents below are the
canonical reference; this file is the quick-start pointer.

- Contract + schemas: `docs/phase10-api-contract.md`
- Black-box boundary & streaming protocol: `docs/phase10-frontend-integration-contract.md`
- Security, observability, deployment:
  `docs/phase10-security.md`, `docs/phase10-observability.md`, `docs/phase10-deployment.md`

## Quick start

```bash
# run backend
cd apps/api && python -m uvicorn app.main:app --port 8080
# publish contract metadata + JSON schemas
curl http://localhost:8080/api/v1/contract
```

### Turn

```jsonc
POST /api/v1/orchestrate
{ "query": "is it safe today?", "language": "en",
  "user_location": { "latitude": 9.9, "longitude": 76.3, "source": "USER" },
  "requested_outputs": ["text", "map", "charts", "alerts", "route"] }
```

### Rules of the road

1. Never copy, reference, or depend on internal prompts / tool names / DB
   schema.
2. The backend is the sole authority for safety (`risk.classification`,
   `hard_constraint`, `route.blocked`). Never derive SAFE yourself.
3. Read `status`; if `needs_input`, collect `needs_input.questions` and
   re-submit in the same session.
4. Version metadata (`api_version`, `response_schema_version`,
   `event_schema_version`) is in every envelope - assert it on bootstrap.
5. Always send/echo `request_id`; the backend returns `request_id` + `run_id`
   for support correlation (`X-Request-ID` header).

## Contract fixtures

`apps/api/app/contracts/fixtures.py`: 12 labeled `CONTRACT FIXTURE` examples
(validated against the published JSON schemas). Use them as golden files for
frontend component/e2e tests - any change to them is a contract change.

## Versioning

- Backward-compatible changes are additive only; existing fields never change
  meaning.
- Breaking changes ship as `/api/v2/`; v1 stays frozen. The frontend pins to
  `api_version: "1"`.