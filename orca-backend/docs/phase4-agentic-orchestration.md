# Phase 4 Architecture Report - Agentic Orchestration

Phase 4 adds a deterministic agentic orchestrator on top of the Phase 2/3 MCP
tool layer and the Phase 3.5 knowledge engine. It is data-driven (a capability
matrix), never a keyword router; every number it emits is verifier-traced to a
real tool output; and all execution is bounded by config-driven limits.

Pipeline: **Message -> Intent -> Plan -> Validate -> Execute (DAG) -> Verify ->
Synthesize**, exposed as `POST /api/v1/orchestrate`.

## 1. Modules (`app/orchestration/`)

| Module | Responsibility |
|---|---|
| `models.py` | Dataclasses: `Intent`/`IntentName`, `Task`/`TaskStatus`, `Plan`, `ValidationResult`, `ExecutionResult`, `AgentSpec` |
| `intent.py` | `LanguageDetector` (script ranges: en/hi/ml/ta/ur-IN), `IntentParser` (scored keyword matching, coordinate/region + `from X to Y` parsing, multi-turn merge) |
| `agents.py` | Static `AgentSpec` catalog, `ToolRegistry` boundary (`ToolBus` with per-run tool-call budget), seven data handlers + `verifier` |
| `planner.py` | Data-driven plan builder from the capability matrix |
| `validator.py` | Existence, tool-registration, cycle (Kahn), duplicate, and risk+verifier checks |
| `executor.py` | Dependency-ordered (Kahn-like) DAG execution with bounded asyncio parallelism, per-task retry policy, timeouts, max-tasks guard, budget enforcement |
| `domain.py` | `verify_claims` / `extract_claims` - deterministic number-to-evidence tracing |
| `context.py` | `InMemoryContextRepository` (tests) and `PgContextRepository` (production multi-turn) |
| `trace.py` | Bounded `Tracer` event log |
| `synthesis.py` | Reads only executor evidence; safety guidance tied to the risk profile's hard-constraint flag |
| `orchestrator.py` | `OrchestratorService` composition root; `get_orchestrator_service()` singleton |
| `routers/orchestrate.py` | `POST /api/v1/orchestrate` (query params: `message`, `conversation_id`, `request_id`) |

## 2. Intent + multi-turn

- Keyword scoring is transparent and fixed; ties resolve safety-first; a zero
  match falls back to `briefing`; a missing location becomes a `needs_input`
  turn (`"Which location are you asking about?"`) instead of a dead end.
- Region anchors are deterministic constants (Goa, Mumbai, Kochi, ...).
  `from X to Y` routes populate intent `origin`/`location`.
- Multi-turn merge fills a location/language from the previous turn's context
  record only when this turn supplied none (`merged_from_context` reported).

## 3. Agents and the MCP boundary

- Data agents may call **only** registered MCP tools, through a `ToolBus` that
  wraps `ToolRegistry.invoke` (passing `request_id`/`conversation_id` for
  evidence) and enforces the run's tool-call budget.
- Agent -> tools mapping:

| Agent | MCP / domain steps |
|---|---|
| `marine_intelligence` | `marine.get_fused_state` |
| `weather_hazard` | `safety.marine_safety_check` + `marine.get_fused_state` |
| `fisheries_intelligence` | `marine.get_fused_state` + `analytics.favorability` |
| `maritime_safety` | `safety.marine_safety_check` + `analytics.risk_profile` + `marine.get_fused_state` |
| `scenario_whatif` | `marine.get_fused_state` (per option) + scenario domain comparison |
| `route_intelligence` | `geospatial.restrictions_near_route` + endpoint `marine.get_fused_state` |
| `knowledge_rag` | `knowledge.search` |
| `verifier` | deterministic `domain.verify_claims` |

The new `analytics.risk_profile` MCP tool (tool count 19 -> 20) builds a real
`FusedMarineState`, reuses caller-fetched active warnings/restrictions when
provided, and runs the Risk Engine (hard constraints always override
environmental scores).

## 4. Planning, validation, execution

- **Planner**: `Intent -> required capabilities -> (agent, tool)` pairs from
  the declared capability matrix. Safety plans assemble
  `maritime_safety + knowledge_rag + verifier`; route plans add `verifier`;
  the verifier task depends on every data task.
- **Validator**: every agent exists, every declared tool is registered on the
  ToolBus, no duplicate task ids, no cycles (Kahn over dependencies), and
  safety/route plans carry both the risk capability and the verifier step.
- **Executor**: ready tasks run in bounded `asyncio.gather` batches; transient
  failures retry up to `max_retries` per task (bounded total); per-task
  `wait_for` timeouts; plan size and tool-call budgets enforced; failures are
  surfaced honestly as `partial`/`aborted` with the task table.
- **Verifier**: claims are extracted verbatim from tool outputs; every number
  must appear in the run's evidence within 0.001 tolerance. A hard-constraint
  safety response is structurally incapable of printing SAFE.

## 5. Configuration (`app/config.py`)

`orchestrator_max_tasks` (12), `orchestrator_max_tool_calls` (30),
`orchestrator_max_retries` (2), `orchestrator_max_total_retries` (6),
`orchestrator_max_repairs` (2), `orchestrator_parallel` (4),
`orchestrator_timeout_seconds` (60), `orchestrator_task_timeout_seconds` (30),
`orchestrator_planner_llm_enabled` (False).

The planner is fully deterministic by default; `orchestrator_planner_llm_enabled`
exists as an explicit opt-in for a future LLM planner, never a silent default.

## 6. Response contract

`200` always returns: `request_id`, `conversation_id`, `intent`, `language`,
`status` (`success` | `partial` | `aborted` | `needs_input` | `unavailable` |
`error` | `invalid`), `message`, `sections`, `verification` (`all_verified`,
`checked`, `failed_claims`), `tool_calls`, `duration_ms`, `notes`. Partial
failures are described, never hidden.

## 7. Tests

`tests/test_orchestration.py` (30 tests) is DB/network-free: a duck-typed fake
`ToolRegistry` returns deterministic envelopes of the same shape the MCP
boundary produces, and context is the in-memory repository. Coverage includes
intent detection/merging, planner/validator failure modes (unknown agent,
duplicates, cycles, missing risk), claim tracing, executor retries/limits
(task cap, tool budget), synthesis honesty under hard constraints, and full
service round-trips (safety, fishing, knowledge, route, needs-input,
multi-turn location, language persistence, validation failure).

**Regression:** `python -m pytest tests -q` = **194 passed, 2 skipped**
(Phase 3.5 baseline 161; +30 orchestration, +1 risk-profile tool, +2 MCP
updates).

## 8. Compliance matrix

| Guardrail | Where enforced |
|---|---|
| Agents only reach registered MCP tools | `ToolBus` wraps `ToolRegistry.invoke` |
| No fabricated numbers in answers | `verifier` traces claims to run evidence |
| Safety plans cannot print SAFE under hard constraints | `synthesis._safety_guidance` reads `hard_constraint` |
| Bounded execution | config limits + `Executor` guards |
| Multi-turn memory is explicit | `InMemory`/`PgContextRepository` with per-turn write |
| Honest availability | `needs_input` / `unavailable` / `partial` statuses |
| /api/v1/mcp/* and legacy `app/agents/` untouched | all Phase 4 code is additive |