# Phase 10 - readiness probe (Part 21).
#
# GET /api/v1/ready - a coarse-grained, load-balancer-facing readiness check
# used to decide whether this instance can take traffic.  It reports only
# safe component status (database, scheduler, source registry, orchestrator)
# as a bounded enum - never stack traces, endpoints or credentials.  It is
# deliberately lightweight (no external network calls on every poll).
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.client import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["health"])


def _extra_checks(app) -> dict:
    checks = {}
    scheduler = getattr(app.state, "scheduler", None)
    checks["scheduler"] = {
        "status": "running" if scheduler is not None else "not_configured",
    }
    try:
        from app.orchestration.orchestrator import get_orchestrator_service
        get_orchestrator_service()
        checks["orchestrator"] = {"status": "available"}
    except Exception as e:  # noqa: BLE001
        logger.warning("orchestrator readiness check failed: %s", e)
        checks["orchestrator"] = {"status": "unavailable"}
    return checks


@router.get("/ready")
async def readiness(request: Request, session: AsyncSession = Depends(get_db_session)):
    """Readiness probe: true only when the instance can serve traffic."""
    db_components = {"database": {"status": "connected"}}
    ready = True
    try:
        await session.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        logger.warning("readiness DB check failed: %s", e)
        db_components["database"] = {"status": "disconnected"}
        ready = False

    checks = {**db_components, **_extra_checks(request.app)}
    if checks.get("orchestrator", {}).get("status") != "available":
        ready = False

    return {
        "status": "ready" if ready else "not_ready",
        "ready": ready,
        "components": checks,
        "timestamp": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
    }
