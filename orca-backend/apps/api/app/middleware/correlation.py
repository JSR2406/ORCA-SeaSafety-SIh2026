# Phase 10 - correlation + structured request logging middleware (Part 26).
#
# Assigns a request_id for every HTTP request (honouring an inbound
# X-Request-ID when present) and propagates it into structlog context so that
# request_id -> run_id -> task_id -> tool_call_id can be correlated across a
# single user turn.  The access log is structured and deliberately excludes
# credentials, authorization headers, cookies and request bodies.
import time
import uuid
import structlog

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = structlog.get_logger("floatchat.access")


def _get_client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _sanitise_headers(request: Request) -> dict:
    """Never record credentials/tokens/authorization/cookies."""
    result = {}
    for name in ("authorization", "cookie", "x-api-key", "proxy-authorization"):
        if request.headers.get(name):
            result[name] = "<redacted>"
    return result


class CorrelationMiddleware(BaseHTTPMiddleware):
    ALLOWED_PATHS = {"/health", "/ready", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        request_id = request.headers.get("X-Request-ID") or \
            f"req-{uuid.uuid4().hex[:12]}"
        # Bind request_id into structlog contextvars for this request so every
        # log line in the same turn carries the correlation id.
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = None
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            path = request.url.path
            if response is not None and path not in self.ALLOWED_PATHS:
                logger.info(
                    "access",
                    method=request.method,
                    path=path,
                    status=response.status_code,
                    duration_ms=round(duration_ms, 2),
                    client_ip=_get_client_ip(request),
                )
            structlog.contextvars.unbind_contextvars("request_id")
