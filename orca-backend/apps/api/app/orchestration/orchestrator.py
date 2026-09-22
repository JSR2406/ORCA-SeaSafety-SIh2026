# Orchestrator service (Phase 4) - the composition root for agentic runs.
#
# Flow: intent parse -> (optional context) -> plan -> validate -> execute ->
# synthesize.  The whole run is bounded by config-driven limits and every
# number in the reply is verifier-traced.  DB/network-free when a fake tool
# registry and an in-memory context repository are injected (tests), and the
# real registry from build_mcp_component() when used by the HTTP router.
import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.config import settings

from app.orchestration.agents import ToolBus
from app.orchestration.context import (
    InMemoryContextRepository, PgContextRepository)
from app.orchestration.executor import Executor
from app.orchestration.intent import IntentParser, IntentValidator
from app.orchestration.models import Intent, IntentName, ValidationResult
from app.orchestration.planner import Planner
from app.orchestration.synthesis import synthesize
from app.orchestration.validator import PlanValidator
from app.services.evidence_service import get_marine_evidence_service


class OrchestrationError(RuntimeError):
    pass


class OrchestratorService:
    def __init__(self, tool_registry=None, context_repository=None,
                 request_timeout_seconds: float = 60.0,
                 max_tool_calls: int = 30,
                 planner_llm_enabled: bool = False,
                 tracer=None):
        self.tool_registry = tool_registry
        self.context = context_repository or InMemoryContextRepository()
        self.parser = IntentParser()
        self.intent_validator = IntentValidator()
        self.planner = Planner(llm_enabled=planner_llm_enabled)
        self.request_timeout_seconds = request_timeout_seconds
        self.max_tool_calls = max_tool_calls
        self.tracer = tracer

    def _tool_bus(self, request_id: str, conversation_id: Optional[str]) -> ToolBus:
        return ToolBus(
            registry=self.tool_registry,
            request_id=request_id,
            conversation_id=conversation_id,
            max_tool_calls=self.max_tool_calls,
            tracer=self.tracer,
        )

    async def run(self, message: str, *, conversation_id: Optional[str] = None,
                  request_id: Optional[str] = None,
                  user_location: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.tool_registry is None:
            self.tool_registry = get_registry()
            if not self._registry_usable(self.tool_registry):
                raise OrchestrationError(
                    "no tool registry is available to run orchestration")

        rid = request_id or f"orch-{uuid.uuid4().hex[:12]}"
        phase_timings: Dict[str, int] = {}
        t0 = time.monotonic()
        if self.tracer:
            await self.tracer.event("execution_start", source="orchestrator")
        context = await self.context.get_context(conversation_id) \
            if conversation_id else None

        intent = await self._parse(message, context, user_location)
        parse_ms = int((time.monotonic() - t0) * 1000)
        if self.tracer:
            await self.tracer.event(
                "intent_detected", source=intent.name.value,
                payload={"intent": intent.name.value,
                         "language": intent.language})

        if not self.intent_validator.is_resolvable(intent):
            if self.tracer:
                await self.tracer.event(
                    "needs_input", source=intent.name.value)
            from app.services.localization import t
            message = t(intent.language, "line.which_location")
            response: Dict[str, Any] = {
                "request_id": rid,
                "conversation_id": conversation_id,
                "intent": intent.name.value,
                "language": intent.language,
                "status": "needs_input",
                "message": message,
                "answer": message,
                "sections": [],
                "verification": None,
                "tool_calls": 0,
                "duration_ms": 0,
                "phase_timings": {"intent_ms": 0, "plan_ms": 0, "execute_ms": 0,
                                  "synthesize_ms": 0},
                "confidence": {"score": 1.0, "label": "high",
                               "basis": ["awaiting user clarification"]},
                "risk": {"level": "unknown", "hard_constraint": False,
                         "assessed": False},
                "outputs": {"maps": {"type": "FeatureCollection",
                                     "features": [], "generated_at": None},
                            "charts": [], "alerts": [], "route": None},
                "evidence": [],
                "provenance": {}, "limitations": [],
                "notes": {"merged_from_context": False},
            }
            await self.context.save_turn(conversation_id, {
                "request_id": rid, "intent": intent.name.value,
                "message": message, "needed": intent.needs})
            response = dict(response)
            response["notes"]["phase_timings"] = {
                "intent_ms": parse_ms, "plan_ms": 0, "execute_ms": 0,
                "synthesize_ms": 0}
            return response

        t1 = time.monotonic()
        plan = self.planner.plan(intent)
        bus = self._tool_bus(rid, conversation_id)
        if self.tracer:
            plan_id = f"{rid}-plan"
            if hasattr(self.tracer, "set_plan_id"):
                self.tracer.set_plan_id(plan_id)
            await self.tracer.event(
                "plan_created", source="orchestrator",
                payload={"tasks": len(plan.tasks), "safety": plan.safety})
        validation = PlanValidator(tool_bus=bus).validate(plan)
        plan_ms = int((time.monotonic() - t1) * 1000)
        if not validation.ok:
            if self.tracer:
                await self.tracer.event(
                    "validation_failed", source="orchestrator",
                    payload={"errors": validation.errors})
            response = synthesize_for_validation_failure(
                intent, validation, rid, conversation_id)
            response["notes"]["phase_timings"] = {
                "intent_ms": parse_ms, "plan_ms": plan_ms,
                "execute_ms": 0, "synthesize_ms": 0}
            response["phase_timings"] = response["notes"]["phase_timings"]
            await self.context.save_turn(conversation_id, {
                "request_id": rid, "intent": intent.name.value,
                "message": message, "validation_errors": validation.errors})
            return response

        executor = Executor(
            tool_bus=bus,
            tracer=self.tracer,
            max_parallel=settings.orchestrator_parallel,
            max_retries_per_task=settings.orchestrator_max_retries,
            max_total_retries=settings.orchestrator_max_total_retries,
            max_tasks=settings.orchestrator_max_tasks,
            task_timeout_seconds=settings.orchestrator_task_timeout_seconds,
        )
        try:
            execution = await asyncio.wait_for(
                executor.run(plan), timeout=self.request_timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise OrchestrationError(
                f"orchestration exceeded {self.request_timeout_seconds}s") \
                from exc
        if self.tracer:
            await self.tracer.event(
                "execution_complete", source="orchestrator",
                payload={"status": execution.status,
                         "task_count": len(plan.tasks)})
        execute_ms = int((time.monotonic() - t1) * 1000)

        t2 = time.monotonic()
        response = synthesize(intent, execution, rid, conversation_id)
        synthesize_ms = int((time.monotonic() - t2) * 1000)
        phase_timings = {
            "intent_ms": parse_ms,
            "plan_ms": plan_ms,
            "execute_ms": execute_ms,
            "synthesize_ms": synthesize_ms,
        }
        response["notes"]["phase_timings"] = phase_timings
        response["phase_timings"] = phase_timings
        if self.tracer:
            await self.tracer.event(
                "phase_metrics", source="orchestrator",
                payload=phase_timings)
            await self.tracer.event(
                "response_ready", source="orchestrator",
                payload={"status": response["status"]})
        await self._record_turn(conversation_id, intent, message, response)
        await self._persist_run_evidence(rid, conversation_id, response)
        return response

    # ------------------------------------------------------------ internal
    async def _parse(self, message: str,
                     context, user_location: Optional[Dict[str, Any]] = None) -> Intent:
        return self.parser.parse(message, context, user_location)

    async def _record_turn(self, conversation_id: Optional[str], intent: Intent,
                           message: str, response: Dict[str, Any]) -> None:
        if not conversation_id:
            return
        try:
            await self.context.save_turn(conversation_id, {
                "request_id": response["request_id"],
                "intent": intent.name.value,
                "message": message,
                "language": intent.language,
            })
            if intent.location:
                await self.context.update_location(
                    conversation_id, intent.location)
            await self.context.update_language(
                conversation_id, intent.language)
            await self.context.update_time(
                conversation_id, {
                    "label": intent.time,
                    "at": datetime.now(timezone.utc).isoformat(),
                })
            await self.context.update_intent(
                conversation_id, intent.name.value)
        except Exception:  # noqa: BLE001 - context writes never fail a turn
            pass

    async def _persist_run_evidence(
            self, request_id: str, conversation_id: Optional[str],
            response: Dict[str, Any]) -> None:
        try:
            service = get_marine_evidence_service()
            await service.record(
                query_run_id=request_id,
                agent_name="orchestrator",
                tool_name="orchestrate",
                evidence_type="orchestration_run",
                source=",".join(
                    (response.get("provenance") or {}).get("sources") or []),
                payload={
                    "status": response.get("status"),
                    "intent": response.get("intent"),
                    "language": response.get("language"),
                    "conversation_id": conversation_id,
                    "verification": response.get("verification"),
                    "evidence": response.get("evidence"),
                    "evidence_graph": response.get("evidence_graph"),
                    "provenance": response.get("provenance"),
                    "limitations": response.get("limitations"),
                })
        except Exception:  # noqa: BLE001 - observability never fails a turn
            pass

    @staticmethod
    def _registry_usable(registry) -> bool:
        try:
            return callable(getattr(registry, "invoke", None))
        except Exception:  # noqa: BLE001
            return False


def synthesize_for_validation_failure(
        intent: Intent, validation: ValidationResult,
        request_id: str, conversation_id: Optional[str]) -> Dict[str, Any]:
    message = ("The requested capability is not currently configured. "
               "Validation errors: " + "; ".join(validation.errors))
    return {
        "request_id": request_id,
        "conversation_id": conversation_id,
        "intent": intent.name.value,
        "language": intent.language,
        "status": "unavailable",
        "message": message,
        "answer": message,
        "sections": [],
        "verification": None,
        "tool_calls": 0,
        "duration_ms": 0,
        "phase_timings": {"intent_ms": 0, "plan_ms": 0, "execute_ms": 0,
                          "synthesize_ms": 0},
        "confidence": {"score": 0.5, "label": "medium",
                       "basis": ["capability validation failed"]},
        "risk": {"level": "unknown", "hard_constraint": False,
                 "assessed": False},
        "outputs": {"maps": {"type": "FeatureCollection", "features": [],
                             "generated_at": None},
                    "charts": [], "alerts": [], "route": None},
        "evidence": [],
        "provenance": {}, "limitations": [],
        "notes": {"validation_failed": True},
    }


def get_registry():
    """Real composition-root registry; available DB/network free at import."""
    from app.mcp.register import build_mcp_component
    try:
        component = build_mcp_component()
    except Exception:  # noqa: BLE001 - offline environments return None
        return None
    return component["tool_registry"]


def get_orchestrator_service(context_repository=None, tracer=None) -> OrchestratorService:
    if context_repository is None:
        context_repository = InMemoryContextRepository()
        # Production binding: swap in PgContextRepository when the application
        # supplies a live session factory.
    return OrchestratorService(
        tool_registry=None,
        context_repository=context_repository,
        request_timeout_seconds=settings.orchestrator_timeout_seconds,
        max_tool_calls=settings.orchestrator_max_tool_calls,
        planner_llm_enabled=settings.orchestrator_planner_llm_enabled,
        tracer=tracer,
    )