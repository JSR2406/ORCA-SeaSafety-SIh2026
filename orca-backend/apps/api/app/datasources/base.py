# Base contract for real-time marine data sources.
#
# Adapters target GOVT-mandated Indian marine data providers:
#   INCOIS  - ocean conditions, currents, waves, tides, PFZ, fishing advisories
#   IMD     - marine weather observation/forecast, cyclone warnings
#   MOSDAC  - satellite-derived products (SST/chlorophyll, PFZ support)
#
# NO MOCK FALLBACK POLICY:
# - Every adapter reports its configuration state honestly.
# - If a source is not configured (no credentials/endpoint enabled), product
#   fetches raise SourceNotConfiguredError and consumers receive an explicit
#   NOT_CONFIGURED status - fabricated data is never inserted.
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import structlog

from app.config import Settings
from app.datasources.errors import (
    SourceNotConfiguredError,
    SourceUnavailableError,
)
from app.datasources.http import HttpDataTransport
from app.models.common import QualityStatus
from app.models.ocean import OceanConditions
from app.models.pfz import PFZZone
from app.models.source import (
    SourceAvailability,
    SourceCapability,
    SourceInfo,
    SourceType,
)
from app.models.tides import TidePrediction
from app.models.weather import WeatherForecast, WeatherObservation
from app.models.warnings import MarineWarning

logger: logging.Logger = structlog.get_logger(__name__)


class BaseMarineDataSource(ABC):
    """Abstract real-time marine data source.

    Subclasses control their own config keys (base_url / api_key / enabled),
    their capabilities and their normalizers.  Fetching any product when the
    source is not configured raises SourceNotConfiguredError.
    """

    name: str = ""
    display_name: str = ""
    source_type: SourceType = SourceType.UNKNOWN
    default_base_url: str = ""

    # TEST-MOCK flag: subclass overrides to True for synthetic/sample sources.
    # Such sources never report LIVE - only TEST_MOCK - so mocks are never
    # passed off as real ingestion.
    is_mock: bool = False

    # Product -> endpoint path mapping.  Unknown products have no entry, and
    # fetching them raises SourceNotConfiguredError until a real endpoint is
    # provided (honest "configuration required" - no fabricated URLs).
    PRODUCT_ENDPOINTS: Dict[str, str] = {}

    def __init__(self, settings: Settings, transport: Optional[HttpDataTransport] = None):
        self.settings = settings
        self.transport = transport or HttpDataTransport(settings)

    # -- configuration -----------------------------------------------------
    @property
    @abstractmethod
    def base_url(self) -> str:
        """Configured base URL from settings."""

    @property
    @abstractmethod
    def api_key(self) -> Optional[str]:
        """Configured API key from settings (None if unused)."""

    @property
    def enabled(self) -> bool:
        return True

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.enabled)

    @property
    @abstractmethod
    def capabilities(self) -> List[SourceCapability]:
        ...

    # -- helpers -----------------------------------------------------------
    def _ensure_configured(self, product: str) -> None:
        if not self.is_configured:
            raise SourceNotConfiguredError(
                f"source '{self.name}' is not configured; cannot fetch '{product}'"
            )

    def _auth_headers(self) -> Optional[Dict[str, str]]:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return None

    async def _fetch_json(self, path: str, params=None) -> dict:
        url = self.base_url.rstrip("/") + path
        return await self.transport.get_json(url, params=params, headers=self._auth_headers())

    def _unsupported(self, product: str) -> SourceUnavailableError:
        return SourceUnavailableError(
            f"source '{self.name}' does not provide product '{product}'",
            transient=False,
        )

    def _endpoint(self, product: str) -> str:
        """Resolve the configured endpoint path for a product.

        Raises SourceNotConfiguredError when the source profile has no endpoint
        defined for the product - i.e. "configuration required".
        """
        path = self.PRODUCT_ENDPOINTS.get(product)
        if not path:
            raise SourceNotConfiguredError(
                f"source '{self.name}' has no configured endpoint for "
                f"product '{product}' (configuration required)."
            )
        return path

    # -- product fetchers (override per source) -----------------------------
    async def fetch_ocean(self, *, lat: float, lon: float, time=None, **kw) -> List[OceanConditions]:
        raise self._unsupported("ocean")

    async def fetch_weather_observation(self, *, lat: float, lon: float, time=None, **kw) -> List[WeatherObservation]:
        raise self._unsupported("weather_observation")

    async def fetch_weather_forecast(self, *, lat: float, lon: float, time=None, **kw) -> List[WeatherForecast]:
        raise self._unsupported("weather_forecast")

    async def fetch_warnings(self, *, lat: float = None, lon: float = None, **kw) -> List[MarineWarning]:
        raise self._unsupported("warnings")

    async def fetch_tides(self, *, lat: float, lon: float, start=None, end=None, **kw) -> List[TidePrediction]:
        raise self._unsupported("tides")

    async def fetch_pfz(self, *, lat: float = None, lon: float = None, date=None, **kw) -> List[PFZZone]:
        raise self._unsupported("pfz")

    # -- availability --------------------------------------------------------
    def get_availability(self) -> SourceAvailability:
        if self.is_mock:
            return SourceAvailability(
                source=self.name,
                configured=self.is_configured,
                connected=self.is_configured,
                message=(f"Source '{self.name}' provides TEST-MOCK (sample) data only; "
                         f"it is never LIVE. Enable it only to exercise the pipeline "
                         f"until real source credentials are approved."),
            )
        if not self.is_configured:
            return SourceAvailability(
                source=self.name,
                configured=False,
                connected=False,
                message=f"Source '{self.name}' is not configured "
                        f"(no credentials/endpoint enabled). Connect it to go live.",
            )
        return SourceAvailability(
            source=self.name,
            configured=True,
            message=f"Source '{self.name}' is configured and ready for ingestion.",
        )

    def get_info(self) -> SourceInfo:
        return SourceInfo(
            name=self.name,
            display_name=self.display_name,
            source_type=self.source_type,
            base_url=self.base_url,
            enabled=self.enabled and self.is_configured,
            capabilities=self.capabilities,
        )

    # -- normalization -------------------------------------------------------
    # Normalizers turn a fetched raw payload (list items) into canonical
    # models.  They are exercised deterministically by unit tests using
    # fixtures; at runtime they only ever receive real fetched payloads.
    @staticmethod
    def _to_quality(flags: Dict[str, str]) -> QualityStatus:
        for name in ("quality_flag", "qc_flag", "quality"):
            val = str(flags.get(name, "")).lower()
            if val in (QualityStatus.VALID.value, "good", "pass", "2"):
                return QualityStatus.VALID
            if val in (QualityStatus.SUSPICIOUS.value, "suspect", "3"):
                return QualityStatus.SUSPICIOUS
            if val in (QualityStatus.INVALID.value, "bad", "4"):
                return QualityStatus.INVALID
            if val in (QualityStatus.MISSING.value, "", "none", "1"):
                return QualityStatus.MISSING
        return QualityStatus.VALID