# Real-time marine data source adapters.
# Live stack: Open-Meteo / NOAA CoastWatch / Storm Glass / OpenWeather / JTWC / GDACS.
# Legacy government adapters (INCOIS / IMD / MOSDAC) stay registered but are
# disabled by default. No fabricated fallbacks: an unconfigured source is
# reported as NOT_CONFIGURED, never silently replaced with mock data.
from app.datasources.base import BaseMarineDataSource  # noqa: F401
from app.datasources.coastwatch import CoastWatchAdapter  # noqa: F401
from app.datasources.errors import (  # noqa: F401
    SourceError,
    SourceInvalidDataError,
    SourceNotConfiguredError,
    SourceRateLimitError,
    SourceUnavailableError,
)
from app.datasources.gdacs import GDACSAdapter  # noqa: F401
from app.datasources.http import HttpDataTransport  # noqa: F401
from app.datasources.imd import IMDAdapter  # noqa: F401
from app.datasources.incois import INCOISAdapter  # noqa: F401
from app.datasources.jtwc import JTWCAdapter  # noqa: F401
from app.datasources.mosdac import MOSDACAdapter  # noqa: F401
from app.datasources.open_meteo import OpenMeteoAdapter  # noqa: F401
from app.datasources.openweather import OpenWeatherAdapter  # noqa: F401
from app.datasources.registry import SourceRegistry, build_registry  # noqa: F401
from app.datasources.stormglass import StormGlassAdapter  # noqa: F401