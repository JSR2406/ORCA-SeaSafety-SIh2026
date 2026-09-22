# HTTP transport for marine data feeds with bounded retry/backoff.
#
# Design constraints (per platform spec):
# - Never retry forever; honours a bounded attempt limit and capped exponential backoff.
# - Timeouts are enforced per request and are configurable.
# - Retryable failures (timeout, transport, HTTP 5xx, HTTP 429) are logged and retried.
# - Permanent failures (HTTP 404/410, rejected 4xx, non-JSON payload) fail fast, explicitly.
# - Failures surface as typed SourceError exceptions - never a mock/offline fallback.
import asyncio
import structlog

import httpx

from app.datasources.errors import (
    SourceInvalidDataError,
    SourceRateLimitError,
    SourceUnavailableError,
)

logger = structlog.get_logger(__name__)

_RETRY_MAX_BACKOFF = 30.0


class HttpDataTransport:
    """Synchronous-friendly async fetch with bounded retry/backoff."""

    def __init__(self, settings, client: httpx.AsyncClient | None = None):
        self.timeout_seconds = settings.data_timeout_seconds
        self.retry_limit = max(1, settings.data_retry_limit)
        self.backoff_seconds = settings.data_retry_backoff_seconds
        self._client = client

    async def get_json(self, url: str, params=None, headers=None) -> dict:
        last_exc: SourceError | None = None
        backoff = self.backoff_seconds
        for attempt in range(1, self.retry_limit + 1):
            try:
                return await self._get_json_once(url, params=params, headers=headers)
            except SourceRateLimitError as exc:
                last_exc = exc
                if attempt < self.retry_limit:
                    logger.warning("marine_fetch_rate_limited", url=url,
                                   attempt=attempt, retry_after=exc.retry_after)
                    await asyncio.sleep(exc.retry_after)
            except SourceUnavailableError as exc:
                last_exc = exc
                if exc.transient and attempt < self.retry_limit:
                    logger.warning("marine_fetch_retryable", url=url,
                                   attempt=attempt, backoff=round(backoff, 2),
                                   error=str(exc))
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 1.5, _RETRY_MAX_BACKOFF)
                else:
                    logger.warning("marine_fetch_failed_permanent", url=url,
                                   error=str(exc))
                    break
            except SourceInvalidDataError:
                raise
        if last_exc is None:
            raise SourceUnavailableError("marine fetch failed (no attempts made)")
        raise last_exc

    async def _get_json_once(self, url: str, params=None, headers=None) -> dict:
        client = self._client
        try:
            if client is None:
                async with httpx.AsyncClient(timeout=self.timeout_seconds,
                                             follow_redirects=True) as c:
                    resp = await c.get(url, params=params, headers=headers)
            else:
                resp = await client.get(url, params=params, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPError) as exc:
            raise SourceUnavailableError(
                f"transport failure for {url}: {exc.__class__.__name__}",
                transient=True,
            ) from exc

        if resp.status_code == 429:
            retry_after = _parse_retry_after(resp, self.backoff_seconds)
            raise SourceRateLimitError(
                f"rate limited (HTTP 429) for {url}", retry_after=retry_after,
            )
        if resp.status_code >= 500:
            raise SourceUnavailableError(
                f"upstream server error (HTTP {resp.status_code}) for {url}",
                transient=True,
            )
        if resp.status_code >= 400:
            raise SourceUnavailableError(
                f"upstream rejected request (HTTP {resp.status_code}) for {url}",
                transient=False,
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise SourceInvalidDataError(f"non-JSON response from {url}") from exc


def _parse_retry_after(resp: httpx.Response, fallback: float) -> float:
    header = resp.headers.get("Retry-After")
    if header is None:
        return fallback
    try:
        return min(max(float(header), 0.5), _RETRY_MAX_BACKOFF)
    except (TypeError, ValueError):
        return fallback