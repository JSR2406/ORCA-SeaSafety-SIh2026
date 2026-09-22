# Phase 10 - Frontend Integration Contract

The frontend treats the FloatChat backend as a **black box**. It consumes only
the stable versioned contract below and never couples to agents, MCP, database
schema, planner/executor internals, or the fusion/risk/verifier implementation.

Canonical docs: `docs/phase10-api-contract.md` (schemas), `docs/phase10-security.md`,
`docs/phase10-observability.md`, `docs/phase10-deployment.md`.

## 1. What the frontend MAY know

| Knowledge | Allowed |
|---|---|
| Endpoints: `POST /api/v1/orchestrate`, WS `/api/v1/orchestrate/stream` | ✅ |
| Request/response/error JSON schemas (published at `/api/v1/contract`) | ✅ |
| Auth model (API key / auth header) | ✅ |
| Streaming event protocol | ✅ |
| map / charts / alerts / route / evidence / provenance / confidence / risk schemas | ✅ |
| `request_id` → `run_id` correlation, session, language | ✅ |

## 2. What the frontend MUST NOT know

| Knowledge | Forbidden |
|---|---|
| Agent implementation, planner/executor internals | 🚫 |
| MCP tool names / invocation details | 🚫 |
| Database schema / queries | 🚫 |
| Model/fusion/risk/verifier implementation | 🚫 |
| Internal prompts / hidden reasoning | 🚫 |
| Credentials / tokens / API keys | 🚫 |

The boundary is enforced by `app/contracts/normalize.py`: it is the **only**
place the public response is derived from the internal orchestrator dict, and
it is additive/defensive (never leaks extra internal fields).

## 3. Black-box authority rule

**The frontend never independently decides something is SAFE.** The backend is
the sole authority for:

- risk classification (`risk.classification`)
- restriction status (`risk.hard_constraint`)
- route blocking (`route.blocked`, `route.status`)
- safety verdict (embedded in `answer` + `risk`)
- confidence (`confidence.level` / `confidence.score`)

A frontend developer cannot accidentally bypass the Risk Engine / Verifier /
hard constraints: those decisions are computed server-side and only *reported*
through the contract.

## 4. Versioning rules

- `api_version: "1"`, `response_schema_version: "1.0"`,
  `event_schema_version: "1.0"` (see `app/contracts/versions.py`).
- Backward-compatible changes (new optional fields) are **additive only**.
- Breaking changes move to `/api/v2/`; v1 is never silently mutated.
- Every response carries `schema_version` + `api_version` so the frontend can
  assert which contract it is speaking.

## 5. Primary request flow

```http
POST /api/v1/orchestrate
Content-Type: application/json

{
  "query": "is it safe to go out today?",
  "language": "en",
  "session_id": "sess-42",
  "user_location": { "latitude": 9.9, "longitude": 76.3, "source": "USER" },
  "requested_outputs": ["text", "map", "charts", "alerts", "route"],
  "request_id": "client-abc"
}
```

The legacy query-parameter channel (`?message=&conversation_id=&request_id=`)
remains supported and returns the same additive envelope.

## 6. Streaming protocol

`WS /api/v1/orchestrate/stream?message=...` emits sanitized execution metadata
events. Every event envelope:

```json
{
  "run_id": "orch-abc",
  "request_id": "orch-abc",
  "timestamp": "2026-08-31T12:00:00Z",
  "event": "task.started",
  "status": "running",
  "task_id": "t1",
  "data": { "task": "verify" },
  "event_schema_version": "1.0"
}
```

Event vocabulary (union): `execution.started`, `intent.detected`,
`plan.created`, `task.started`, `task.completed`, `task.failed`,
`tool.started`, `tool.completed`, `tool.failed`, `verification.*`,
`response.ready`, `execution.completed`, `execution.failed`,
`execution.timings`. Only whitelisted numeric/categorical data is streamed;
evidence text, tool arguments and internal reasoning are never sent.

## 7. Success contract excerpt (see api-contract.md for the full schema)

```json
{
  "request_id": "client-abc",
  "run_id": "orch-ab12cd34ef56",
  "session_id": "sess-42",
  "status": "completed",
  "schema_version": "1.0",
  "api_version": "1",
  "language": "en",
  "answer": "…",
  "confidence": { "score": 0.8, "level": "high", "basis": ["…"] },
  "risk":      { "classification": "HIGH_RISK", "assessed": true, "hard_constraint": false, "reason": "…" },
  "needs_input": { "questions": [] },
  "evidence": [], "provenance": [], "limitations": [],
  "map": { "features": [], "generated_at": null },
  "charts": [], "alerts": [], "route": { "status": "none", "blocked": false },
  "execution": { "intent": "safety", "tool_calls": 5, "duration_ms": 120, "verification": { "all_verified": true } },
  "error": null
}
```

Legacy fields (`message`, `conversation_id`, `sections`, `verification`,
`tool_calls`, `duration_ms`, `intent`, `notes`) are appended for drop-in
compatibility with Phase 4/6 consumers.

## 8. Contract fixtures

`apps/api/app/contracts/fixtures.py` ships 12 labeled `CONTRACT FIXTURE`
examples covering: PFZ, marine briefing, safety, active restriction (route
blocked), open route, productivity, knowledge retrieval, scenarios,
multilingual (Hindi), multi-turn session, degraded source, and needs_input.
Each is validated against the published JSON schema by
`tests/test_phase10_contract.py` and is the source for contract tests.