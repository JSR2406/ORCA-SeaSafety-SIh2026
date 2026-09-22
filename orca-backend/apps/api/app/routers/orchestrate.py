# Phase 4 router: autonomous agentic orchestration.
#
# POST /api/v1/orchestrate  - run the Intent -> Plan -> Execute -> Synthesize
# pipeline.  The response reports the retrieval/execution status honestly and
# verification results; it never hides partial failures.
#
# Phase 10 productionizes the boundary as a strict, versioned contract:
#   * Optional structured JSON body (OrchestrationRequest) while keeping the
#     legacy ?message / ?conversation_id / ?request_id query-parameter channel
#     fully backward compatible.
#   * Response is the canonical OrchestrationResponse (additive) with run_id,
#     typed risk.classification, confidence, structured needs_input / error.
#   * Frontend never sees agent/MCP/DB internals; it treats this router as a
#     black box behind the /api/v1 contract.
#
# Phase 6 adds GET-style WebSocket /api/v1/orchestrate/stream - the same run
# surfaced as a sequence of sanitized execution events (execution.started ->
# intent.detected -> plan.created -> task/tool/verification events ->
# response.ready).  Only safe execution metadata is streamed; never secrets or
# hidden reasoning.
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, Body, WebSocket, WebSocketDisconnect
from fastapi.params import Body as _BodyParam
from fastapi.responses import JSONResponse

from app.config import settings
from app.contracts.errors import ErrorCode, ErrorResponse
from app.contracts.orchestration import OrchestrationRequest, UserLocation
from app.contracts.normalize import normalize_response
from app.contracts.versions import contract_meta
from app.orchestration.orchestrator import (
    OrchestrationError, OrchestratorService,
    get_orchestrator_service)

router = APIRouter(prefix="/api/v1/orchestrate", tags=["orchestrate"])


def _orchestrator() -> OrchestratorService:
    return get_orchestrator_service()


def _validate_location(location: Optional[UserLocation]) -> Optional[str]:
    """Geometry bounds validation (Part 31): never let bogus coordinates
    through to the backend."""
    if location is None:
        return None
    # The model enforces latitude/longitude Field bounds; this is belt-and-
    # suspenders for any path that bypasses pydantic binding.
    if not (-90.0 <= location.latitude <= 90.0):
        return "latitude must be between -90 and 90"
    if not (-180.0 <= location.longitude <= 180.0):
        return "longitude must be between -180 and 180"
    return None


def _invalid_response(rid: Optional[str], reason: str,
                      status_code: int = 400) -> JSONResponse:
    payload = ErrorResponse.build(
        code=ErrorCode.INVALID_REQUEST, message=reason,
        retryable=False, http_status=status_code,
        request_id=rid or "").model_dump()
    return JSONResponse(status_code=status_code, content=payload)


async def _run(body_message: str, body_request_id: Optional[str],
               conversation_id: Optional[str],
               request_id: Optional[str],
               user_location: Optional[UserLocation] = None) -> Dict[str, Any]:
    """Shared execution path used by both the query-parameter and JSON-body
    channels.  Returns the canonical contract response merged additively with
    the legacy fields so v1 consumers keep working unchanged."""
    client_rid = body_request_id or request_id
    rid = client_rid or f"orch-{uuid4().hex[:12]}"

    if not body_message or not body_message.strip():
        return _reject(client_rid, conversation_id,
                       "A non-empty message is required.", run_id=rid)
    if len(body_message) > settings.orchestrator_max_message_chars:
        return _reject(
            client_rid, conversation_id,
            f"Message exceeds {settings.orchestrator_max_message_chars} "
            "character limit.", run_id=rid)

    try:
        response = await _orchestrator().run(
            body_message,
            conversation_id=conversation_id,
            request_id=rid,
            user_location=user_location,
        )
    except OrchestrationError as exc:
        error = ErrorResponse.build(
            code=ErrorCode.INTERNAL_ERROR, message=str(exc),
            retryable=True, run_id=rid, http_status=200).model_dump()
        return {
            "request_id": client_rid or rid,
            "run_id": rid,
            "conversation_id": conversation_id,
            "status": "failed",
            "message": str(exc),
            "answer": str(exc),
            "sections": [],
            "verification": None,
            "tool_calls": 0,
            "duration_ms": 0,
            "notes": {"error": "orchestration_error"},
            "error": error["error"],
            "schema_version": contract_meta()["response_schema_version"],
            "api_version": contract_meta()["api_version"],
        }

    canonical = normalize_response(response)
    payload = canonical.model_dump(mode="json")
    # Additive legacy fields: keep every v1 field the orchestrator produced so
    # existing consumers are unaffected.
    payload["message"] = response.get("message") or canonical.answer
    payload["conversation_id"] = response.get("conversation_id")
    payload["intent"] = response.get("intent")
    payload["sections"] = response.get("sections") or []
    payload["verification"] = response.get("verification")
    payload["tool_calls"] = response.get("tool_calls")
    payload["duration_ms"] = response.get("duration_ms")
    payload["phase_timings"] = response.get("phase_timings")
    payload["freshness"] = response.get("freshness")
    payload["evidence_graph"] = response.get("evidence_graph")
    payload["notes"] = response.get("notes")
    return payload


def _reject(rid: Optional[str], cid: Optional[str], reason: str,
            run_id: str = "") -> dict:
    return {
        "request_id": rid or run_id or "",
        "run_id": run_id or rid or "",
        "conversation_id": cid,
        "intent": None,
        "status": "invalid",
        "message": reason,
        "answer": reason,
        "sections": [],
        "verification": None,
        "tool_calls": 0,
        "duration_ms": 0,
        "notes": {"error": reason},
        "error": ErrorResponse.build(
            code=ErrorCode.INVALID_REQUEST, message=reason,
            retryable=False, run_id=run_id or rid or "",
            http_status=200).model_dump()["error"],
        "schema_version": contract_meta()["response_schema_version"],
        "api_version": contract_meta()["api_version"],
    }


@router.post("")
async def orchestrate(
    payload: Optional[OrchestrationRequest] = Body(default=None),
    message: str = "",
    conversation_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Any:
    """Structured orchestration entrypoint.

    Two mutually compatible channels:
      * NEW: JSON body of OrchestrationRequest (query, message, language, session_id,
        conversation_id, user_location, context, requested_outputs, route_request,
        scenario_request, request_id).
      * LEGACY: query parameters ?message=&conversation_id=&request_id=.

    If a JSON body is supplied it takes precedence; otherwise the query
    parameters are used.  The response is the canonical OrchestrationResponse
    with the legacy response fields appended for drop-in compatibility.
    """
    if payload is not None and not isinstance(payload, _BodyParam):
        loc_error = _validate_location(payload.user_location)
        if loc_error:
            return _invalid_response(payload.request_id, loc_error)
        resolved_query = payload.query or payload.message
        resolved_session = payload.session_id or payload.conversation_id
        return await _run(
            body_message=resolved_query,
            body_request_id=payload.request_id,
            conversation_id=resolved_session,
            request_id=request_id,
            user_location=payload.user_location,
        )
    return await _run(
        body_message=message,
        body_request_id=None,
        conversation_id=conversation_id,
        request_id=request_id,
        user_location=None,
    )


@router.websocket("/stream")
async def orchestrate_stream(
    websocket: WebSocket,
    message: str = "",
    conversation_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
    """Stream one executed run as sanitized events (Phase 6 #16).

    Protocol: client connects, then sends the request payload as the FIRST
    JSON text frame (same shape as POST /api/v1/orchestrate body). The server
    does NOT read query parameters for the message; it reads the first frame.
    """
    await websocket.accept()
    rid = request_id or f"orch-{uuid4().hex[:12]}"

    disconnected = False

    async def sink(event) -> None:
        nonlocal disconnected
        if disconnected:
            return
        try:
            await websocket.send_json(event)
        except Exception:  # noqa: BLE001 - client gone; stop streaming
            disconnected = True

    # Read first JSON frame from client (replaces ?message= query param)
    try:
        first_frame = await websocket.receive_text()
    except WebSocketDisconnect:
        return
    except Exception:
        await sink({
            "event": "execution.failed",
            "request_id": rid,
            "conversation_id": conversation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "data": {"reason": "receive_failed"},
        })
        try:
            await websocket.close()
        except Exception:
            pass
        return

    import json
    try:
        payload = json.loads(first_frame)
    except json.JSONDecodeError:
        await sink({
            "event": "execution.failed",
            "request_id": rid,
            "conversation_id": conversation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "data": {"reason": "invalid_json_frame"},
        })
        try:
            await websocket.close()
        except Exception:
            pass
        return

    # Extract fields (same as OrchestrationRequest canonical + legacy)
    ws_message = payload.get("query") or payload.get("message") or ""
    ws_conversation_id = payload.get("session_id") or payload.get("conversation_id") or conversation_id
    ws_request_id = payload.get("request_id") or request_id
    ws_user_location = payload.get("user_location")
    ws_language = payload.get("language")
    ws_requested_outputs = payload.get("requested_outputs")
    ws_route_request = payload.get("route_request")
    ws_scenario_request = payload.get("scenario_request")

    if not ws_message or not ws_message.strip():
        await sink({
            "event": "execution.failed",
            "request_id": rid,
            "conversation_id": ws_conversation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "data": {"reason": "empty_message"},
        })
        try:
            await websocket.close()
        except Exception:
            pass
        return

    if len(ws_message) > settings.websocket_max_message_chars:
        await sink({
            "event": "execution.failed",
            "request_id": rid,
            "conversation_id": ws_conversation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "data": {"reason": "message_too_long",
                     "limit": settings.websocket_max_message_chars},
        })
        try:
            await websocket.close()
        except Exception:
            pass
        return

    from app.orchestration.stream import stream_orchestration
    try:
        await stream_orchestration(
            ws_message,
            conversation_id=ws_conversation_id,
            request_id=ws_request_id,
            user_location=ws_user_location,
            sink=sink,
        )
    except WebSocketDisconnect:  # noqa: F841 - client closed; nothing to send
        pass
    except Exception:  # noqa: BLE001 - execution.failed already emitted by the
        pass  #               tracer; never leak internal error details.
    finally:
        try:
            if not disconnected:
                await websocket.close()
        except Exception:  # noqa: BLE001
            pass