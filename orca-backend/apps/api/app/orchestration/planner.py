# Capability-matrix planner (Phase 4).
#
# The plan is derived from the DECLARED capability matrix (agent capabilities
# -> tools) - a data structure, not an if/elif keyword router.  An optional LLM
# planner exists behind a config flag, but the deterministic matrix is the
# default and the only mode used when no LLM key is configured.
from typing import Any, Dict, List

from app.orchestration.agents import get_agent_registry
from app.orchestration.intent import IntentValidator
from app.orchestration.models import AgentSpec, Intent, IntentName, Plan, Task

# Intent -> capabilities that MUST be present for a safe answer.
_INTENT_CAPABILITIES: Dict[IntentName, List[str]] = {
    IntentName.BRIEFING: ["fusion"],
    IntentName.SAFETY: ["safety", "risk", "knowledge"],
    IntentName.FISHING: ["fishing", "knowledge"],
    IntentName.ROUTE: ["route"],
    IntentName.SCENARIO: ["scenario"],
    IntentName.KNOWLEDGE: ["knowledge"],
    IntentName.PFZ: ["pfz", "knowledge"],
    IntentName.PRODUCTIVITY: ["productivity", "knowledge"],
}


class Planner:
    def __init__(self, registry=None, intent_validator=None,
                 llm_enabled: bool = False):
        self.registry = registry or get_agent_registry()
        self.intent_validator = intent_validator or IntentValidator()
        self.llm_enabled = llm_enabled

    def plan(self, intent: Intent) -> Plan:
        plan = Plan(intent=intent, strategy="capability_matrix",
                    safety=intent.name == IntentName.SAFETY)
        assigned: Dict[str, str] = {}
        for capability in _INTENT_CAPABILITIES.get(intent.name, []):
            agent = self._pick_agent(capability, assigned)
            if agent is None:
                continue
            assigned[agent] = capability
            task = self._build_data_task(intent, agent, capability)
            if task is not None:
                plan.tasks.append(task)
        # Every plan carries the deterministic verifier step so every number
        # the response surfaces is traced back to a tool output.  The verifier
        # is only useful when there is evidence to check.
        if plan.tasks:
            plan.tasks.append(self._verifier_task())
        self._wire_dependencies(plan.tasks)
        return plan

    # ---------------------------------------------------------------- helpers
    def _pick_agent(self, capability: str, assigned: Dict[str, str]) -> str | None:
        for spec in self.registry.capability_agents(capability):
            if spec.name == "verifier":
                continue
            primary_capability = assigned.get(spec.name)
            if primary_capability is None or primary_capability == capability:
                return spec.name
        return None

    def _build_data_task(self, intent: Intent, agent: str,
                         capability: str) -> Task | None:
        spec = self.registry.get(agent)
        if spec is None:
            return None
        tool = self._tool_for(spec, capability)
        args = self._resolve_args(intent, tool, agent)
        if args is None:
            return None
        return Task(
            task_id=self._task_id(agent, capability),
            agent=agent,
            tool=tool,
            max_retries=2,
            timeout_seconds=30.0,
            safety_step=capability in ("safety", "risk"),
            args=args,
        )

    @staticmethod
    def _tool_for(spec: AgentSpec, capability: str) -> str | None:
        order = {
            "marine.get_fused_state": ["fusion", "briefing", "hazard", "fishing",
                                       "route", "scenario"],
            "safety.marine_safety_check": ["safety", "hazard", "route"],
            "analytics.favorability": ["fishing"],
            "analytics.risk_profile": ["risk"],
            "geospatial.restrictions_near_route": ["route"],
            "marine.pfz_nearest": ["pfz"],
            "analytics.fishing_potential": ["pfz"],
            "analytics.productivity": ["productivity"],
            "knowledge.search": ["knowledge"],
            "knowledge.query": ["knowledge"],
        }
        for tool, capabilities in order.items():
            if tool in spec.tools and capability in capabilities:
                return tool
        return None

    def _resolve_args(self, intent: Intent, tool: str | None,
                      agent: str) -> Dict[str, Any] | None:
        if tool == "marine.get_fused_state":
            if not intent.location:
                return None
            return {"lat": intent.location["lat"],
                    "lon": intent.location["lon"]}
        if tool == "safety.marine_safety_check":
            if not intent.location:
                return None
            return {"lat": intent.location["lat"],
                    "lon": intent.location["lon"]}
        if tool == "analytics.favorability":
            if not intent.location:
                return None
            return {"lat": intent.location["lat"],
                    "lon": intent.location["lon"],
                    "target": intent.target or "fishing"}
        if tool == "analytics.risk_profile":
            if not intent.location:
                return None
            return {"lat": intent.location["lat"],
                    "lon": intent.location["lon"]}
        if tool == "geospatial.restrictions_near_route":
            if not (intent.origin and intent.location):
                return None
            return {
                "route": [[intent.origin["lat"], intent.origin["lon"]],
                          [intent.location["lat"], intent.location["lon"]]],
            }
        if tool in ("marine.pfz_nearest", "analytics.fishing_potential",
                    "analytics.productivity"):
            if not intent.location:
                return None
            return {"lat": intent.location["lat"],
                    "lon": intent.location["lon"]}
        if tool == "knowledge.search":
            return {"query": intent.query or "marine safety advisory",
                    "limit": 5}
        if tool == "knowledge.query":
            return {"query": intent.query or "marine safety advisory",
                    "top_k": 5}
        return {}

    def _verifier_task(self) -> Task:
        return Task(task_id="verifier-verify",
                    agent="verifier", domain_step="verifier",
                    max_retries=1, timeout_seconds=5.0,
                    args={"claims": []})

    def _wire_dependencies(self, tasks: List[Task]) -> None:
        data_tasks = [t for t in tasks if t.domain_step is None]
        for task in tasks:
            if task.domain_step == "verifier":
                task.depends_on = [t.task_id for t in data_tasks
                                   if t.task_id != task.task_id]

    @staticmethod
    def _task_id(agent: str, capability: str) -> str:
        return f"{agent}:{capability}"