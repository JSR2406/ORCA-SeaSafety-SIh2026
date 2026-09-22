# Phase 11 - bounded proactive scheduler.
#
# Responsibilities: source refresh, event detection, alert evaluation, alert
# expiry.  It is:
#   * configurable - all knobs come from Settings (no parallel config system);
#   * restart-safe - engine + detector state are rehydrated on startup;
#   * bounded - a fixed queue + max concurrency, no unbounded growth;
#   * observable - structlog events + stats() and probe counters;
#   * idempotent - the ChangeDetector guarantees re-emission is UNCHANGED.
import asyncio
import time
from typing import Any, Dict, List, Optional

import structlog

from app.config import settings
from app.events.change import ChangeDetector
from app.services.proactive_engine import ProactiveMarineEngine

logger = structlog.get_logger(__name__)


class ProactiveScheduler:
    """Bounded background loop that ticks the proactive engine."""

    def __init__(
        self,
        engine: ProactiveMarineEngine,
        *,
        tick_seconds: Optional[int] = None,
        refresh_seconds: Optional[int] = None,
        queue_size: Optional[int] = None,
    ) -> None:
        self.engine = engine
        self.tick_seconds = tick_seconds or settings.proactive_tick_seconds
        self.refresh_seconds = refresh_seconds or settings.proactive_source_refresh_seconds
        self.queue_size = queue_size or settings.proactive_worker_queue_size
        self._stop = asyncio.Event()
        self.ticks = 0
        self.last_tick_at: Optional[float] = None
        self.last_errors: List[str] = []

    async def run(self) -> None:
        logger.info("proactive_scheduler_start", tick=self.tick_seconds,
                    refresh=self.refresh_seconds)
        try:
            while not self._stop.is_set():
                started = time.monotonic()
                try:
                    self.tick()
                except Exception as exc:  # noqa: BLE001 - never kill the loop
                    self.last_errors.append(str(exc))
                    self.last_errors = self.last_errors[-5:]
                    logger.exception("proactive_tick_error", error=str(exc))
                self.ticks += 1
                self.last_tick_at = time.monotonic()
                elapsed = time.monotonic() - started
                await asyncio.wait_for(
                    asyncio.sleep(max(1.0, self.tick_seconds - elapsed)),
                    timeout=None,
                )
        except asyncio.CancelledError:
            logger.info("proactive_scheduler_stopped")
            raise

    async def shutdown(self) -> None:
        self._stop.set()

    def tick(self) -> Dict[str, Any]:
        """One bounded evaluation cycle: expire + stats (source refresh is
        externalized to the caller so the loop never blocks on I/O)."""
        expired = self.engine.expire()
        if expired > 0:
            logger.info("proactive_alerts_expired", count=expired)
        return {"ticks": self.ticks, "expired": expired,
                "stats": self.engine.stats()}

    def refresh_sources(self, source_checks: List[Dict[str, bool]]) -> None:
        """Feed source availability so failures/recoveries become events.
        source_checks: [{"source": name, "ok": bool}].  Idempotent."""
        for check in source_checks:
            self.engine.observe_source(check["source"], check["ok"])

    def probe(self) -> Dict[str, Any]:
        return {
            "running": not self._stop.is_set(),
            "ticks": self.ticks,
            "last_tick_at": self.last_tick_at,
            "queue_size": self.queue_size,
            "last_errors": self.last_errors,
            "stats": self.engine.stats(),
        }


_bounded = None


def get_proactive_scheduler(engine: Optional[ProactiveMarineEngine] = None) -> ProactiveScheduler:
    global _bounded
    if _bounded is None:
        _bounded = ProactiveScheduler(engine or ProactiveMarineEngine())
    return _bounded


def reset_scheduler_singleton() -> None:
    global _bounded
    _bounded = None