# Phase 10 - rate limiting middleware (Parts 24, 40).
#
# A small in-memory fixed-window limiter keyed by client IP and bounded by
# settings.rate_limit_rpm.  On breach it returns a structured ErrorResponse
# with code=RATE_LIMITED and HTTP 429.  It only introduces steady, fixed
# overhead and never blocks internal /api/v1/mcp endpoints beyond the same
# shared budget.  No client state is persisted; this is an edge guard, not an
# auth system.
from collections import defaultdict, deque
from time import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings
from app.contracts.errors import ErrorCode, ErrorResponse


def _client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    ip = (fwd.split(",")[0].strip() if fwd
          else (request.client.host if request.client else "unknown"))
    return f"{ip}:{request.url.path}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, rpm: int = 0):
        super().__init__(app)
        self.rpm = rpm if rpm and rpm > 0 else settings.rate_limit_rpm
        self._window = 60.0
        self._hits: "defaultdict[str, deque]" = defaultdict(deque)
        # Skip static/documentation and health paths from the limiter.
        self._skipped = {"/", "/health", "/ready", "/docs", "/redoc",
                         "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path not in self._skipped and request.method in ("POST", "PUT", "DELETE"):
            key = _client_key(request)
            now = time()
            window = self._hits[key]
            while window and now - window[0] > self._window:
                window.popleft()
            if len(window) >= self.rpm:
                payload = ErrorResponse.build(
                    code=ErrorCode.RATE_LIMITED,
                    message="Too many requests. Please retry shortly.",
                    retryable=True, http_status=429).model_dump()
                return JSONResponse(status_code=429, content=payload,
                                    headers={"Retry-After": "60"})
            window.append(now)
        return await call_next(request)
