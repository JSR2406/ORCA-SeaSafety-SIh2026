# Phase 10 - JSON schemas for the stable contract (Parts 29, 33).
#
# The JSON-Schema documents for the orchestrator request/response/error and
# streaming-event contracts are generated from the authoritative pydantic
# models so the schema can never drift from the code.  The frontend project
# consumes these as black-box type definitions - it never sees agent/MCP/DB
# internals.
from typing import Any, Dict

from app.contracts.errors import ErrorResponse
from app.contracts.event import StreamEvent
from app.contracts.orchestration import OrchestrationRequest
from app.contracts.response import OrchestrationResponse
from app.contracts.versions import contract_meta


def _base_schema(model, title: str, description: str) -> Dict[str, Any]:
    schema = model.model_json_schema()
    schema["title"] = title
    schema["description"] = description
    return schema


def orchestration_request_schema() -> Dict[str, Any]:
    return _base_schema(
        OrchestrationRequest,
        "OrchestrationRequest",
        "Structured body accepted by POST /api/v1/orchestrate "
        "(contract v%s)." % contract_meta()["api_version"],
    )


def orchestration_response_schema() -> Dict[str, Any]:
    return _base_schema(
        OrchestrationResponse,
        "OrchestrationResponse",
        "Canonical response returned by POST /api/v1/orchestrate "
        "(schema v%s)." % contract_meta()["response_schema_version"],
    )


def error_response_schema() -> Dict[str, Any]:
    return _base_schema(
        ErrorResponse,
        "ErrorResponse",
        "Structured error envelope used for all /api/v1/orchestrate "
        "failures and 429 rate-limit responses.",
    )


def stream_event_schema() -> Dict[str, Any]:
    return _base_schema(
        StreamEvent,
        "StreamEvent",
        "Sanitized execution event envelope streamed over the "
        "/api/v1/orchestrate/stream WebSocket "
        "(event schema v%s)." % contract_meta()["event_schema_version"],
    )


def all_schemas() -> Dict[str, Dict[str, Any]]:
    return {
        "orchestration_request": orchestration_request_schema(),
        "orchestration_response": orchestration_response_schema(),
        "error_response": error_response_schema(),
        "stream_event": stream_event_schema(),
    }