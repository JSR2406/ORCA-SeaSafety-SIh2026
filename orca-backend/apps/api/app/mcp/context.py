# Safe logging bridge from MCP tools to the MCP request Context.
# The Context is optional: when a tool is invoked via the HTTP /mcp/invoke
# boundary no live MCP request context exists, and logging simply falls back
# to structlog.  When invoked by a real MCP client the context methods are used.
from typing import Any, Dict, Optional

import structlog

from mcp.server.mcpserver import Context

logger = structlog.get_logger(__name__)


LEVEL_MAP = {
    "debug": "debug",
    "info": "info",
    "notice": "warning",
    "warning": "warning",
    "error": "error",
    "critical": "error",
    "alert": "error",
    "emergency": "error",
}


class ContextLogger:
    """Log adapter that routes to the MCP Context when available."""

    def __init__(self, context: Optional[Context] = None, fields: Optional[Dict[str, Any]] = None):
        self._context = context
        self._fields = fields or {}

    def bind(self, context: Optional[Context] = None, **fields: Any) -> "ContextLogger":
        self._context = context
        self._fields.update(fields)
        return self

    async def log(self, level: str, event: str, **fields: Any) -> None:
        merged = dict(self._fields)
        merged.update(fields)
        method = getattr(logger, LEVEL_MAP.get(level, "info"), None)
        if method is not None:
            method(event, **merged)
        if self._context is not None:
            try:
                line = event
                if merged:
                    line = f"{event} {merged}"
                await self._context.log(level, line)
            except Exception:
                # Logging must never break a tool call.
                pass

    async def debug(self, event: str, **fields: Any) -> None:
        await self.log("debug", event, **fields)

    async def info(self, event: str, **fields: Any) -> None:
        await self.log("info", event, **fields)

    async def warning(self, event: str, **fields: Any) -> None:
        await self.log("warning", event, **fields)

    async def error(self, event: str, **fields: Any) -> None:
        await self.log("error", event, **fields)