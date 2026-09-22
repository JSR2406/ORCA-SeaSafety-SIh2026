# Phase 9 - Part 2: source health monitoring.
#
# Distinguishes HTTP/configuration availability from data FRESHNESS.
# A source that is reachable but returning old data is STALE (its data is not
# trustworthy as current), not HEALTHY.  A source that is configured but has
# been failing is DEGRADED; one that has never succeeded or is not configured
# is UNAVAILABLE; one we have no signal for is UNKNOWN.
#
# This is deliberately separate from per-record DataStatus: it answers
# "can this source be relied on right now?" for the ops dashboard.
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class SourceHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


@dataclass
class SourceHealth:
    source: str
    status: SourceHealthStatus
    configured: bool
    connected: bool = False
    last_successful_fetch: Optional[datetime] = None
    age_seconds: Optional[float] = None
    threshold_seconds: Optional[int] = None
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    message: str = ""
    evaluated_at: Optional[datetime] = None


class SourceHealthMonitor:
    """Compute a source health verdict from config + fetch + freshness state."""

    def evaluate(
        self,
        *,
        source: str,
        configured: bool,
        last_successful_fetch: Optional[datetime],
        threshold_seconds: Optional[int] = None,
        consecutive_failures: int = 0,
        last_error: Optional[str] = None,
        latest_data_timestamp: Optional[datetime] = None,
        now: Optional[datetime] = None,
    ) -> SourceHealth:
        now = now or __import__("app.models.common", fromlist=["utcnow"]).utcnow()
        age = None
        if last_successful_fetch is not None:
            ts = last_successful_fetch
            if ts.tzinfo is None:
                from datetime import timezone
                ts = ts.replace(tzinfo=timezone.utc)
            age = max(0.0, (now - ts).total_seconds())

        if not configured:
            return SourceHealth(
                source=source, status=SourceHealthStatus.UNAVAILABLE,
                configured=False, connected=False,
                last_successful_fetch=last_successful_fetch, age_seconds=age,
                threshold_seconds=threshold_seconds,
                consecutive_failures=consecutive_failures,
                last_error=last_error,
                message="source not configured (no endpoint/credentials)",
                evaluated_at=now)

        # Never succeeded -> cannot be relied on.
        if last_successful_fetch is None:
            if consecutive_failures:
                return SourceHealth(
                    source=source, status=SourceHealthStatus.UNAVAILABLE,
                    configured=True, connected=False,
                    consecutive_failures=consecutive_failures,
                    last_error=last_error,
                    message="no successful fetch recorded",
                    evaluated_at=now)
            return SourceHealth(
                source=source, status=SourceHealthStatus.UNKNOWN,
                configured=True, connected=True,
                message="configured but never fetched yet",
                evaluated_at=now)

        # Data age crosses the freshness threshold -> STALE (honest: not current).
        if threshold_seconds is not None and age is not None and age > threshold_seconds:
            return SourceHealth(
                source=source, status=SourceHealthStatus.STALE,
                configured=True, connected=True,
                last_successful_fetch=last_successful_fetch, age_seconds=age,
                threshold_seconds=threshold_seconds,
                consecutive_failures=consecutive_failures, last_error=last_error,
                message=f"last successful fetch {age:.0f}s ago "
                        f"(threshold {threshold_seconds}s)",
                evaluated_at=now)

        # Reachable and fresh, but with a history of failures -> DEGRADED.
        if consecutive_failures > 0:
            return SourceHealth(
                source=source, status=SourceHealthStatus.DEGRADED,
                configured=True, connected=True,
                last_successful_fetch=last_successful_fetch, age_seconds=age,
                threshold_seconds=threshold_seconds,
                consecutive_failures=consecutive_failures, last_error=last_error,
                message=f"reachable but {consecutive_failures} consecutive failures",
                evaluated_at=now)

        return SourceHealth(
            source=source, status=SourceHealthStatus.HEALTHY,
            configured=True, connected=True,
            last_successful_fetch=last_successful_fetch, age_seconds=age,
            threshold_seconds=threshold_seconds, consecutive_failures=0,
            last_error=None,
            message="configured and healthy",
            evaluated_at=now)
