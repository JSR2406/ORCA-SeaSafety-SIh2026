# Registry of real-time marine data sources.
from typing import Dict, List, Optional
import structlog

from app.config import Settings
from app.datasources.base import BaseMarineDataSource
from app.datasources.coastwatch import CoastWatchAdapter
from app.datasources.gdacs import GDACSAdapter
from app.datasources.http import HttpDataTransport
from app.datasources.imd import IMDAdapter
from app.datasources.incois import INCOISAdapter
from app.datasources.jtwc import JTWCAdapter
from app.datasources.mock import MockMarineDataSource
from app.datasources.mosdac import MOSDACAdapter
from app.datasources.open_meteo import OpenMeteoAdapter
from app.datasources.openweather import OpenWeatherAdapter
from app.datasources.stormglass import StormGlassAdapter
from app.models.common import DataStatus
from app.models.source import SourceAvailability, SourceInfo, SourceStatus

logger = structlog.get_logger(__name__)


def build_registry(
    settings: Settings,
    transport: Optional[HttpDataTransport] = None,
) -> "SourceRegistry":
    return SourceRegistry(settings, transport)


class SourceRegistry:
    """Holds the configured marine data sources and their runtime state."""

    def __init__(self, settings: Settings, transport: Optional[HttpDataTransport] = None):
        self.settings = settings
        # Open-Meteo / CoastWatch / Storm Glass / OpenWeather / JTWC are the
        # live stack; the government adapters stay registered but disabled so
        # they can be flipped on when an endpoint becomes reachable.
        factories = (
            OpenMeteoAdapter, CoastWatchAdapter, StormGlassAdapter,
            OpenWeatherAdapter, JTWCAdapter, GDACSAdapter,
            INCOISAdapter, IMDAdapter, MOSDACAdapter,
            MockMarineDataSource,
        )
        self._sources: Dict[str, BaseMarineDataSource] = {}
        for factory in factories:
            source = factory(settings, transport=transport)
            self._sources[source.name] = source

    def get(self, name: str) -> BaseMarineDataSource:
        assert name in self._sources, f"unknown marine source: {name}"
        return self._sources[name]

    def list(self) -> List[BaseMarineDataSource]:
        return list(self._sources.values())

    def names(self) -> List[str]:
        return list(self._sources.keys())

    def configured_names(self) -> List[str]:
        return [name for name, s in self._sources.items() if s.is_configured]

    def get_info(self) -> List[SourceInfo]:
        # Hide disabled TEST-MOCK sources from the catalog so the default
        # catalog lists only real providers (mock appears once enabled/demo).
        return [
            s.get_info() for s in self._sources.values()
            if not (s.is_mock and not s.enabled)
        ]

    def availability(self) -> Dict[str, SourceAvailability]:
        return {name: s.get_availability() for name, s in self._sources.items()}

    def status(self) -> List[SourceStatus]:
        """Adjudicated per-source freshness status.

        Ingestion timestamps (TrackedSource in the DB, when present) are merged
        in by the MarineDataService; here we only report the configured state.
        """
        return [
            SourceStatus(
                source=s.name,
                source_type=s.source_type,
                status=(DataStatus.TEST_MOCK if s.is_mock
                        else _status_from_availability(s.get_availability())),
                configured=s.is_configured,
                connected=s.is_configured,
                message=s.get_availability().message,
            )
            for s in self._sources.values()
        ]


def _status_from_availability(avail: SourceAvailability):
    from app.models.common import DataStatus
    if not avail.configured:
        return DataStatus.NOT_CONFIGURED
    return DataStatus.UNAVAILABLE if not avail.connected else DataStatus.LIVE