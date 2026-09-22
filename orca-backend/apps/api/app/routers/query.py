# Query shim router (frontend legacy compatibility).
#
# POST /api/v1/query/plan     - wraps the orchestrator's intent detection into a
#                               plan-shaped response without executing tools.
# POST /api/v1/query/execute  - runs the orchestrator end-to-end for a message
#                               (or a structured plan produced by /plan).
#
# These are compatibility surfaces for the old chat/planner UX; the canonical
# flow the frontend should use is POST /api/v1/orchestrate.
import logging
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.contracts.errors import ErrorCode, ErrorResponse
from app.contracts.versions import contract_meta
from app.orchestration.orchestrator import OrchestratorService, get_orchestrator_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/query", tags=["query"])


class PlanRequest(BaseModel):
    message: str = Field(min_length=1)
    language: Optional[str] = None


class ExecuteRequest(BaseModel):
    query: Any
    message: Optional[str] = None
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    user_location: Optional[Any] = None
    request_id: Optional[str] = None


def _orchestrator() -> OrchestratorService:
    return get_orchestrator_service()


@router.post("/plan")
async def plan_query(body: PlanRequest):
    """Honest intent/plan detection without execution.

    Never fabricates a plan: when the intent is not resolvable (e.g. no
    location), the response reports needs_input with the missing parameter."""
    try:
        intent = await _orchestrator()._parse(
            body.message,
            context=None,
            user_location=_user_location(body),
        )
    except Exception as exc:  # noqa: BLE001 - surface a controlled envelope
        return ErrorResponse.build(
            code=ErrorCode.INTERNAL_ERROR, message=str(exc),
            retryable=True, http_status=200).model_dump()

    plan = {
        "status": "needs_clarification" if intent.needs else "ready",
        "intent": intent.name.value,
        "language": intent.language,
        "message": body.message,
        "structured_query": {
            "intent": intent.name.value,
            "location": intent.location,
            "time": intent.time,
            "route": intent.route if intent.name.value == "route" else None,
            "needs": intent.needs,
        },
        "clarification_question": None,
        "needs": intent.needs,
        "api_version": contract_meta()["api_version"],
    }
    if intent.needs:
        # Deterministic clarification prompt (never fabricates options).
        from app.services.localization import t
        plan["clarification_question"] = t(intent.language, "line.which_location") \
            if "location" in intent.needs else None
    return plan


@router.post("/execute")
async def execute_query(body: ExecuteRequest):
    """Run the orchestrator for a message (canonical path for this shim).

    Accepts either a structured plan dict or a message; the orchestrator is the
    sole executor - the shim never executes tools on its own."""
    message = body.message or (
        body.query.get("message") if isinstance(body.query, dict) else None)
    if not message or not str(message).strip():
        return ErrorResponse.build(
            code=ErrorCode.INVALID_REQUEST, message="message is required",
            retryable=False, http_status=400).model_dump()

    session_id = body.session_id or body.conversation_id
    rid = body.request_id or f"qry-{uuid4().hex[:12]}"
    try:
        response = await _orchestrator().run(
            message, conversation_id=session_id, request_id=rid,
            user_location=_user_location(body))
    except Exception as exc:  # noqa: BLE001 - controlled failure envelope
        return ErrorResponse.build(
            code=ErrorCode.INTERNAL_ERROR, message=str(exc),
            retryable=True, run_id=rid, http_status=200).model_dump()
    return response


def _user_location(body) -> Optional[Dict[str, Any]]:
    loc = getattr(body, "user_location", None)
    if not loc:
        return None
    if isinstance(loc, dict):
        return {k: v for k, v in loc.items() if k in
                ("latitude", "longitude", "accuracy_m", "source", "timestamp")}
    return None