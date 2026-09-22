# Ingestion pipeline: fetch -> validate -> normalize -> dedup -> store -> track.
#
# Idempotency is enforced via the (source, source_record_id) natural key in the
# DB (UNIQUE + ON CONFLICT DO NOTHING) plus a deterministic content hash for
# records without upstream IDs.  Failures are explicit and tracked - never
# masked by mock data.
import structlog
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from app.config import Settings
from app.datasources.errors import (
    SourceInvalidDataError,
    SourceNotConfiguredError,
    SourceRateLimitError,
    SourceUnavailableError,
)
from app.datasources.registry import SourceRegistry
from app.db.marine_repository import MarineRepository
from app.ingestion.dedup import dedup_batch, ensure_dedup_keys
from app.ingestion.mapping import map_records
from app.models.common import QualityStatus

logger = structlog.get_logger(__name__)

FETCH_METHODS: Dict[str, str] = {
    "ocean": "fetch_ocean",
    "weather_observation": "fetch_weather_observation",
    "weather_forecast": "fetch_weather_forecast",
    "tides": "fetch_tides",
    "pfz": "fetch_pfz",
    "warnings": "fetch_warnings",
}

INSERT_METHODS: Dict[str, Callable[[MarineRepository, List[Dict[str, Any]]], Awaitable[Tuple[int, int]]]] = {
    "ocean": MarineRepository.insert_ocean,
    "weather_observation": MarineRepository.insert_weather_observation,
    "weather_forecast": MarineRepository.insert_weather_forecast,
    "tides": MarineRepository.insert_tides,
    "pfz": MarineRepository.insert_pfz,
    "warnings": MarineRepository.insert_warnings,
}

_LATEST_TIMESTAMP_ATTRS: Dict[str, str] = {
    "ocean": "observation_time",
    "weather_observation": "valid_time",
    "weather_forecast": "issue_time",
    "tides": "event_time",
    "pfz": "generated_at",
}

_COORDINATE_REQUIRED_PRODUCTS = {"ocean", "tides", "weather_observation", "weather_forecast"}


def _error_category(exc: Exception) -> str:
    if isinstance(exc, SourceNotConfiguredError):
        return "not_configured"
    if isinstance(exc, SourceRateLimitError):
        return "rate_limited"
    if isinstance(exc, SourceUnavailableError):
        return "unavailable" if exc.transient else "unavailable_permanent"
    if isinstance(exc, SourceInvalidDataError):
        return "invalid_data"
    return "error"


class IngestionPipeline:
    """Runs a single (source, product) ingestion and tracks its outcome."""

    def __init__(
        self,
        settings: Settings,
        registry: SourceRegistry,
        session_factory: Callable,
        classifier_factory: Optional[Callable] = None,
    ):
        self.settings = settings
        self.registry = registry
        self.session_factory = session_factory
        self.classifier = classifier_factory(settings) if classifier_factory else None
        if self.classifier is None:
            from app.ingestion.validation import MarineValidationService
            self.classifier = MarineValidationService(settings)

    def _classify(self, product: str, record: Any) -> QualityStatus:
        method = {
            "ocean": self.classifier.classify_ocean,
            "weather_observation": self.classifier.classify_weather_observation,
            "weather_forecast": self.classifier.classify_weather_forecast,
            "tides": self.classifier.classify_tide,
            "pfz": self.classifier.classify_pfz,
            "warnings": self.classifier.classify_warning,
        }[product]
        quality, _reasons = method(record)
        return quality

    @staticmethod
    def _latest_timestamp(product: str, records: List[Any]) -> Optional[Any]:
        attr = _LATEST_TIMESTAMP_ATTRS.get(product)
        if not attr:
            return None
        values = [getattr(r, attr) for r in records if getattr(r, attr, None)]
        return max(values) if values else None

    async def run_product(
        self,
        source_name: str,
        product: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Execute one ingestion for a source/product pair.

        Returns a summary dict (or None when the product is not a known
        ingestible product). Raises nothing - failures are recorded.
        """
        if product not in FETCH_METHODS:
            logger.warning("ingestion_unknown_product", source=source_name, product=product)
            return None

        source = self.registry.get(source_name)
        summary: Dict[str, Any] = {
            "source": source_name, "product": product, "status": "running",
            "fetched": 0, "valid": 0, "suspicious": 0, "invalid": 0,
            "inserted": 0, "duplicates": 0, "error": None, "error_category": None,
        }

        try:
            if not source.is_configured:
                raise SourceNotConfiguredError(
                    f"source '{source_name}' is not configured for '{product}'"
                )
            if not source.capabilities or not any(
                cap.data_product == product for cap in source.capabilities
            ):
                raise SourceUnavailableError(
                    f"source '{source_name}' does not support product '{product}'",
                    transient=False,
                )
            fetch_kwargs = dict(params or {})
            if product in _COORDINATE_REQUIRED_PRODUCTS and not fetch_kwargs.get("lat"):
                raise SourceUnavailableError(
                    f"product '{product}' needs lat/lon fetch parameters (not configured)",
                    transient=False,
                )

            records = await getattr(source, FETCH_METHODS[product])(**fetch_kwargs)
            summary["fetched"] = len(records)

            valid_recs, suspicious_recs, invalid_recs = [], [], []
            for record in records:
                quality = self._classify(product, record)
                if quality == QualityStatus.INVALID:
                    invalid_recs.append(record)
                elif quality == QualityStatus.SUSPICIOUS:
                    suspicious_recs.append(record)
                else:
                    valid_recs.append(record)

            summary["invalid"] = len(invalid_recs)
            summary["suspicious"] = len(suspicious_recs)
            summary["valid"] = len(valid_recs)

            async with self.session_factory() as session:
                repo = MarineRepository(session, srid=self.settings.geom_srid)
                run = await repo.start_ingestion_run(source_name, product)
                inserted_total, dup_total = 0, 0
                for group in (valid_recs, suspicious_recs):
                    keyed = ensure_dedup_keys(group, source_name)
                    pre = len(keyed)
                    deduped = dedup_batch(keyed, source_name)
                    dup_total += pre - len(deduped)
                    rows = map_records(product, deduped, self.settings)
                    if rows:
                        try:
                            ins, dup = await INSERT_METHODS[product](repo, rows)
                        except Exception as exc:
                            raise SourceUnavailableError(
                                f"store failure for {product}: {exc}", transient=False,
                            ) from exc
                        inserted_total += ins
                        dup_total += dup
                summary["inserted"] = inserted_total
                summary["duplicates"] = dup_total

                latest_ts = self._latest_timestamp(product, records)
                if not invalid_recs:
                    await repo.set_source_success(source_name, latest_ts)
                    await repo.finish_ingestion_run(
                        run.id, status="success", fetched=summary["fetched"],
                        valid=summary["valid"], suspicious=summary["suspicious"],
                        invalid=summary["invalid"], inserted=inserted_total,
                        duplicates=dup_total,
                    )
                    summary["status"] = "success"
                else:
                    await repo.set_source_success(source_name, latest_ts)
                    await repo.finish_ingestion_run(
                        run.id, status="partial", fetched=summary["fetched"],
                        valid=summary["valid"], suspicious=summary["suspicious"],
                        invalid=summary["invalid"], inserted=inserted_total,
                        duplicates=dup_total,
                        error=f"{summary['invalid']} invalid records dropped",
                        error_category="invalid_records",
                    )
                    summary["status"] = "partial"
            logger.info("ingestion_complete", **summary)
            return summary

        except Exception as exc:
            category = _error_category(exc)
            summary["status"] = "skipped" if category == "not_configured" else "failure"
            summary["error"] = str(exc)[:2000]
            summary["error_category"] = category
            try:
                async with self.session_factory() as session:
                    repo = MarineRepository(session, srid=self.settings.geom_srid)
                    run = await repo.start_ingestion_run(source_name, product)
                    if category != "not_configured":
                        await repo.set_source_failure(source_name, str(exc), category)
                    await repo.finish_ingestion_run(
                        run.id, status=summary["status"], fetched=summary["fetched"],
                        error=str(exc)[:2000], error_category=category,
                    )
            except Exception as inner:
                logger.warning("ingestion_tracking_failed", source=source_name,
                               product=product, error=str(inner))
            logger.warning("ingestion_failed", source=source_name, product=product,
                           error=str(exc), category=category)
            return summary