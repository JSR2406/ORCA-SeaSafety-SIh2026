# MCP-layer error handling.  Stable machine error codes for tool invocations.
# Tools never raise for "expected" outcomes (unconfigured source, missing data,
# stale data): those are reported as structured statuses in the result envelope.
# Exceptions are reserved for genuinely broken invocations / dependencies.
from typing import Optional


class MCPErrorCode:
    """Stable machine-readable error codes exposed by the capability layer."""
    INVALID_INPUT = "INVALID_INPUT"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_STALE = "SOURCE_STALE"
    DATA_NOT_FOUND = "DATA_NOT_FOUND"
    GEOMETRY_INVALID = "GEOMETRY_INVALID"
    TIME_OUT_OF_RANGE = "TIME_OUT_OF_RANGE"
    RATE_LIMITED = "RATE_LIMITED"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class MCPToolError(Exception):
    """Raised by the MCP boundary for genuinely failed tool invocations."""

    def __init__(self, code: str, message: str, *, details: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        out = {"code": self.code, "message": self.message}
        if self.details:
            out["details"] = self.details
        return out