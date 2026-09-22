# HTTP boundary for the MCP capability layer.
# GET  /api/v1/mcp/tools   -> tool descriptor catalog (names, schemas, safety)
# POST /api/v1/mcp/invoke  -> invoke one tool with structured arguments
# GET  /api/v1/mcp/status  -> server + group overview
import structlog
from fastapi import APIRouter, HTTPException

from app.mcp.errors import MCPToolError
from app.mcp.registry import ToolRegistry
from app.mcp.register import build_mcp_component
from app.mcp.schema import ToolCallRequest, ToolCallResponse, ToolDescriptor
from app.mcp.server import SERVER_NAME, SERVER_TITLE, SERVER_VERSION

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])

# Single component for the process (registry is stateless between calls beyond
# the connection-less adapters; DB sessions are opened per invocation).
_component = build_mcp_component()


def _registry() -> ToolRegistry:
    return _component["tool_registry"]


@router.get("/tools", response_model=dict)
async def list_tools() -> dict:
    tools = _registry().descriptors()
    return {
        "server": {"name": SERVER_NAME, "title": SERVER_TITLE, "version": SERVER_VERSION},
        "count": len(tools),
        "tools": [t.model_dump() for t in tools],
    }


@router.post("/invoke", response_model=ToolCallResponse)
async def invoke_tool(request: ToolCallRequest) -> ToolCallResponse:
    try:
        result = await _registry().invoke(
            request.tool,
            request.arguments,
            request_id=request.request_id,
            conversation_id=request.conversation_id,
        )
    except MCPToolError as exc:
        logger.warning(
            "mcp.http_invoke_failed",
            tool=request.tool,
            code=exc.code,
            request_id=request.request_id,
            conversation_id=request.conversation_id,
        )
        raise HTTPException(status_code=400, detail=exc.to_dict())
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "mcp.http_invoke_unexpected",
            tool=request.tool,
            request_id=request.request_id,
        )
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(exc)})
    return ToolCallResponse(
        ok=True,
        tool=request.tool,
        result=result,
        request_id=request.request_id,
        conversation_id=request.conversation_id,
    )


@router.get("/status", response_model=dict)
async def mcp_status() -> dict:
    registry = _registry()
    groups = {}
    for tool in registry.list():
        groups.setdefault(tool.group, []).append(tool.name)
    return {
        "server": {"name": SERVER_NAME, "title": SERVER_TITLE, "version": SERVER_VERSION},
        "tool_count": len(registry.list()),
        "groups": groups,
    }