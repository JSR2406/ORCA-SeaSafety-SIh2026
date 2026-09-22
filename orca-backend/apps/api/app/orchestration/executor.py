# Deterministic DAG executor for Phase 4 plans.
#
# Scheduling is dependency ordered (Kahn-like), runs ready tasks with bounded
# asyncio parallelism, applies per-task retry policies for transient failures,
# and caps total retries so a run is bounded.  The verifier task is populated
# with the evidence collected this run, so no number ever ships against a
# value the tools did not return.
import asyncio
import time
from typing import Any, Dict, List, Optional, Set

from app.orchestration.agents import (
    LimitExceededError, ToolBus, get_agent_registry, get_handler)
from app.orchestration.domain import extract_claims
from app.orchestration.models import (
    ExecutionResult, Plan, Task, TaskStatus)
from app.orchestration.trace import Tracer

TRANSIENT_ERRORS = ("connection", "timeout", "temporary", "retry",
                    "momentarily unavailable")


class ExecutionLimitsError(RuntimeError):
    pass


class ToolAuthorizationError(RuntimeError):
    """Phase 7 - a handler reached for a tool outside its agent's allow-list.

    Non-retryable by design: the executor records the task as failed and the
    run continues (partial) unless a mandatory task aborts it.  No unauthorized
    tool call ever reaches the registry or the trace stream.
    """

    def __init__(self, agent: str, tool: str):
        super().__init__(
            f"agent '{agent}' is not authorized to invoke tool '{tool}'")


class AuthorizedToolBus:
    """Phase 7 per-agent authorization envelope over the ToolBus.

    Any handler running under an agent may invoke only the tools declared in
    that agent's AgentSpec allow-list.  A disallowed call raises
    ToolAuthorizationError BEFORE the registry is contacted and BEFORE any
    tool_start trace event, so unauthorized tools are never executed, never
    budgeted and never streamed.  The inner bus still owns the call budget.
    """

    def __init__(self, inner: ToolBus, agent: str, allowed: Set[str]):
        self._inner = inner
        self._agent = agent
        self._allowed = allowed

    async def invoke(self, tool: str, arguments: Optional[Dict[str, Any]] = None
                     ) -> Dict[str, Any]:
        if tool not in self._allowed:
            raise ToolAuthorizationError(self._agent, tool)
        return await self._inner.invoke(tool, arguments)

    def can_invoke(self, tool: str) -> bool:
        return tool in self._allowed and self._inner.can_invoke(tool)

    def available_tools(self) -> List[str]:
        return [t for t in self._inner.available_tools() if t in self._allowed]

    @property
    def calls(self) -> int:
        return self._inner.calls

    @property
    def max_tool_calls(self) -> int:
        return self._inner.max_tool_calls


class Executor:
    def __init__(self, tool_bus: ToolBus, tracer: Tracer | None = None,
                 max_parallel: int = 4,
                 max_retries_per_task: int = 2,
                 max_total_retries: int = 6,
                 max_tasks: int = 12,
                 task_timeout_seconds: float = 30.0):
        self.tool_bus = tool_bus
        self.tracer = tracer or Tracer()
        self.max_parallel = max_parallel
        self.max_retries_per_task = max_retries_per_task
        self.max_total_retries = max_total_retries
        self.max_tasks = max_tasks
        self.task_timeout_seconds = task_timeout_seconds

    # ------------------------------------------------------------- public
    async def run(self, plan: Plan) -> ExecutionResult:
        start = time.monotonic()
        if len(plan.tasks) > self.max_tasks:
            raise ExecutionLimitsError(
                f"plan exceeds max tasks ({len(plan.tasks)} > {self.max_tasks})")

        remaining = {t.task_id: set(t.depends_on) for t in plan.tasks}
        outcome: Dict[str, Dict[str, Any]] = {
            t.task_id: {"agent": t.agent, "status": self._status_name(TaskStatus.PENDING),
                        "attempts": 0, "retries": 0}
            for t in plan.tasks}
        evidence: Dict[str, Any] = {}
        errors: List[str] = []
        total_retries = 0
        self._total_retries_used = 0

        while len(outcome) > 0:
            ready = [t for t in plan.tasks
                     if outcome[t.task_id]["status"] == "pending"
                     and all(outcome[d]["status"] == "succeeded"
                             for d in remaining[t.task_id])]
            if not ready:
                for task in plan.tasks:
                    if outcome[task.task_id]["status"] == "pending":
                        outcome[task.task_id]["status"] = "failed"
                        outcome[task.task_id]["error"] = \
                            "dependency blocked (cycle)"
                        errors.append(
                            f"{task.task_id}: dependency blocked (cycle)")
                break

            batch = ready[: self.max_parallel]
            results = await asyncio.gather(
                *(self._run_task(task, plan, evidence) for task in batch),
                return_exceptions=True,
            )
            for task, res in zip(batch, results):
                if isinstance(res, Exception):
                    outcome[task.task_id]["status"] = "failed"
                    outcome[task.task_id]["error"] = \
                        str(res) or res.__class__.__name__
                    errors.append(
                        f"{task.task_id}: {outcome[task.task_id]['error']}")
                    outcome[task.task_id]["retries"] = task.retry_count
                    total_retries += task.retry_count
                else:
                    outcome[task.task_id]["status"] = "succeeded"
                    outcome[task.task_id]["retries"] = task.retry_count
                    total_retries += task.retry_count
                    key = self._evidence_key(task)
                    evidence[key] = res
                    for follower in plan.tasks:
                        deps = remaining.get(follower.task_id)
                        if deps is not None:
                            deps.discard(task.task_id)

        succeeded = sum(1 for v in outcome.values()
                        if v["status"] == "succeeded")
        duration_ms = int((time.monotonic() - start) * 1000)
        verification = self._extract_verification(plan, evidence)
        return ExecutionResult(
            status="success" if not errors
            else ("partial" if succeeded else "aborted"),
            tasks=outcome,
            evidence=evidence,
            tool_calls=self.tool_bus.calls,
            errors=errors,
            verification=verification,
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------ internal
    async def _run_task(self, task: Task, plan: Plan,
                        evidence: Dict[str, Any]) -> Dict[str, Any]:
        handler = get_handler(task.agent)
        if handler is None:
            raise RuntimeError(f"no handler for agent {task.agent}")
        if task.agent == "verifier":
            task.args = {"claims": extract_claims(
                plan.intent.name.value, evidence),
                "evidence": dict(evidence)}
        elif task.tool and self._accepts_run_id(task.tool):
            run_id = self.tool_bus.request_id
            if run_id:
                task.args = {**(task.args or {}), "query_run_id": run_id}
        bus = self._authorized_bus(task.agent)
        last: Optional[Exception] = None
        for attempt in range(task.max_retries + 1):
            task.attempts = attempt + 1
            task.retry_count = attempt
            if self.tracer:
                await self.tracer.event(
                    "task_start", source=task.task_id,
                    payload={"attempt": attempt + 1})
            is_verifier = task.agent == "verifier" or task.domain_step == "verifier"
            if is_verifier and self.tracer:
                await self.tracer.event(
                    "verification_start", source=task.task_id)
            try:
                res = await asyncio.wait_for(
                    handler(bus, task, plan.intent),
                    timeout=task.timeout_seconds)
                if is_verifier and self.tracer:
                    await self.tracer.event(
                        "verification_completed", source=task.task_id,
                        payload={"checked": res.get("checked", 0),
                                 "all_verified": res.get("all_verified")})
                if self.tracer:
                    await self.tracer.event(
                        "task_completed", source=task.task_id)
                res = dict(res)
                res.setdefault("_tool", task.tool or task.domain_step or "domain")
                return res
            except Exception as exc:  # noqa: BLE001 - bounded retries below
                last = exc
                if is_verifier and self.tracer:
                    await self.tracer.event(
                        "verification_failed", source=task.task_id)
                if self.tracer:
                    await self.tracer.event(
                        "task_failed", source=task.task_id,
                        payload={"attempt": attempt + 1,
                                 "error": str(exc)[:300]})
                if not self._retryable(exc) \
                        or task.retry_count >= task.max_retries \
                        or self.tool_bus.calls >= self.tool_bus.max_tool_calls \
                        or self._total_retries_used >= self.max_total_retries:
                    break
                self._total_retries_used += 1
        assert last is not None
        raise last

    @staticmethod
    def _retryable(exc: Exception) -> bool:
        if isinstance(exc, LimitExceededError):
            return False
        message = str(exc).lower()
        return any(token in message for token in TRANSIENT_ERRORS)

    def _accepts_run_id(self, tool: str) -> bool:
        try:
            meta = self.tool_bus.registry.get(tool)
        except Exception:  # noqa: BLE001 - duck-typed fakes may lack introspection
            return False
        model = getattr(meta, "input_model", None)
        if model is None:
            return False
        try:
            return "query_run_id" in getattr(model, "__fields__", {})
        except Exception:  # noqa: BLE001
            return False

    def _authorized_bus(self, agent: str) -> ToolBus:
        """Phase 7: bound every agent task to its declared tool allow-list."""
        spec = get_agent_registry().get(agent)
        if spec is None or not spec.tools:
            return self.tool_bus
        return AuthorizedToolBus(self.tool_bus, agent, set(spec.tools))

    @staticmethod
    def _evidence_key(task: Task) -> str:
        return task.tool or task.domain_step or task.task_id

    @staticmethod
    def _status_name(status: TaskStatus) -> str:
        mapping = {
            TaskStatus.PENDING: "pending",
            TaskStatus.SUCCEEDED: "succeeded",
            TaskStatus.FAILED: "failed",
            TaskStatus.SKIPPED: "skipped",
        }
        return mapping.get(status, "pending")

    @staticmethod
    def _extract_verification(plan: Plan,
                              evidence: Dict[str, Any]) -> Dict[str, Any] | None:
        verifier_task = next(
            (t for t in plan.tasks if t.domain_step == "verifier"), None)
        if verifier_task is None:
            return None
        result = evidence.get("verifier")
        if not isinstance(result, dict):
            return None
        return {
            "all_verified": result.get("all_verified", False),
            "checked": result.get("checked", 0),
            "failed_claims": result.get("failed_claims", []),
        }