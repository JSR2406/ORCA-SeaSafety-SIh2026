# Phase 7 - run scenarios/golden cases against the real orchestrator stack.
#
# All pipelines are database- and network-free: the fake ScenarioRegistry is
# the only tool boundary, and the in-memory context repository is used for
# multi-turn cases.  The plan agents (and therefore the authorized tool set for
# Part 6) come from the deterministic Planner, never from a keyword guess.
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.orchestration.context import InMemoryContextRepository
from app.orchestration.intent import IntentParser
from app.orchestration.orchestrator import OrchestratorService
from app.orchestration.planner import Planner
from app.orchestration.stream import StreamTracer, stream_orchestration

from evaluation.datasets import GoldenCase
from evaluation.fixtures import ScenarioRegistry, World
from evaluation.scenarios import Scenario


@dataclass
class Case:
    id: str
    message: str
    world: World
    pipeline: str = "orchestrator"
    title: str = ""
    parts: Tuple[int, ...] = ()
    response: Optional[Dict[str, Any]] = None
    calls: List[tuple] = field(default_factory=list)
    events: Optional[List[Dict[str, Any]]] = None
    second_response: Optional[Dict[str, Any]] = None
    second_calls: List[tuple] = field(default_factory=list)
    expected: Any = None
    error: Optional[str] = None

    @property
    def text(self) -> str:
        payload = self.response or {}
        return " ".join([
            str(payload.get("message") or ""),
            str(payload.get("answer") or ""),
            " ".join(str(l) for s in (payload.get("sections") or [])
                     for l in s.get("lines", [])),
        ])


def allowed_tool_set(message: str) -> Tuple[List[str], set]:
    """Plan (deterministic) -> (agents, union of max allowed tools)."""
    from app.orchestration.agents import AgentRegistry

    intent = IntentParser().parse(message)
    plan = Planner().plan(intent)
    registry = AgentRegistry()
    agents = [t.agent for t in plan.tasks]
    allowed: set = set()
    for agent in agents:
        spec = registry.get(agent)
        if spec is not None:
            allowed |= set(spec.tools)
    return agents, allowed


def run_golden(case: GoldenCase) -> Case:
    return run_scenario_parts(case.id, case.message, case.world,
                              expected=case.expected, title=case.id)


def run_scenario_parts(identifier: str, message: str, world: World, *,
                       expected=None, title: str = "",
                       parts: Tuple[int, ...] = (),
                       pipeline: str = "orchestrator",
                       second_turn: Optional[str] = None) -> Case:
    if pipeline == "stream":
        return _run_stream(identifier, message, world, expected, title, parts)
    if pipeline == "router":
        return _run_router(identifier, message, world, expected, title, parts)
    if pipeline == "repeat":
        return _run_repeat(identifier, message, world, expected, title, parts)
    if pipeline == "twoturn":
        return _run_twoturn(identifier, message, world, expected, title, parts,
                            second_turn)
    return _run_orchestrator(identifier, message, world, expected, title, parts)


def run_scenario(sc: Scenario) -> Case:
    return run_scenario_parts(
        sc.id, sc.message, sc.world, title=sc.title, parts=sc.parts,
        pipeline=sc.pipeline, second_turn=sc.second_turn,
        expected=sc.expected)


# ------------------------------------------------------------- orchestrator
def _run_orchestrator(identifier: str, message: str, world: World, expected,
                      title: str, parts) -> Case:
    registry = ScenarioRegistry(world)
    service = OrchestratorService(
        tool_registry=registry,
        context_repository=InMemoryContextRepository())
    try:
        response = asyncio.run(service.run(message, request_id=f"eval-{identifier}"))
    except Exception as exc:  # noqa: BLE001 - captured for the report
        return Case(identifier, message, world, expected=expected, title=title,
                    parts=parts, error=f"{type(exc).__name__}: {exc}")
    return Case(identifier, message, world, response=response,
                calls=registry.calls, expected=expected, title=title, parts=parts)


async def _run_async(identifier, message, world, expected, title, parts):
    registry = ScenarioRegistry(world)
    service = OrchestratorService(
        tool_registry=registry,
        context_repository=InMemoryContextRepository())
    response = await service.run(message, request_id=f"eval-{identifier}")
    return Case(identifier, message, world, response=response,
                calls=registry.calls, expected=expected, title=title, parts=parts)


# ---------------------------------------------------------------- multi-turn
def _run_twoturn(identifier, message, world, expected, title, parts,
                 second_turn) -> Case:
    registry = ScenarioRegistry(world)
    repo = InMemoryContextRepository()
    service = OrchestratorService(tool_registry=registry,
                                  context_repository=repo)
    conversation_id = f"{identifier}-conv"
    first = asyncio.run(service.run(
        message, request_id=f"eval-{identifier}", conversation_id=conversation_id))
    calls_after_first = list(registry.calls)
    second = asyncio.run(service.run(
        second_turn, request_id=f"eval-{identifier}-2",
        conversation_id=conversation_id))
    return Case(identifier, message, world, response=first,
                calls=calls_after_first, second_response=second,
                second_calls=list(registry.calls),
                expected=expected, title=title, parts=parts)


# ------------------------------------------------------------------ repeat
def _run_repeat(identifier, message, world, expected, title, parts) -> Case:
    a = asyncio.run(_run_async(identifier, message, world, expected, title, parts))
    b = asyncio.run(_run_async(f"{identifier}-r2", message, world, expected,
                               title, parts))
    concurrent = asyncio.run(_run_concurrent(message, world, identifier))
    a.second_response = b.response
    a.second_calls = b.calls
    a.events = concurrent  # list of (response, calls)
    return a


async def _run_concurrent(message, world, identifier):
    async def once(tag):
        world_a = _copy_world(world)
        registry = ScenarioRegistry(world_a)
        service = OrchestratorService(
            tool_registry=registry,
            context_repository=InMemoryContextRepository())
        response = await service.run(message, request_id=f"{tag}")
        return response
    first, second = await asyncio.gather(once(f"eval-{identifier}-c1"),
                                         once(f"eval-{identifier}-c2"))
    return [first, second]


def _copy_world(world: World) -> World:
    return World(
        name=world.name, ocean_rows=list(world.ocean_rows),
        weather_rows=list(world.weather_rows),
        ocean_status=world.ocean_status, weather_status=world.weather_status,
        ocean_confidence=world.ocean_confidence,
        weather_confidence=world.weather_confidence,
        warnings=list(world.warnings), restrictions=list(world.restrictions),
        inside_restricted_area=world.inside_restricted_area,
        suggested=world.suggested, dynamic_active=list(world.dynamic_active),
        static_geofence_hits=list(world.static_geofence_hits),
        route_intersections=list(world.route_intersections),
        route_intersects_count=world.route_intersects_count,
        route_length_km=world.route_length_km, risk_override=world.risk_override,
        favorability_score=world.favorability_score,
        knowledge_chunks=list(world.knowledge_chunks),
        knowledge_mode=world.knowledge_mode, knowledge_note=world.knowledge_note,
        pfz_candidates=list(world.pfz_candidates),
        fishing_potential=world.fishing_potential,
        productivity=world.productivity,
        failing_tool=world.failing_tool, malicious_text=world.malicious_text)


# ------------------------------------------------------------------- stream
def _run_stream(identifier, message, world, expected, title, parts) -> Case:
    collector: List[Dict[str, Any]] = []

    async def sink(record: Dict[str, Any]) -> None:
        collector.append(record)

    result = asyncio.run(stream_orchestration(
        message,
        request_id=f"eval-{identifier}",
        tool_registry=ScenarioRegistry(world),
        context_repository=InMemoryContextRepository(),
        sink=sink))
    return Case(identifier, message, world, response=result, events=collector,
                expected=expected, title=title, parts=parts)


# ------------------------------------------------------------------- router
def _run_router(identifier, message, world, expected, title, parts) -> Case:
    import app.routers.orchestrate as router_module

    # If the guard fails, the orchestrator would be reached: make that visible.
    class _Exploding:
        async def run(self, *a, **k):
            raise AssertionError("oversized input must not reach the orchestrator")

    original = router_module.get_orchestrator_service
    router_module.get_orchestrator_service = lambda: _Exploding()
    try:
        response = asyncio.run(router_module.orchestrate(
            message=message, request_id=f"eval-{identifier}"))
    finally:
        router_module.get_orchestrator_service = original
    return Case(identifier, message, world, response=response, expected=expected,
                title=title, parts=parts)