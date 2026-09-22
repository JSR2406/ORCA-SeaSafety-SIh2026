# ToolRegistry - the thin MCP boundary over the Phase 1 services.
# Every registered tool: (1) is bounded to a service method, never an external
# API directly; (2) has a typed Pydantic input model used to coerce/validate
# raw arguments; (3) returns the structured envelope (MarineDataResult or a
# plain dict); (4) carries a safety class and a stable namespaced name.
#
# A tool function is a plain typed async callable that MAY declare an optional
# trailing `ctx: Context | None = None` parameter (used when invoked by a real
# MCP client); the HTTP /mcp/invoke boundary always calls it without a context.
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type

import structlog
from pydantic import BaseModel, ValidationError

from mcp.server.mcpserver import Context

from app.mcp.context import ContextLogger
from app.mcp.errors import MCPErrorCode, MCPToolError
from app.mcp.schema import ToolDescriptor, marine_envelope
from app.models.common import DataStatus
from app.models.result import MarineDataResult

logger = structlog.get_logger(__name__)

READ_ONLY = "READ_ONLY"
SPATIAL_ANALYSIS = "SPATIAL_ANALYSIS"
DECISION_SUPPORT = "DECISION_SUPPORT"


@dataclass
class ToolDefinition:
    name: str
    fn: Callable[..., Any]
    title: str
    description: str
    group: str
    safety: str = READ_ONLY
    input_model: Optional[Type[BaseModel]] = None

    @property
    def input_schema(self) -> Optional[Dict[str, Any]]:
        if self.input_model is None:
            return None
        return self.input_model.model_json_schema()

    def mcp_callable(self) -> Callable[..., Any]:
        """Callable for the MCP SDK (same signature; hides nothing)."""
        return self.fn


class ToolRegistry:
    def __init__(self, evidence=None) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._log = ContextLogger()
        # Optional best-effort evidence persistence (injected at the app
        # assembly boundary only; tests and bare registries leave it None).
        self._evidence = evidence

    # ---------------------------------------------------------------- register
    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"duplicate MCP tool name: {definition.name}")
        self._tools[definition.name] = definition

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError:
            raise MCPToolError(MCPErrorCode.INVALID_INPUT, f"unknown tool: {name}")

    def list(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def names(self) -> List[str]:
        return list(self._tools.keys())

    def descriptors(self) -> List[ToolDescriptor]:
        return [
            ToolDescriptor(
                name=t.name,
                title=t.title,
                description=t.description,
                group=t.group,
                safety=t.safety,
                input_schema=t.input_schema,
            )
            for t in self._tools.values()
        ]

    # ---------------------------------------------------------------- invoke
    async def invoke(
        self,
        name: str,
        arguments: Dict[str, Any],
        context: Optional[Context] = None,
        *,
        request_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        tool = self.get(name)
        self._log.bind(
            context,
            request_id=request_id,
            conversation_id=conversation_id,
        )
        await self._log.info("mcp.invoke", tool=name)

        # 1. Coerce/validate raw arguments through the tool's input model.
        if tool.input_model is not None:
            try:
                parsed = tool.input_model.model_validate(arguments or {})
                args = parsed.model_dump()
            except ValidationError as exc:
                await self._log.warning("mcp.invalid_input", tool=name)
                raise MCPToolError(
                    MCPErrorCode.INVALID_INPUT,
                    f"invalid arguments for '{name}'",
                    details={"errors": exc.errors()},
                )
        else:
            args = dict(arguments or {})

        # 2. Run the boundary tool (service call, wrapped at the boundary).
        try:
            result = await tool.fn(**args)
        except MCPToolError:
            raise
        except ValueError as exc:
            await self._log.warning("mcp.invalid_argument", tool=name, error=str(exc))
            raise MCPToolError(MCPErrorCode.INVALID_INPUT, str(exc), details={"tool": name})
        except Exception as exc:  # noqa: BLE001 - the boundary must stay stable
            logger.exception("mcp.tool_failed", tool=name)
            await self._log.error("mcp.tool_failed", tool=name, error=str(exc))
            raise MCPToolError(
                MCPErrorCode.DEPENDENCY_FAILURE,
                f"tool '{name}' failed while querying data",
                details={"tool": name, "error": str(exc)},
            )

        # 3. Best-effort evidence persistence (never affects the response).
        if self._evidence is not None and request_id and isinstance(result, MarineDataResult):
            try:
                if (result.status in (DataStatus.LIVE, DataStatus.RECENT, DataStatus.STALE)
                        and result.data not in (None, [], {})):
                    await self._evidence.record(
                        query_run_id=request_id,
                        agent_name="mcp",
                        tool_name=name,
                        evidence_type="marine_data_result",
                        source=",".join(result.sources or []),
                        payload={
                            "status": result.status.value,
                            "conversation_id": conversation_id,
                        },
                    )
            except Exception:  # noqa: BLE001 - evidence must not break invoke
                logger.warning("mcp evidence write failed", tool=name)

        # 4. Normalize to the structured envelope.
        await self._log.info("mcp.invoke_ok", tool=name)
        if isinstance(result, MarineDataResult):
            return marine_envelope(result)
        return {"status": "live", "code": None, "data": result}