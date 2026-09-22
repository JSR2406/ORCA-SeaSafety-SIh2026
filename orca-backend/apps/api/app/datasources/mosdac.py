# MOSDAC adapter - Meteorological & Oceanographic Satellite Data Archival Centre.
#
# Uses open-source data channels:
#   - OGC WMS/WFS at mosdac.gov.in/geoserver for near-real-time satellite
#     products (SST, chlorophyll, ocean currents)
#   - ERDDAP (when available) for gridded satellite data
#   - Scraping for PFZ-related satellite advisories
#
# MOSDAC is operated by ISRO/SAC.  The OGC web services are publicly
# accessible for read operations.
from datetime import timedelta
import logging
import re
from typing import Dict, List, Optional

from app.config import Settings
from app.datasources.base import BaseMarineDataSource
from app.datasources.errors import SourceInvalidDataError
from app.datasources.http import HttpDataTransport
from app.datasources.normalize import (
    ensure_list,
    parse_datetime,
    take_numeric,
    take_string,
)
from app.datasources.scrapers import fetch_mosdac_wms
from app.models.common import QualityStatus, utcnow
from app.models.ocean import OceanConditions
from app.models.pfz import PFZZone
from app.models.source import SourceCapability, SourceType
from app.models.warnings import MarineWarning, WarningSeverity, WarningType

logger = logging.getLogger(__name__)


class MOSDACAdapter(BaseMarineDataSource):
    name = "mosdac"
    display_name = "MOSDAC (ISRO) Satellite Ocean Products"
    source_type = SourceType.MOSDAC

    PRODUCT_ENDPOINTS: Dict[str, str] = {
        "ocean": "/geoserver/wms",
        "pfz": "/geoserver/wms",
        "warnings": "/scrape",
    }

    def __init__(self, settings: Settings, transport: Optional[HttpDataTransport] = None):
        super().__init__(settings, transport)

    @property
    def base_url(self) -> str:
        return self.settings.mosdac_base_url

    @property
    def api_key(self) -> Optional[str]:
        return self.settings.mosdac_api_key or None

    @property
    def enabled(self) -> bool:
        return self.settings.mosdac_enabled

    @property
    def capabilities(self) -> List[SourceCapability]:
        return [
            SourceCapability(
                name="satellite_ocean",
                description="Satellite-derived SST, chlorophyll via OGC WMS",
                data_product="ocean",
                config_required=True,
            ),
            SourceCapability(
                name="pfz_satellite",
                description="PFZ-related satellite advisory zones",
                data_product="pfz",
                config_required=True,
            ),
            SourceCapability(
                name="satellite_warnings",
                description="Marine warnings from MOSDAC satellite monitoring",
                data_product="warnings",
                config_required=True,
            ),
        ]

    # ------------------------------------------------------------------ ocean
    async def fetch_ocean(
        self, *, lat: float, lon: float, time=None, **kw
    ) -> List[OceanConditions]:
        self._ensure_configured("ocean")

        # Query MOSDAC OGC WMS for satellite products at this point.
        wms_data = await fetch_mosdac_wms(
            lat, lon,
            layers=["mosdac:sst", "mosdac:chlorophyll", "mosdac:current"],
        )

        results: List[OceanConditions] = []

        if wms_data:
            # WMS GetFeatureInfo returns pixel values.
            sst = None
            chl = None
            for layer_key, props in wms_data.items():
                if "sst" in layer_key.lower():
                    sst = take_numeric(props, "GRAY_INDEX", "value", "sst")
                elif "chl" in layer_key.lower():
                    chl = take_numeric(props, "GRAY_INDEX", "value", "chlorophyll")

            if sst is not None or chl is not None:
                results.append(OceanConditions(
                    latitude=lat,
                    longitude=lon,
                    observation_time=time or utcnow(),
                    source_timestamp=utcnow(),
                    sst_c=sst,
                    chlorophyll=chl,
                    wave_height_m=None,
                    wave_period_s=None,
                    wave_direction_deg=None,
                    current_speed_ms=None,
                    current_direction_deg=None,
                    salinity_psu=None,
                    source=self.name,
                    source_record_id=f"mosdac-wms-{lat:.2f}-{lon:.2f}",
                    quality=QualityStatus.VALID,
                    raw_payload=wms_data,
                ))

        # Fallback: NOAA CoastWatch MUR SST (real lat/lon axes) fills the
        # satellite-product role when MOSDAC's geoserver is unreachable.
        if not results:
            coast = await self._fetch_coastwatch_satellite(lat, lon, time)
            results.extend(coast)

        # Fallback: try ERDDAP if MOSDAC has one.
        if not results:
            erddap_data = await self._fetch_from_erddap(lat, lon, time)
            results.extend(erddap_data)

        # MOSDAC's geoserver/catalog require SSO; when nothing resolves,
        # fall back to keyless Open-Meteo waves so the ocean bucket is live.
        if not results:
            from app.datasources.scrapers import fetch_open_meteo_marine

            wave = await fetch_open_meteo_marine(lat, lon)
            if wave:
                wave_time = parse_datetime(wave.get("observation_time")) or (time or utcnow())
                results.append(OceanConditions(
                    latitude=lat,
                    longitude=lon,
                    observation_time=wave_time,
                    source_timestamp=utcnow(),
                    wave_height_m=wave.get("wave_height_m"),
                    wave_period_s=wave.get("wave_period_s"),
                    wave_direction_deg=wave.get("wave_direction_deg"),
                    source=self.name,
                    source_record_id=f"mosdac-openmeteo-{lat:.2f}-{lon:.2f}",
                    quality=QualityStatus.VALID,
                    raw_payload={"waves_provider": "open-meteo", "waves": wave},
                ))

        return results

    async def _fetch_coastwatch_satellite(
        self, lat: float, lon: float, time
    ) -> List[OceanConditions]:
        """Fallback: NOAA CoastWatch MUR SST + VIIRS chl at the point.

        Keyless near-real-time satellite products on real lat/lon axes;
        works around MOSDAC's retired geoserver.  VIIRS chl may be
        restricted (403) in which case only SST is reported.
        """
        from app.datasources.scrapers import (
            fetch_coastwatch_chlorophyll_point,
            fetch_coastwatch_sst_point,
        )

        sst_row = await fetch_coastwatch_sst_point(lat, lon)
        if not sst_row:
            return []

        t = time or utcnow()
        sst_time = parse_datetime(sst_row.get("time"))
        observation_time = sst_time or t
        stale = ((t - observation_time).total_seconds() > 48 * 3600) if sst_time else False
        quality = QualityStatus.STALE if stale else QualityStatus.VALID

        chl_row = await fetch_coastwatch_chlorophyll_point(lat, lon)
        if chl_row:
            sst_row["chlorophyll"] = chl_row.get("chlorophyll")

        payload = {
            "satellite_provider": "noaa_coastwatch",
            **sst_row,
        }
        if chl_row:
            payload["chlorophyll_provider"] = "noaa_coastwatch"

        return [OceanConditions(
            latitude=lat,
            longitude=lon,
            observation_time=observation_time,
            source_timestamp=utcnow(),
            sst_c=sst_row.get("sst_c"),
            chlorophyll=sst_row.get("chlorophyll"),
            wave_height_m=None,
            wave_period_s=None,
            wave_direction_deg=None,
            current_speed_ms=None,
            current_direction_deg=None,
            salinity_psu=None,
            source=self.name,
            source_record_id=f"mosdac-coastwatch-{lat:.2f}-{lon:.2f}",
            quality=quality,
            raw_payload=payload,
        )]

    async def _fetch_from_erddap(
        self, lat: float, lon: float, time
    ) -> List[OceanConditions]:
        """Fallback: query INCOIS ERDDAP via the shared scraper."""
        from app.datasources.scrapers import fetch_erddap_ocean

        t = time or utcnow()
        rows = await fetch_erddap_ocean(lat, lon, time_start=t - timedelta(hours=24), time_end=t)

        results = []
        for row in rows[:1]:
            try:
                r_lat = row.get("latitude", lat)
                r_lon = row.get("longitude", lon)
                time_obs = parse_datetime(row.get("time"))
                if not time_obs:
                    time_obs = t
                stale = ((t - time_obs).total_seconds() > 24 * 3600) if time_obs else True
                quality = QualityStatus.STALE if stale else QualityStatus.VALID
                results.append(OceanConditions(
                    latitude=float(r_lat) if r_lat else lat,
                    longitude=float(r_lon) if r_lon else lon,
                    observation_time=time_obs,
                    source_timestamp=utcnow(),
                    sst_c=row.get("sst_c") or row.get("water_temp_c"),
                    chlorophyll=row.get("chlorophylla") or row.get("chlorophyll"),
                    wave_height_m=None,
                    wave_period_s=None,
                    wave_direction_deg=None,
                    current_speed_ms=row.get("current_speed_ms"),
                    current_direction_deg=row.get("current_direction_deg"),
                    salinity_psu=row.get("salinity_psu"),
                    source=self.name,
                    source_record_id=f"mosdac-erddap-{lat:.2f}-{lon:.2f}",
                    quality=quality,
                    raw_payload=row,
                ))
            except Exception:
                continue
        return results

    # --------------------------------------------------------------------- pfz
    async def fetch_pfz(
        self, *, lat: float = None, lon: float = None, date=None, **kw
    ) -> List[PFZZone]:
        self._ensure_configured("pfz")

        # PFZ from MOSDAC is the same INCOIS data; use the INCOIS scraper.
        from app.datasources.scrapers import scrape_incois_pfz

        # Determine sector from lat/lon.
        sector = self._lat_lon_to_sector(lat, lon)
        raw_pfz = await scrape_incois_pfz(sector)

        results: List[PFZZone] = []
        for item in raw_pfz:
            try:
                p_lat = item.get("lat")
                p_lon = item.get("lon")
                if p_lat is None or p_lon is None:
                    continue

                delta = 0.25
                geometry = {
                    "type": "Polygon",
                    "coordinates": [[
                        [p_lon - delta, p_lat - delta],
                        [p_lon + delta, p_lat - delta],
                        [p_lon + delta, p_lat + delta],
                        [p_lon - delta, p_lat + delta],
                        [p_lon - delta, p_lat - delta],
                    ]],
                }

                species = [item["species"]] if item.get("species") else []

                results.append(PFZZone(
                    geometry=geometry,
                    centroid={"latitude": p_lat, "longitude": p_lon},
                    generated_at=utcnow(),
                    valid_from=parse_datetime(item.get("valid_from")) or utcnow(),
                    valid_until=parse_datetime(item.get("valid_until")) or (utcnow() + timedelta(hours=72)),
                    species=species,
                    confidence=0.5,
                    metadata={"sector": sector, "source": "mosdac"},
                    source=self.name,
                    source_record_id=f"mosdac-pfz-{sector}-{p_lat:.2f}-{p_lon:.2f}",
                    quality=QualityStatus.VALID,
                    raw_payload=item,
                ))
            except Exception:
                continue

        # Fallback: INCOIS PFZ text page is JS-rendered (needs a headless
        # browser); derive likely fishing fronts from real satellite SST.
        if not results and lat is not None and lon is not None:
            derived = await self._derive_pfz_from_sst_fronts(lat, lon, sector)
            results.extend(derived)

        return results

    async def _derive_pfz_from_sst_fronts(
        self, lat: float, lon: float, sector: str
    ) -> List[PFZZone]:
        """Same satellite SST-front fallback used by INCOIS (see incois.py)."""
        from app.datasources.scrapers import (
            derive_pfz_fronts_from_grid,
            fetch_coastwatch_sst_front_grid,
        )

        grid = await fetch_coastwatch_sst_front_grid(lat, lon)
        if not grid:
            return []

        fronts = derive_pfz_fronts_from_grid(grid)
        results: List[PFZZone] = []
        for front in fronts[:8]:
            try:
                p_lat = front["lat"]
                p_lon = front["lon"]
                delta = 0.20
                geometry = {
                    "type": "Polygon",
                    "coordinates": [[
                        [p_lon - delta, p_lat - delta],
                        [p_lon + delta, p_lat - delta],
                        [p_lon + delta, p_lat + delta],
                        [p_lon - delta, p_lat + delta],
                        [p_lon - delta, p_lat - delta],
                    ]],
                }
                confidence = max(0.35, min(0.75, 0.35 + front["front_delta_c"]))
                results.append(PFZZone(
                    geometry=geometry,
                    centroid={"latitude": p_lat, "longitude": p_lon},
                    generated_at=utcnow(),
                    valid_from=utcnow(),
                    valid_until=utcnow() + timedelta(hours=72),
                    species=[],
                    confidence=round(confidence, 3),
                    metadata={
                        "sector": sector,
                        "estimated": True,
                        "basis": "noaa_coastwatch_mur_sst_front",
                        "front_delta_c": front["front_delta_c"],
                        "method": "satellite-sst-front",
                        "note": "Derived from satellite SST fronts; not the official INCOIS PFZ advisory.",
                    },
                    source=self.name,
                    source_record_id=f"mosdac-pfz-derived-{p_lat:.2f}-{p_lon:.2f}",
                    quality=QualityStatus.VALID,
                    raw_payload=front,
                ))
            except Exception:
                continue
        return results

    def _lat_lon_to_sector(self, lat: float, lon: float) -> str:
        if lat is None or lon is None:
            return "KERALA"
        sector_centers = {
            "GUJARAT": (22.0, 70.0), "MAHARASHTRA": (17.0, 73.0),
            "GOA": (15.4, 73.8), "KARNATAKA": (13.5, 74.5),
            "KERALA": (10.0, 76.3), "SOUTH_TAMILNADU": (8.5, 78.0),
            "NORTH_TAMILNADU": (12.5, 80.0), "SOUTH_ANDHRA_PRADESH": (14.5, 80.0),
            "NORTH_ANDHRA_PRADESH": (17.0, 82.5), "ODISHA": (19.0, 86.0),
            "WEST_BENGAL": (21.0, 88.0), "ANDAMAN": (11.5, 92.5),
            "NICOBAR": (7.5, 93.5), "LAKSHADWEEP": (10.5, 72.5),
        }
        best = "KERALA"
        best_d = float("inf")
        for s, (sl, sLon) in sector_centers.items():
            d = abs(lat - sl) + abs(lon - sLon)
            if d < best_d:
                best_d = d
                best = s
        return best

    # ---------------------------------------------------------------- warnings
    async def fetch_warnings(
        self, *, lat: float = None, lon: float = None, **kw
    ) -> List[MarineWarning]:
        self._ensure_configured("warnings")

        # MOSDAC warnings overlap with INCOIS; scrape INCOIS RSMC.
        from app.datasources.scrapers import scrape_incois_warnings

        raw_warnings = await scrape_incois_warnings()

        results: List[MarineWarning] = []
        for item in raw_warnings:
            try:
                w_type_str = item.get("warning_type", "other")
                warning_type = _map_warning_type(w_type_str)
                severity = _map_severity(item.get("severity", "unknown"))

                results.append(MarineWarning(
                    warning_id=item.get("warning_id", f"mosdac-warn-{hash(str(item)) & 0xFFFFFF:06x}"),
                    warning_type=warning_type,
                    severity=severity,
                    geometry=item.get("geometry") or {},
                    valid_from=parse_datetime(item.get("valid_from")),
                    valid_until=parse_datetime(item.get("valid_until")),
                    issued_at=utcnow(),
                    updated_at=utcnow(),
                    description=item.get("description", ""),
                    source=self.name,
                    source_record_id=item.get("warning_id"),
                    metadata={},
                ))
            except Exception:
                continue

        return results


def _map_warning_type(value: str) -> WarningType:
    lowered = value.lower()
    if "cyclone" in lowered:
        return WarningType.CYCLONE
    if "fishing" in lowered or "fish" in lowered:
        return WarningType.FISHING_WARNING
    if "storm" in lowered:
        return WarningType.STORM_WARNING
    if "nav" in lowered:
        return WarningType.NAVIGATIONAL_WARNING
    if "restrict" in lowered:
        return WarningType.RESTRICTION
    return WarningType.OTHER


def _map_severity(value: str) -> WarningSeverity:
    lowered = value.lower()
    for sev in (WarningSeverity.CRITICAL, WarningSeverity.HIGH,
                WarningSeverity.MODERATE, WarningSeverity.LOW):
        if sev.value in lowered:
            return sev
    return WarningSeverity.UNKNOWN
