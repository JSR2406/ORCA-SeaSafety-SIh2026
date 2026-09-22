# Phase 4 agents: a registry of AgentSpec entries bound to deterministic
# handlers.  Every data agent reaches the real world ONLY through the MCP
# ToolBus boundary (registered MCP tools).  Domain steps (risk profile,
# scenario comparison, verifier) are deterministic computation over the
# evidence those tool calls return - never fabricated values.
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.orchestration.models import AgentSpec, Intent, Task

Handler = Callable[..., Awaitable[Dict[str, Any]]]


# ---------------------------------------------------------------- tool bus
class LimitExceededError(RuntimeError):
    pass


class ToolBus:
    """The single boundary agents may use to reach MCP tools.

    Wraps a ToolRegistry-compatible object (duck-typed for tests) and enforces
    the tool-call budget for the run.  ToolRegistry.invoke already handles the
    evidence recording and the structured envelope.
    """

    def __init__(self, registry, request_id: Optional[str] = None,
                 conversation_id: Optional[str] = None,
                 max_tool_calls: int = 30, tracer=None):
        self.registry = registry
        self.request_id = request_id
        self.conversation_id = conversation_id
        self.max_tool_calls = max_tool_calls
        self.calls = 0
        self.tracer = tracer

    async def invoke(self, tool: str, arguments: Optional[Dict[str, Any]] = None
                     ) -> Dict[str, Any]:
        if self.calls >= self.max_tool_calls:
            raise LimitExceededError(
                f"tool-call budget exhausted ({self.max_tool_calls})")
        self.calls += 1
        if self.tracer is not None:
            await self.tracer.event("tool_start", source=tool,
                                    payload={"tool": tool})
        try:
            result = await self.registry.invoke(
                tool,
                arguments or {},
                request_id=self.request_id,
                conversation_id=self.conversation_id,
            )
        except Exception:  # noqa: BLE001 - re-raise after streaming the failure
            if self.tracer is not None:
                await self.tracer.event("tool_failed", source=tool,
                                        payload={"tool": tool})
            raise
        if self.tracer is not None:
            await self.tracer.event("tool_call", source=tool,
                                    payload={"arguments": arguments or {}})
            await self.tracer.event("tool_completed", source=tool,
                                    payload={"tool": tool})
        return result

    def can_invoke(self, tool: str) -> bool:
        return tool in self.available_tools()

    def available_tools(self) -> List[str]:
        try:
            return list(self.registry.names())
        except Exception:  # noqa: BLE001 - duck-typed fakes may map tools directly
            return []


# --------------------------------------------------------------- registry
# Static capability catalog.  Each agent declares the tools it may call and an
# optional deterministic domain step it may run on returned evidence.
_SPECS: Dict[str, AgentSpec] = {}


def register_agent(spec: AgentSpec) -> None:
    _SPECS[spec.name] = spec


def _bootstrap() -> None:
    if _SPECS:
        return
    register_agent(AgentSpec(
        name="marine_intelligence",
        description="Canonical fused marine state at a point (waves, wind, "
                    "current, SST) with per-variable provider provenance.",
        capabilities=["briefing", "fusion"],
        tools=["marine.get_fused_state"],
        priority=1))
    register_agent(AgentSpec(
        name="weather_hazard",
        description="Hazard view: fused weather/wave state plus active marine "
                    "warnings and restricted-area containment for a point.",
        capabilities=["hazard", "briefing"],
        tools=["marine.get_fused_state", "safety.marine_safety_check"],
        priority=2))
    register_agent(AgentSpec(
        name="fisheries_intelligence",
        description="Fishing favorability from real fused-state variables with "
                    "per-variable weights and rationale.",
        capabilities=["fishing"],
        tools=["marine.get_fused_state", "analytics.favorability"],
        priority=3))
    register_agent(AgentSpec(
        name="maritime_safety",
        description="Safety advisory: risk profile (Risk Engine with hard "
                    "constraints) plus active warnings and restricted areas. "
                    "Never issues false SAFE verdicts.",
        capabilities=["risk", "safety"],
        tools=["safety.marine_safety_check", "analytics.risk_profile",
               "marine.get_fused_state", "restriction.dynamic_active"],
        priority=0))
    register_agent(AgentSpec(
        name="scenario_whatif",
        description="Deterministic what-if comparison of real fused states "
                    "describes differences in observed variables only.",
        capabilities=["scenario"],
        tools=["marine.get_fused_state"],
        domain="scenario",
        priority=4))
    register_agent(AgentSpec(
        name="route_intelligence",
        description="Route-level advisories: restricted areas along the "
                    "planned course, live dynamic restrictions, plus endpoint "
                    "marine states.",
        capabilities=["route"],
        tools=["geospatial.restrictions_near_route", "marine.get_fused_state",
               "restriction.dynamic_active"],
        priority=5))
    register_agent(AgentSpec(
        name="pfz_intelligence",
        description="Nearest PFZ advisory zone (deterministic rank by real "
                    "stored geometry), its distance, and the fishing potential "
                    "at the zone centroid.",
        capabilities=["pfz"],
        tools=["marine.pfz_nearest", "marine.get_fused_state",
               "analytics.fishing_potential"],
        priority=2))
    register_agent(AgentSpec(
        name="productivity_intelligence",
        description="SRP productivity index from chlorophyll + SST (+ upwelling "
                    "proxy) with per-variable contributions and data caveats.",
        capabilities=["productivity"],
        tools=["marine.get_fused_state", "analytics.productivity"],
        priority=2))
    register_agent(AgentSpec(
        name="knowledge_rag",
        description="Hybrid retrieval over the curated knowledge base with "
                    "verbatim citations and reported retrieval mode.",
        capabilities=["knowledge", "enrichment"],
        tools=["knowledge.search", "knowledge.query"],
        priority=6))
    register_agent(AgentSpec(
        name="verifier",
        description="Deterministic claim verifier: every number surfaced in "
                    "the answer must trace to a value returned by a tool.",
        capabilities=["verification"],
        tools=[],
        domain="verifier",
        priority=9))


_bootstrap()


class AgentRegistry:
    """Agent catalog used by the planner and the validator."""

    def get(self, name: str) -> Optional[AgentSpec]:
        return _SPECS.get(name)

    def names(self) -> List[str]:
        return list(_SPECS.keys())

    def all(self) -> List[AgentSpec]:
        return list(_SPECS.values())

    def tool_for(self, agent: str, capability: str) -> Optional[str]:
        spec = self.get(agent)
        if spec is None:
            return None
        return next((t for t in spec.tools
                     if capability in _TOOL_CAPABILITIES.get(t, [])), None)

    def capability_agents(self, capability: str) -> List[AgentSpec]:
        return sorted(
            [s for s in _SPECS.values() if capability in s.capabilities],
            key=lambda s: s.priority)


_TOOL_CAPABILITIES = {
    "marine.get_fused_state": ["fusion", "briefing", "hazard", "fishing", "route", "scenario"],
    "safety.marine_safety_check": ["safety", "hazard", "route"],
    "analytics.favorability": ["fishing"],
    "analytics.risk_profile": ["risk"],
    "geospatial.restrictions_near_route": ["route"],
    "restriction.dynamic_active": ["route"],
    "marine.pfz_nearest": ["pfz"],
    "analytics.fishing_potential": ["pfz"],
    "analytics.productivity": ["productivity"],
    "knowledge.search": ["knowledge"],
    "knowledge.query": ["knowledge"],
}


def get_agent_registry() -> AgentRegistry:
    return AgentRegistry()


# ---------------------------------------------------------------- handlers
async def _call(bus: ToolBus, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
    return await bus.invoke(tool, args)


async def handle_marine_intelligence(bus: ToolBus, task: Task,
                                     intent: Intent) -> Dict[str, Any]:
    return await _call(bus, "marine.get_fused_state", task.args)


async def handle_weather_hazard(bus: ToolBus, task: Task,
                                intent: Intent) -> Dict[str, Any]:
    safe = await _call(bus, "safety.marine_safety_check",
                       {"lat": task.args["lat"], "lon": task.args["lon"]})
    state = await _call(bus, "marine.get_fused_state", task.args)
    return {"marine_safety_check": safe, "fused_state": state}


async def handle_fisheries_intelligence(bus: ToolBus, task: Task,
                                        intent: Intent) -> Dict[str, Any]:
    lat, lon = task.args["lat"], task.args["lon"]
    favorability = await _call(bus, "analytics.favorability", {
        "lat": lat, "lon": lon,
        "target": intent.target or "fishing"})
    state = await _call(bus, "marine.get_fused_state",
                        {"lat": lat, "lon": lon})
    return {"favorability": favorability, "fused_state": state}


async def handle_maritime_safety(bus: ToolBus, task: Task,
                                 intent: Intent) -> Dict[str, Any]:
    lat, lon = task.args["lat"], task.args["lon"]
    safe = await _call(bus, "safety.marine_safety_check",
                       {"lat": lat, "lon": lon})
    safe_data = (safe.get("data") or {}) if isinstance(safe, dict) else {}
    # Phase 7: ACTIVE dynamic restrictions are authoritative too - they are
    # merged into the risk profile's restriction set so a live official
    # restriction drives the same hard-constraint verdict as static ones.
    dynamic = None
    try:
        dynamic = await _call(bus, "restriction.dynamic_active",
                              {"lat": lat, "lon": lon,
                               "include_static_geofences": True})
    except (KeyError, RuntimeError):
        dynamic = None
    active_dynamic = []
    if isinstance(dynamic, dict):
        dyn_data = dynamic.get("data") if isinstance(dynamic.get("data"), dict) \
            else dynamic
        active_dynamic = [r for r in (dyn_data.get("active_dynamic") or [])
                          if isinstance(r, dict)
                          and str(r.get("status") or "active").lower() == "active"]
    risk = await _call(bus, "analytics.risk_profile", {
        "lat": lat, "lon": lon,
        "active_warnings": safe_data.get("active_warnings", []),
        "active_restrictions":
            list(safe_data.get("restriction_details", [])) + active_dynamic,
    })
    state = await _call(bus, "marine.get_fused_state",
                        {"lat": lat, "lon": lon})
    return {"marine_safety_check": safe, "risk_profile": risk,
            "fused_state": state,
            "dynamic_restrictions": dynamic if dynamic is not None else {}}


async def handle_scenario_whatif(bus: ToolBus, task: Task,
                                 intent: Intent) -> Dict[str, Any]:
    states = []
    points = task.args.get("points") or [task.args]
    for point in points[:2]:
        states.append(await _call(bus, "marine.get_fused_state", point))
    return {"states": states}


async def handle_route_intelligence(bus: ToolBus, task: Task,
                                    intent: Intent) -> Dict[str, Any]:
    route_points = [[float(p[0]), float(p[1])]
                    for p in (intent.route or [])][:2]
    args = dict(task.args)
    if route_points:
        args["route"] = list(route_points)
    route = await _call(bus, "geospatial.restrictions_near_route", args)
    endpoints = []
    dynamic_hits = []
    for lat, lon in route_points:
        endpoints.append(await _call(
            bus, "marine.get_fused_state", {"lat": lat, "lon": lon}))
        try:
            dyn = await _call(bus, "restriction.dynamic_active",
                              {"lat": lat, "lon": lon,
                               "include_static_geofences": True})
            dyn_data = dyn.get("data") if isinstance(dyn, dict) and \
                isinstance(dyn.get("data"), dict) else dyn
            if isinstance(dyn_data.get("active_dynamic"), list) \
                    and dyn_data.get("active_dynamic"):
                dynamic_hits.append(dyn)
        except (KeyError, RuntimeError):
            continue
    return {"restrictions_near_route": route,
            "endpoint_states": endpoints,
            "dynamic_restrictions": dynamic_hits}


async def handle_pfz_intelligence(bus: ToolBus, task: Task,
                                  intent: Intent) -> Dict[str, Any]:
    lat, lon = task.args["lat"], task.args["lon"]
    pfz = await _call(bus, "marine.pfz_nearest",
                      {"lat": lat, "lon": lon,
                       "radius_km": task.args.get("radius_km", 200.0),
                       "limit": task.args.get("limit", 3)})
    data = pfz.get("data") or pfz
    candidates = data.get("candidates") or []
    states = []
    potentials = []
    for cand in candidates[:1]:
        loc = cand.get("location")
        if not loc:
            continue
        state = await _call(bus, "marine.get_fused_state",
                            {"lat": loc["lat"], "lon": loc["lon"]})
        potential = await _call(bus, "analytics.fishing_potential",
                                {"lat": loc["lat"], "lon": loc["lon"]})
        states.append(state)
        potentials.append(potential)
    return {"pfz_nearest": pfz, "states": states, "potentials": potentials}


async def handle_productivity_intelligence(bus: ToolBus, task: Task,
                                           intent: Intent) -> Dict[str, Any]:
    state = await _call(bus, "marine.get_fused_state", task.args)
    prod = await _call(bus, "analytics.productivity", task.args)
    return {"productivity": prod, "fused_state": state}


async def handle_knowledge_rag(bus: ToolBus, task: Task,
                               intent: Intent) -> Dict[str, Any]:
    tool = task.tool or "knowledge.search"
    return await _call(bus, tool, task.args)


async def handle_verifier(bus: ToolBus, task: Task,
                          intent: Intent) -> Dict[str, Any]:
    # Deterministic; evidence is passed in task.args by the executor.
    from app.orchestration.domain import verify_claims

    claims = task.args.get("claims", [])
    if not claims:
        return {"verified": True, "all_verified": True,
                "message": "no numeric claims to verify"}
    evidence = task.args.get("evidence", {})
    result = verify_claims(claims, evidence)
    return result


_HANDLERS: Dict[str, Handler] = {
    "marine_intelligence": handle_marine_intelligence,
    "weather_hazard": handle_weather_hazard,
    "fisheries_intelligence": handle_fisheries_intelligence,
    "maritime_safety": handle_maritime_safety,
    "scenario_whatif": handle_scenario_whatif,
    "route_intelligence": handle_route_intelligence,
    "pfz_intelligence": handle_pfz_intelligence,
    "productivity_intelligence": handle_productivity_intelligence,
    "knowledge_rag": handle_knowledge_rag,
    "verifier": handle_verifier,
}


def get_handler(agent: str) -> Optional[Handler]:
    return _HANDLERS.get(agent)