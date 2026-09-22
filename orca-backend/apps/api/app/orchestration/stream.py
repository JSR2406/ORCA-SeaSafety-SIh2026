# Phase 6 - WebSocket execution streaming.
#
# The same internal trace events the orchestrator, executor and tool bus emit
# are mapped onto a public, sanitized execution vocabulary and forwarded to the
# client (a WebSocket sink).  Only safe execution METADATA is streamed: event
# name, request/conversation/plan/task ids, a status, and a small whitelist of
# numeric/categorical fields.  Evidence payloads, tool arguments, error text
# and any hidden reasoning are never streamed.
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.orchestration.context import InMemoryContextRepository
from app.orchestration.orchestrator import OrchestratorService, get_registry

# Internal trace kind -> public event name (Phase 6 #15 vocabulary).
EVENT_NAMES: Dict[str, str] = {
    "needs_input": "execution.needs_input",
    "validation_failed": "execution.rejected",
    "execution_start": "execution.started",
    "intent_detected": "intent.detected",
    "plan_created": "plan.created",
    "task_start": "task.started",
    "task_completed": "task.completed",
    "task_failed": "task.failed",
    "tool_start": "tool.started",
    "tool_completed": "tool.completed",
    "tool_failed": "tool.failed",
    "verification_start": "verification.started",
    "verification_completed": "verification.completed",
    "verification_failed": "verification.failed",
    "response_ready": "response.ready",
    "execution_complete": "execution.completed",
    "execution_error": "execution.failed",
    "phase_metrics": "execution.timings",
}

_STATUS: Dict[str, str] = {
    "execution.needs_input": "needs_input",
    "execution.rejected": "rejected",
    "execution.started": "running",
    "execution.completed": "completed",
    "execution.failed": "failed",
    "intent.detected": "detected",
    "plan.created": "created",
    "task.started": "running",
    "task.completed": "succeeded",
    "task.failed": "failed",
    "tool.started": "running",
    "tool.completed": "completed",
    "tool.failed": "failed",
    "verification.started": "running",
    "verification.completed": "completed",
    "verification.failed": "failed",
    "response.ready": "success",
    "execution.timings": "measured",
}


def _safe_payload(kind: str, source: str,
                  payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Whitelist per kind: numbers/categoricals only, never evidence text."""
    payload = payload or {}
    if kind in ("task_start", "task_completed", "task_failed"):
        data: Dict[str, Any] = {"task": source}
        if kind == "task_start" and isinstance(payload.get("attempt"), int):
            data["attempt"] = payload["attempt"]
        return data
    if kind in ("tool_start", "tool_completed", "tool_failed"):
        return {"tool": source}
    if kind == "execution_start":
        return {"tasks": payload.get("tasks")} \
            if isinstance(payload.get("tasks"), int) else {}
    if kind == "intent_detected":
        return {k: payload.get(k) for k in ("intent", "language")
                if payload.get(k)}
    if kind == "plan_created":
        data = {}
        if isinstance(payload.get("tasks"), int):
            data["tasks"] = payload["tasks"]
        if payload.get("safety") is not None:
            data["safety"] = bool(payload["safety"])
        return data
    if kind == "verification_start":
        return {"task": source}
    if kind == "verification_completed":
        return {k: payload.get(k) for k in ("checked", "all_verified")
                if payload.get(k) is not None}
    if kind == "execution_complete":
        return {k: payload.get(k) for k in ("status", "task_count")
                if payload.get(k) is not None}
    if kind == "execution_error":
        return {}
    if kind == "phase_metrics":
        # Numeric timing fields only - already safe.
        return {k: v for k, v in payload.items()
                if isinstance(v, (int, float))}
    return {}


@dataclass
class StreamEvent:
    event: str
    request_id: str
    conversation_id: Optional[str] = None
    plan_id: Optional[str] = None
    task_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(
        timezone.utc).isoformat())
    status: str = "running"
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        from app.contracts.versions import contract_meta
        record: Dict[str, Any] = {"event": self.event,
                                  "request_id": self.request_id,
                                  "run_id": self.request_id,
                                  "timestamp": self.timestamp,
                                  "status": self.status,
                                  "data": self.data,
                                  "event_schema_version":
                                      contract_meta()["event_schema_version"]}
        if self.conversation_id:
            record["conversation_id"] = self.conversation_id
        if self.plan_id:
            record["plan_id"] = self.plan_id
        if self.task_id:
            record["task_id"] = self.task_id
        return record


class StreamTracer:
    """Forwards internal tracer events onto the public stream vocabulary.

    Used by the orchestrator/executor/tool-bus exactly like Tracer, but only
    accepts mapped kinds and only ever forwards the sanitized whitelist.
    """

    def __init__(self, request_id: str = "", conversation_id: Optional[str] = None,
                 sink: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
                 limit: int = 400):
        self.request_id = request_id
        self.conversation_id = conversation_id
        self.plan_id: Optional[str] = None
        self._sink = sink
        self.sent: List[Dict[str, Any]] = []
        self._limit = limit

    def set_plan_id(self, plan_id: Optional[str]) -> None:
        self.plan_id = plan_id

    async def event(self, kind: str, source: str = "",
                    payload: Optional[Dict[str, Any]] = None) -> None:
        public = EVENT_NAMES.get(kind)
        if public is None:
            return
        if len(self.sent) >= self._limit:
            return
        record = StreamEvent(
            event=public,
            request_id=self.request_id,
            conversation_id=self.conversation_id,
            plan_id=self.plan_id,
            task_id=source if kind in (
                "task_start", "task_completed", "task_failed",
                "verification_start", "verification_completed",
                "verification_failed") else None,
            status=_STATUS.get(public, "running"),
            data=_safe_payload(kind, source, payload),
        ).to_dict()
        self.sent.append(record)
        if self._sink is not None:
            await self._sink(record)

    async def fail(self) -> None:
        """Emit execution.failed (used when the run raises before completion)."""
        already = any(e["event"] == "execution.failed" for e in self.sent)
        if not already:
            await self.event("execution_error", source="orchestrator")


async def stream_orchestration(
    message: str,
    *,
    conversation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    user_location: Optional[Dict[str, Any]] = None,
    tool_registry=None,
    context_repository=None,
    sink: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
) -> Dict[str, Any]:
    """Run orchestration with a StreamTracer; every safe execution event is
    pushed through `sink` as it happens and the final response is returned."""
    rid = request_id or f"orch-{uuid.uuid4().hex[:12]}"
    tracer = StreamTracer(request_id=rid, conversation_id=conversation_id,
                          sink=sink)
    service = OrchestratorService(
        tool_registry=tool_registry if tool_registry is not None
        else get_registry(),
        context_repository=context_repository or InMemoryContextRepository(),
        tracer=tracer,
    )
    try:
        response = await service.run(
            message, conversation_id=conversation_id, request_id=rid,
            user_location=user_location)
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001 - surface as execution.failed, never leak
        await tracer.fail()
        raise
    return response