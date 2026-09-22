# Minimal asyncio polling scheduler for configured marine data sources.
#
# The scheduler only tracks *configured* live sources (no credentials/config ->
# it logs an idle state and stops.  It is a thin orchestration shell; all real
# behaviour lives in adapters + pipeline, keeping the layer testable.
import asyncio
import time
from typing import Any, Dict, List, Optional

import structlog

from app.config import Settings
from app.datasources.registry import SourceRegistry
from app.ingestion.pipeline import IngestionPipeline

logger = structlog.get_logger(__name__)

# products that need explicit lat/lon fetch parameters we do not synthesize
_COORDINATE_REQUIRED = {"ocean", "tides", "weather_observation", "weather_forecast"}


class SourcePollingScheduler:
    """Polls configured live sources on per-source intervals.

    fetch_params: optional mapping {"source": {"product": {...kwargs}}} that a
    live deployment must supply (e.g. lat/lon centres).  A product entry may
    also be a *list* of per-point dicts (each with lat/lon plus extras such as
    `days` for tides) - the scheduler polls every point:
      {"stormglass": {"tides": {"points": [{"lat": .., "lon": .., "days": 7}, ...]}}}
    Without parameters, coordinate-required products are skipped explicitly
    (no fabricated requests).
    """

    def __init__(
        self,
        settings: Settings,
        registry: SourceRegistry,
        pipeline: IngestionPipeline,
        fetch_params: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.settings = settings
        self.registry = registry
        self.pipeline = pipeline
        self.fetch_params = fetch_params or {}
        self._stop = asyncio.Event()

    async def run(self) -> None:
        configured = [s for s in self.registry.list() if s.is_configured]
        if not configured:
            logger.info("scheduler_idle_no_configured_sources")
            await self._stop.wait()
            return
        logger.info("scheduler_start", sources=[s.name for s in configured])
        tasks = [asyncio.create_task(self._poll_loop(source_name, self._stop))
                 for source_name in (s.name for s in configured)]
        try:
            await self._stop.wait()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def shutdown(self) -> None:
        self._stop.set()

    async def _poll_loop(self, source_name: str, stop: asyncio.Event) -> None:
        interval = self.settings.source_poll_interval_seconds.get(
            source_name, self.settings.data_poll_interval_seconds)
        while not stop.is_set():
            started = time.monotonic()
            await self._poll_source(source_name)
            elapsed = time.monotonic() - started
            await asyncio.wait_for(
                asyncio.sleep(max(1.0, interval - elapsed)),
                timeout=None,
            )

    def _expand_param_sets(self, source_name: str, product: str) -> List[Dict]:
        """Resolve the fetch kwargs for a product into 1+ parameter sets.

        A `points` list under the product entry fans out into one set per
        point; otherwise a single set (possibly empty) is returned.  Product
        entries without coordinates for a coordinate-required product expand
        to nothing.
        """
        raw = self.fetch_params.get(source_name, {}).get(product)
        if raw is None:
            return [] if product in _COORDINATE_REQUIRED else [{}]

        if isinstance(raw, list):
            return [p for p in raw if isinstance(p, dict) and p]

        if isinstance(raw, dict):
            shared = {k: v for k, v in raw.items() if k != "points"}
            points = raw.get("points")
            if isinstance(points, list) and points:
                return [
                    {**shared, **p} for p in points if isinstance(p, dict) and p
                ]
            if product in _COORDINATE_REQUIRED and not raw.get("lat"):
                return []
            return [raw]

        if product in _COORDINATE_REQUIRED:
            return []
        return [{}]

    async def _poll_source(self, source_name: str) -> None:
        source = self.registry.get(source_name)
        for cap in source.capabilities:
            product = cap.data_product
            for product_params in self._expand_param_sets(source_name, product):
                if product in _COORDINATE_REQUIRED and not product_params.get("lat"):
                    logger.info("scheduler_skip_requires_coordinates",
                                source=source_name, product=product)
                    continue
                try:
                    await self.pipeline.run_product(source_name, product, product_params)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("scheduler_poll_error", source=source_name,
                                   product=product, error=str(exc))