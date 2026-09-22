# Schema for the MCP capability layer: tool invocation contracts and the
# uniform structured envelope returned by every tool.
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.common import DataStatus
from app.models.result import MarineDataResult
from app.mcp.errors import MCPErrorCode

# Mapping from the data-layer status to a stable machine error code.  Expected
# outcomes (no data, not configured, stale) become codes in the envelope so an
# agent can react without an exception.
STATUS_TO_CODE = {
    DataStatus.LIVE: None,
    DataStatus.RECENT: None,
    DataStatus.TEST_MOCK: None,  # data present but explicitly sample/TEST-MOCK
    DataStatus.STALE: MCPErrorCode.SOURCE_STALE,
    DataStatus.UNAVAILABLE: MCPErrorCode.DATA_NOT_FOUND,
    DataStatus.NOT_CONFIGURED: MCPErrorCode.SOURCE_UNAVAILABLE,
    DataStatus.ERROR: MCPErrorCode.DEPENDENCY_FAILURE,
}


def marine_envelope(result: MarineDataResult) -> Dict[str, Any]:
    """Render a MarineDataResult as the uniform tool output envelope.

    The envelope always carries `status` and `code` so an agent can branch on
    data outcomes; `data` is only populated when data exists.
    """
    code = STATUS_TO_CODE.get(result.status)
    return {
        "status": result.status.value,
        "code": code,
        "data": result.data if result.data is not None else None,
        "sources": result.sources,
        "timestamps": result.timestamps.model_dump(mode="json")
        if result.timestamps is not None else None,
        "freshness": result.freshness.model_dump(mode="json")
        if result.freshness is not None else None,
        "provenance": [p.model_dump(mode="json") for p in result.provenance],
        "warnings": result.warnings,
        "confidence": result.confidence,
        "error": result.error,
    }


class ToolInput(BaseModel):
    """A single coercion step in the stored-input-parameters pipeline.

    Each tool defines its own parameter names; `ToolInput` carries the values
    exactly as the tool's Pydantic input model declares them under ToolConfig.
    """
    pass


class ToolCallRequest(BaseModel):
    """HTTP boundary request: invoke one registered tool by name."""
    tool: str = Field(..., description="Stable tool name, e.g. marine.ocean_conditions")
    arguments: Dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = Field(
        None, description="Observability id for this invocation (traced through logs)."
    )
    conversation_id: Optional[str] = Field(
        None, description="Observability id for the surrounding conversation/session."
    )


class ToolCallResponse(BaseModel):
    """HTTP boundary response envelope."""
    ok: bool
    tool: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    conversation_id: Optional[str] = None


class ToolDescriptor(BaseModel):
    """Static description of a registered tool (used by the HTTP API + docs)."""
    name: str
    title: str
    description: str
    group: str
    safety: str
    input_schema: Optional[Dict[str, Any]] = None