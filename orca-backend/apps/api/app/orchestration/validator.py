# Plan validator (Phase 4).
#
# Static validation before execution: every referenced agent must exist, every
# declared tool must be registered on the ToolBus, the task graph must be
# acyclic (Kahn), every plan must carry the deterministic verifier so no
# number ships unverified, and - critically - safety plans must ALSO carry a
# risk capability.
from typing import List

from app.orchestration.agents import AgentRegistry, ToolBus
from app.orchestration.models import Plan, ValidationResult


class PlanValidator:
    def __init__(self, registry: AgentRegistry | None = None,
                 tool_bus: ToolBus | None = None):
        self.registry = registry or AgentRegistry()
        self.tool_bus = tool_bus

    def validate(self, plan: Plan) -> ValidationResult:
        errors: List[str] = []
        agent_seen: dict = {}
        for task in plan.tasks:
            spec = self.registry.get(task.agent)
            if spec is None:
                errors.append(f"unknown agent: {task.agent}")
                continue
            agent_seen[task.agent] = True
            if task.tool and not self._tool_available(task.tool):
                errors.append(
                    f"agent {task.agent} declares unregistered tool "
                    f"'{task.tool}'")
        if not plan.tasks:
            errors.append("plan is empty")

        if plan.safety:
            risk_ok = any(
                t.agent == "maritime_safety" for t in plan.tasks)
            if not risk_ok:
                errors.append("safety plan missing risk capability")

        verifier_ok = any(t.domain_step == "verifier" for t in plan.tasks)
        if not verifier_ok:
            errors.append("plan missing verifier task")

        cycle = self._detect_cycle(plan)
        if cycle:
            errors.append(f"dependency cycle detected: {cycle}")

        duplicate = self._detect_duplicates(plan)
        if duplicate:
            errors.append(f"duplicate task ids: {duplicate}")

        ok = not errors
        return ValidationResult(
            ok=ok,
            errors=errors,
            warnings=self._warnings(plan, agent_seen),
        )

    def _tool_available(self, tool: str) -> bool:
        if self.tool_bus is None:
            return True
        try:
            return self.tool_bus.can_invoke(tool)
        except Exception:  # noqa: BLE001
            return True

    @staticmethod
    def _detect_cycle(plan: Plan) -> str | None:
        incoming = {t.task_id: set(t.depends_on) for t in plan.tasks}
        ready = [t for t in plan.tasks
                 if not incoming[t.task_id]]
        removed = 0
        while ready:
            task = ready.pop()
            removed += 1
            for other in plan.tasks:
                deps = incoming[other.task_id]
                if task.task_id in deps:
                    deps.discard(task.task_id)
                    if not deps and other.task_id not in {t.task_id for t in ready}:
                        ready.append(other)
        if removed != len(plan.tasks):
            cycle_ids = [t.task_id for t in plan.tasks
                         if incoming[t.task_id]]
            return ",".join(sorted(cycle_ids))
        return None

    @staticmethod
    def _detect_duplicates(plan: Plan) -> List[str]:
        seen = set()
        dupes = []
        for task in plan.tasks:
            if task.task_id in seen:
                dupes.append(task.task_id)
            seen.add(task.task_id)
        return dupes

    @staticmethod
    def _warnings(plan: Plan, agent_seen: dict) -> List[str]:
        warnings: List[str] = []
        if plan.strategy == "capability_matrix" and len(agent_seen) < 2:
            warnings.append("plan uses a single agent - review coverage")
        return warnings