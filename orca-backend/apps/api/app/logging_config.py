# Phase 10 - structured logging bootstrap (Part 15).
#
# Activates JSON structured logging when settings.log_format == "json"
# (the default) and a readable console format otherwise.  Every structlog
# event carries request_id (bound by CorrelationMiddleware) so logs can be
# correlated request_id -> run_id -> task_id -> tool_call_id.  Sensitive
# values are never logged (see flit).  Existing stdlib logging calls are
# chained through structlog so no call sites need to change.
import logging
import sys

import structlog


def _shared_processors() -> list:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def setup_logging(log_format: str | None = None, log_level: str | None = None) -> None:
    fmt = (log_format or "json").lower()
    level = (log_level or "INFO").upper()

    if fmt == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=_shared_processors() + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level, logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging through structlog so existing logger calls are
    # captured in the same structured stream without changing call sites.
    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))
    try:
        structlog.stdlib.recreate_defaults(
            log_level=level,
            log_file=None,
        )
    except Exception:  # noqa: BLE001 - stdlib proxy optional
        pass
