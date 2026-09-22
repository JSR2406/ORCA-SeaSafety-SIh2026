# FloatChat API Main Application

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db.client import init_db, close_db, get_session
from app.logging_config import setup_logging
from app.contracts.errors import ErrorCode, ErrorResponse
from app.contracts.versions import contract_meta
from app.middleware.correlation import CorrelationMiddleware
from app.middleware.ratelimit import RateLimitMiddleware
from app.routers import chat, profiles, voice, health, anomalies, scenarios, risk, exports, datasets, query_runs, marine, mcp, orchestrate, readiness, alerts, ml, knowledge, route, auth, query as query_router
from app.datasources.registry import build_registry
from app.ingestion import IngestionPipeline, SourcePollingScheduler
from app.ingestion.proactive_scheduler import ProactiveScheduler, reset_scheduler_singleton
from app.agents.proactive_agent import reset_proactive_singletons, get_proactive_engine
from app.routers import alerts as alerts_router_module
from app.ml.governance import reset_governance_singletons, get_governance_engine

# Phase 10: structured logging (JSON binary-configurable via log_format).
setup_logging(settings.log_format, settings.log_level)
logger = logging.getLogger(__name__)

# Coastal anchor points the scheduler ingests on.  Storm Glass free tier is
# capped at 10 requests/day, so the tide anchors fit inside that budget on a
# daily cadence.  The read side snaps arbitrary lat/lon to the nearest stored
# point within a radius, so these ports cover the west/east coast traffic.
_TIDE_ANCHOR_POINTS = [
    {"lat": 22.94, "lon": 70.25},   # Kandla
    {"lat": 18.94, "lon": 72.83},   # Mumbai
    {"lat": 15.39, "lon": 73.82},   # Goa / Mormugao
    {"lat": 12.92, "lon": 74.86},   # Mangalore
    {"lat": 9.93, "lon": 76.27},    # Kochi
    {"lat": 8.75, "lon": 78.18},    # Tuticorin
    {"lat": 13.08, "lon": 80.29},   # Chennai
    {"lat": 17.69, "lon": 83.30},   # Visakhapatnam
    {"lat": 20.29, "lon": 86.68},   # Paradip
]
_CONTROL_POINT = {"lat": 9.93, "lon": 76.27}  # Kochi
# Satellite-focused station.  Nearshore MUR SST is land/cloud masked at the
# control point; this offshore Kochi station (9.9 N, 76.0 E) returns valid SST.
_COAST_STATION_POINT = {"lat": 9.9, "lon": 76.0}

_TIDE_PARAMS = [
    {**p, "days": 7} for p in _TIDE_ANCHOR_POINTS
]


def _default_marine_fetch_params() -> dict:
    """Scheduler fetch parameters for the live source stack.

    Coordinate-required products get seeded points; stormglass polls the tide
    anchors daily (one request per port fits the 10/day free tier),
    openmeteo/coastwatch/openweather poll the control point at their intervals,
    and jtwc/gdacs have global feeds with no coordinates.
    """
    return {
        "stormglass": {"tides": {"points": _TIDE_PARAMS}},
        "openmeteo": {
            "ocean": {"points": [_CONTROL_POINT]},
            "weather_observation": {"points": [_CONTROL_POINT]},
            "weather_forecast": {"points": [_CONTROL_POINT]},
        },
        "coastwatch": {
            "ocean": {"points": [_COAST_STATION_POINT]},
            "pfz": {"points": [_COAST_STATION_POINT]},
        },
        "openweather": {
            "ocean": {"points": [_CONTROL_POINT]},
            "weather_observation": {"points": [_CONTROL_POINT]},
            "weather_forecast": {"points": [_CONTROL_POINT]},
        },
        "jtwc": {"warnings": {}},
        "gdacs": {"warnings": {}},
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting FloatChat API...")
    scheduler: SourcePollingScheduler | None = None
    proactive: ProactiveScheduler | None = None
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    if settings.scheduler_enabled:
        registry = build_registry(settings)
        pipeline = IngestionPipeline(settings, registry, get_session)
        scheduler = SourcePollingScheduler(
            settings, registry, pipeline,
            fetch_params=_default_marine_fetch_params(),
        )
        app.state.scheduler = scheduler
        app.state.scheduler_task = asyncio.create_task(scheduler.run())
        logger.info("Marine data scheduler started")

    # Phase 11 - bounded proactive alert scheduler (event detection, alert
    # evaluation, alert expiry).  It is disabled when proactively disabled.
    if settings.proactive_enabled:
        reset_proactive_singletons()
        engine = get_proactive_engine()
        proactive = ProactiveScheduler(engine)
        app.state.proactive_scheduler = proactive
        app.state.proactive_scheduler_task = asyncio.create_task(proactive.run())
        alerts_router_module.bind_alert_state(type("_AlertState", (), {
            "engine": engine,
            "alert_repository": engine.persistence,
        }))
        logger.info("Proactive alert scheduler started")

    # Phase 13 - ML governance / provenance loop.  Bounded, restart-safe,
    # never auto-deploys: it only records predictions/outcomes, runs matching,
    # evaluation and retraining *candidates*.  Promotion stays a controlled
    # backend operation (approval-gated), never agent-triggered.
    if settings.ml_governance_enabled:
        reset_governance_singletons()
        _gov = get_governance_engine()
        app.state.governance_engine = _gov
        logger.info("ML governance loop started")

    yield

    # Shutdown
    logger.info("Shutting down FloatChat API...")
    if scheduler is not None:
        await scheduler.shutdown()
        task = getattr(app.state, "scheduler_task", None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    if proactive is not None:
        await proactive.shutdown()
        task = getattr(app.state, "proactive_scheduler_task", None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    await close_db()


app = FastAPI(
    title="FloatChat API",
    description="Voice-first, multilingual, explainable AI interface for ARGO ocean data",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.log_level == "DEBUG" else None,
    redoc_url="/redoc" if settings.log_level == "DEBUG" else None,
)

# CORS - explicit origins only.  Credentials are enabled, so a wildcard
# allow_origins is NEVER used (would defeat the Same-Origin policy).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 10 edge guards + correlation.  Added last so they are outermost and
# wrap every route (including rate-limited responses).
app.add_middleware(RateLimitMiddleware, rpm=settings.rate_limit_rpm)
app.add_middleware(CorrelationMiddleware)


@app.middleware("http")
async def security_headers(request, call_next):
    """Baseline response hardening (clickjacking, sniffing, referrer leaks)."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Include routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(readiness.router)
app.include_router(chat.router)
app.include_router(profiles.router)
app.include_router(voice.router)
app.include_router(anomalies.router)
app.include_router(scenarios.router)
app.include_router(risk.router)
app.include_router(exports.router)
app.include_router(datasets.router)
app.include_router(query_runs.router)
app.include_router(query_router.router)
app.include_router(marine.router)
app.include_router(mcp.router)
app.include_router(orchestrate.router)
app.include_router(alerts.router)
app.include_router(ml.router)
app.include_router(knowledge.router)
app.include_router(route.router)


# Global exception handler - returns a generic envelope and never leaks stack
# traces.  The full internal error is captured in structured logs instead.
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled exception (path=%s)", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "type": "internal_error",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "An unexpected error occurred",
            "instance": request.url.path,
        },
    )


# Request validation handler - converts pydantic/FastAPI validation failures
# into the structured INVALID_REQUEST contract (Part 31/40) so the frontend
# sees a consistent error vocabulary instead of an opaque 422.
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    detail = exc.errors()
    first = detail[0] if detail else {}
    field = ".".join(str(p) for p in first.get("loc", []) if p not in ("body",))
    message = first.get("msg", "invalid request").replace("Value error, ", "")
    payload = ErrorResponse.build(
        code=ErrorCode.INVALID_REQUEST,
        message=f"{message} [{field}]" if field else message,
        retryable=False, http_status=400).model_dump()
    return JSONResponse(status_code=400, content=payload,
                        headers={"X-Error-Code": ErrorCode.INVALID_REQUEST.value})


# Root endpoint - advertises the stable versioned contract for discovery.
@app.get("/")
async def root():
    meta = contract_meta()
    return {
        "name": "FloatChat API",
        "version": "0.1.0",
        "description": "Voice-first, multilingual, explainable AI interface for ARGO ocean data",
        "api_version": meta["api_version"],
        "response_schema_version": meta["response_schema_version"],
        "docs": "/docs",
        "health": "/api/v1/health",
        "ready": "/api/v1/ready",
        "contract": "/api/v1/contract",
    }


@app.get("/health", include_in_schema=False)
async def root_health():
    """Root-level health alias for frontend convenience."""
    from app.routers.health import health_check
    from app.db.client import get_session
    async with get_session() as session:
        return await health_check(session)


@app.get("/api/v1/contract")
async def contract():
    """Publishes the stable API/response/event schema versions and the list
    of supported language / output capabilities so the frontend can adapt
    without coupling to implementation internals."""
    meta = contract_meta()
    return {
        "api_version": meta["api_version"],
        "response_schema_version": meta["response_schema_version"],
        "event_schema_version": meta["event_schema_version"],
        "orchestrate": {
            "post": "/api/v1/orchestrate",
            "stream_ws": "/api/v1/orchestrate/stream",
        },
        "languages": ["en", "hi", "ta", "ml", "te"],
        "capabilities": ["map", "charts", "alerts", "route"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.log_level == "DEBUG",
        log_level=settings.log_level.lower(),
    )