# Error contract (Phase 10 - Parts 7, 40).
#
# Stable structured errors so the frontend can distinguish failure modes
# without parsing prose or relying on HTTP 500 for everything.
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel


class ErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    NEEDS_INPUT = "NEEDS_INPUT"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    DATA_STALE = "DATA_STALE"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    ORCHESTRATION_TIMEOUT = "ORCHESTRATION_TIMEOUT"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    NO_DATA = "NO_DATA"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorResponse(BaseModel):
    error: Dict[str, Any]

    @classmethod
    def build(cls, code: ErrorCode | str, message: str,
              retryable: bool = False, source: Optional[str] = None,
              run_id: Optional[str] = None,
              http_status: Optional[int] = None,
              **extra: Any) -> "ErrorResponse":
        body: Dict[str, Any] = {
            "code": (ErrorCode(code) if isinstance(code, str) else code).value,
            "message": message,
            "retryable": bool(retryable),
        }
        if source:
            body["source"] = source
        if run_id:
            body["run_id"] = run_id
        if http_status is not None:
            body["http_status"] = http_status
        body.update(extra)
        return ErrorResponse(error=body)
