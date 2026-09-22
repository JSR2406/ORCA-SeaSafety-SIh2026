# Native MCP SDK server built from the ToolRegistry.
# Registers the exact same tool set as the HTTP /api/v1/mcp boundary so either
# transport can expose the identical capability layer to an agent.
import structlog
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from app.mcp.registry import READ_ONLY, ToolRegistry

logger = structlog.get_logger(__name__)

SERVER_NAME = "floatchat-marine"
SERVER_TITLE = "FloatChat Marine Intelligence"
SERVER_VERSION = "0.2.0"
SERVER_DESCRIPTION = (
    "Real-time marine data capability layer for FloatChat: ocean conditions, "
    "weather, tides, PFZ advisories, restricted areas and safety checks backed "
    "by the Phase 1 PostGIS data foundation. Structured outputs carry explicit "
    "status, freshness and provenance - never fabricated data."
)


def build_mcp_server(tool_registry: ToolRegistry) -> MCPServer:
    server = MCPServer(
        name=SERVER_NAME,
        title=SERVER_TITLE,
        description=SERVER_DESCRIPTION,
        version=SERVER_VERSION,
        debug=False,
    )
    for tool in tool_registry.list():
        read_only = tool.safety == READ_ONLY
        server.add_tool(
            tool.mcp_callable(),
            name=tool.name,
            title=tool.title,
            description=tool.description,
            annotations=ToolAnnotations(
                title=tool.title,
                read_only_hint=read_only,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False,
            ),
            meta={"group": tool.group, "safety": tool.safety},
        )
        logger.debug("mcp.tool_registered", name=tool.name, group=tool.group)
    return server