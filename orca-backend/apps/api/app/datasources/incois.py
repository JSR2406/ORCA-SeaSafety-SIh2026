# INCOIS adapter - Indian National Centre for Ocean Information Services.
#
# Uses real open-source data channels:
#   - ERDDAP tabledap (erddap.incois.gov.in) for ocean conditions (SST,
#     currents, waves, chlorophyll)
#   - PFZ text page scraping (incois.gov.in/MarineFisheries) for fishing zone
#     advisories
#   - RSMC page scraping for marine warnings
#   - INCOIS LAS (las.incois.gov.in) as fallback for grid data
#
# ERDDAP is a publicly available, standards-based (OPeNDAP/ERDDAP) data
# server.  No API key is required for read access.
#
# PFZ advisories are published daily for 14 coastal sectors.  The text
# pages are scraped because INCOIS does not expose a structured API for
# these advisories.
from datetime import datetime, timedelta
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
    take_coordinates,
    take_numeric,
    take_string,
)
from app.datasources.scrapers import (
    ERDDAP_BASE,
    ERDDAP_DATASETS,
    PFZ_SECTORS,
    _parse_erddap_csv,
    scrape_incois_pfz,
    scrape_incois_warnings,
)
from app.models.common import QualityStatus, utcnow
from app.models.ocean import OceanConditions
from app.models.pfz import PFZZone
from app.models.source import SourceCapability, SourceType
from app.models.tides import TidePrediction, TideType
from app.models.warnings import MarineWarning, WarningSeverity, WarningType

logger = logging.getLogger(__name__)


class INCOISAdapter(BaseMarineDataSource):
    name = "incois"
    display_name = "Indian National Centre for Ocean Information Services"
    source_type = SourceType.INCOIS

    # ERDDAP endpoints (replaces placeholder /api/ocean/conditions).
    PRODUCT_ENDPOINTS: Dict[str, str] = {
        "ocean": "/erddap",
        "tides": "/erddap",
        "pfz": "/scrape",
        "warnings": "/scrape",
    }

    def __init__(self, settings: Settings, transport: Optional[HttpDataTransport] = None):
        super().__init__(settings, transport)

    @property
    def base_url(self) -> str:
        return self.settings.incois_base_url

    @property
    def api_key(self) -> Optional[str]:
        return self.settings.incois_api_key or None

    @property
    def enabled(self) -> bool:
        return self.settings.incois_enabled

    @property
    def capabilities(self) -> List[SourceCapability]:
        return [
            SourceCapability(
                name="ocean_conditions",
                description="Ocean conditions via ERDDAP (SST, currents, waves, chlorophyll)",
                data_product="ocean",
                config_required=True,
            ),
            SourceCapability(
                name="tide_predictions",
                description="Tide predictions via ERDDAP or LAS",
                data_product="tides",
                config_required=True,
            ),
            SourceCapability(
                name="pfz_advisories",
                description="Potential Fishing Zone advisories (scraped from INCOIS)",
                data_product="pfz",
                config_required=True,
            ),
            SourceCapability(
                name="marine_warnings",
                description="Marine/cyclone warnings (scraped from INCOIS RSMC)",
                data_product="warnings",
                config_required=True,
            ),
        ]

    # ------------------------------------------------------------------ ocean
    async def fetch_ocean(
        self, *, lat: float, lon: float, time=None, **kw
    ) -> List[OceanConditions]:
        self._ensure_configured("ocean")

        # Query ERDDAP for ocean variables at this point.
        from app.datasources.scrapers import fetch_erddap_ocean

        t = time or utcnow()

        rows = await fetch_erddap_ocean(
            lat, lon,
            time_start=t - timedelta(hours=6),
            time_end=t,
            variables=None,
        )

        results: List[OceanConditions] = []
        for row in rows[:1]:
            try:
                r_lat = row.get("latitude", lat)
                r_lon = row.get("longitude", lon)
                if r_lat is None or r_lon is None:
                    r_lat, r_lon = lat, lon

                time_obs = parse_datetime(row.get("time"))
                if not time_obs:
                    time_obs = t
                stale = ((t - time_obs).total_seconds() > 24 * 3600) if time_obs else True
                quality = QualityStatus.STALE if stale else QualityStatus.VALID

                sst = row.get("sst_c")
                if sst is None:
                    sst = row.get("water_temp_c")

                results.append(OceanConditions(
                    latitude=float(r_lat),
                    longitude=float(r_lon),
                    observation_time=time_obs,
                    source_timestamp=utcnow(),
                    sst_c=sst,
                    chlorophyll=row.get("chlorophylla") or row.get("chlorophyll"),
                    wave_height_m=None,
                    wave_period_s=None,
                    wave_direction_deg=None,
                    current_speed_ms=row.get("current_speed_ms"),
                    current_direction_deg=row.get("current_direction_deg"),
                    salinity_psu=row.get("salinity_psu"),
                    source=self.name,
                    source_record_id=f"erddap-{lat:.2f}-{lon:.2f}-{time_obs:%Y%m%dT%H%M%S}",
                    quality=quality,
                    raw_payload=row,
                ))
            except Exception as exc:
                logger.debug("incois_ocean_parse_skip", error=str(exc))
                continue

        # Fallback: try LAS grid data if ERDDAP returned nothing.
        if not results:
            las_data = await self._fetch_ocean_from_las(lat, lon, t)
            results.extend(las_data)

        # Enrich best-effort with live wave conditions from Open-Meteo.
        # (INCOIS ERDDAP grid datasets are index-encoded and cannot serve
        # point queries for waves/currents.)
        if results:
            from app.datasources.scrapers import fetch_open_meteo_marine

            wave = await fetch_open_meteo_marine(lat, lon)
            if wave:
                base = results[0]
                payload = dict(base.raw_payload or {})
                payload["waves_provider"] = "open-meteo"
                payload["waves"] = wave
                results[0] = base.model_copy(
                    update={
                        "wave_height_m": wave.get("wave_height_m"),
                        "wave_period_s": wave.get("wave_period_s"),
                        "wave_direction_deg": wave.get("wave_direction_deg"),
                        "raw_payload": payload,
                    }
                )
        elif not results:
            # Even without ARGO/LAS, waves alone give a valid ocean bucket.
            from app.datasources.scrapers import fetch_open_meteo_marine

            wave = await fetch_open_meteo_marine(lat, lon)
            if wave:
                wave_time = parse_datetime(wave.get("observation_time")) or t
                results.append(OceanConditions(
                    latitude=lat,
                    longitude=lon,
                    observation_time=wave_time,
                    source_timestamp=utcnow(),
                    wave_height_m=wave.get("wave_height_m"),
                    wave_period_s=wave.get("wave_period_s"),
                    wave_direction_deg=wave.get("wave_direction_deg"),
                    source=self.name,
                    source_record_id=f"openmeteo-{lat:.2f}-{lon:.2f}",
                    quality=QualityStatus.VALID,
                    raw_payload={"waves_provider": "open-meteo", "waves": wave},
                ))

        return results

    async def _fetch_ocean_from_las(
        self, lat: float, lon: float, time: datetime
    ) -> List[OceanConditions]:
        """Fallback: query INCOIS Live Access Server for grid data."""
        las_base = "https://las.incois.gov.in/LAS"

        # LAS data endpoint with point query.
        params = {
            "var": "sst",
            "dsid": "sst_l3m",
            "trange": f"({time.isoformat()},{time.isoformat()})",
            "xname": "longitude",
            "yname": "latitude",
            "xml": "no",
        }
        try:
            resp = await self.transport.get_json(
                f"{las_base}/data",
                params=params,
            )
        except Exception:
            return []

        if not resp:
            return []

        # LAS returns various formats; try to extract values.
        sst = None
        if isinstance(resp, dict):
            sst = take_numeric(resp, "sst", "value", "data")
        elif isinstance(resp, list) and resp:
            sst = take_numeric(resp[0], "sst", "value") if isinstance(resp[0], dict) else None

        if sst is None:
            return []

        return [OceanConditions(
            latitude=lat,
            longitude=lon,
            observation_time=time,
            source_timestamp=utcnow(),
            sst_c=sst,
            chlorophyll=None,
            wave_height_m=None,
            wave_period_s=None,
            wave_direction_deg=None,
            current_speed_ms=None,
            current_direction_deg=None,
            salinity_psu=None,
            source=self.name,
            source_record_id=f"las-{lat:.2f}-{lon:.2f}",
            quality=QualityStatus.VALID,
            raw_payload={"las_response": resp},
        )]

    # ------------------------------------------------------------------ tides
    async def fetch_tides(
        self, *, lat: float, lon: float, start=None, end=None, **kw
    ) -> List[TidePrediction]:
        self._ensure_configured("tides")

        # ERDDAP tide prediction datasets.
        from app.datasources.scrapers import fetch_erddap_ocean

        t_start = start or utcnow()
        t_end = end or (t_start + timedelta(hours=24))

        rows = await fetch_erddap_ocean(
            lat, lon,
            time_start=t_start,
            time_end=t_end,
            variables=["tide_height", "tide_type"],
        )

        results: List[TidePrediction] = []
        for row in rows:
            height = row.get("tide_height")
            tide_type_str = row.get("tide_type", "high")
            try:
                tide_type = TideType.HIGH if str(tide_type_str).lower() in ("high", "h") else TideType.LOW
            except Exception:
                tide_type = TideType.HIGH

            results.append(TidePrediction(
                location_name=f"ERDDAP ({lat:.2f}, {lon:.2f})",
                latitude=float(row.get("latitude", lat)),
                longitude=float(row.get("longitude", lon)),
                event_time=parse_datetime(row.get("time")) or utcnow(),
                tide_height_m=height,
                tide_type=tide_type,
                is_prediction=True,
                source_timestamp=utcnow(),
                source=self.name,
                source_record_id=f"tide-erddap-{lat:.2f}-{lon:.2f}",
                quality=QualityStatus.VALID,
                raw_payload=row,
            ))

        return results

    # --------------------------------------------------------------------- pfz
    async def fetch_pfz(
        self, *, lat: float = None, lon: float = None, date=None, **kw
    ) -> List[PFZZone]:
        self._ensure_configured("pfz")

        # Determine sector from lat/lon.
        sector = self._lat_lon_to_sector(lat, lon)

        # Scrape PFZ text page for the sector.
        raw_pfz = await scrape_incois_pfz(sector)

        results: List[PFZZone] = []
        for item in raw_pfz:
            try:
                p_lat = item.get("lat")
                p_lon = item.get("lon")
                if p_lat is None or p_lon is None:
                    continue

                # Build a small polygon around the PFZ point.
                delta = 0.25  # ~25km box
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
                    confidence=0.6,  # Scraped data, moderate confidence
                    metadata={
                        "sector": sector,
                        "raw_text": item.get("raw_text", ""),
                    },
                    source=self.name,
                    source_record_id=f"pfz-{sector}-{p_lat:.2f}-{p_lon:.2f}",
                    quality=QualityStatus.VALID,
                    raw_payload=item,
                ))
            except Exception as exc:
                logger.debug("incois_pfz_parse_skip", error=str(exc))
                continue

        # Fallback: the INCOIS PFZ text page is JS-rendered and needs a
        # headless browser, which is not a dependency.  When the scrape is
        # empty, derive likely fishing fronts from real satellite SST
        # (NOAA CoastWatch MUR).  These are flagged 'estimated' in metadata
        # and must never be presented as an official INCOIS advisory.
        if not results and lat is not None and lon is not None:
            derived = await self._derive_pfz_from_sst_fronts(lat, lon, sector)
            results.extend(derived)

        return results

    async def _derive_pfz_from_sst_fronts(
        self, lat: float, lon: float, sector: str
    ) -> List[PFZZone]:
        """Derive likely fishing-zone locations from satellite SST fronts.

        Uses real near-real-time MUR SST sampled on a small grid around the
        point; cells where the SST differs strongly from neighbours are the
        thermal fronts used to flag productive water.  This is estimated
        (not the official INCOIS advisory) and marked accordingly.
        """
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
                    source_record_id=f"pfz-derived-{p_lat:.2f}-{p_lon:.2f}",
                    quality=QualityStatus.VALID,
                    raw_payload=front,
                ))
            except Exception as exc:
                logger.debug("incois_pfz_derive_skip", error=str(exc))
                continue
        return results

    def _lat_lon_to_sector(self, lat: float, lon: float) -> str:
        """Map lat/lon to nearest INCOIS PFZ sector."""
        if lat is None or lon is None:
            return "KERALA"

        sector_centers = {
            "GUJARAT": (22.0, 70.0),
            "MAHARASHTRA": (17.0, 73.0),
            "GOA": (15.4, 73.8),
            "KARNATAKA": (13.5, 74.5),
            "KERALA": (10.0, 76.3),
            "SOUTH_TAMILNADU": (8.5, 78.0),
            "NORTH_TAMILNADU": (12.5, 80.0),
            "SOUTH_ANDHRA_PRADESH": (14.5, 80.0),
            "NORTH_ANDHRA_PRADESH": (17.0, 82.5),
            "ODISHA": (19.0, 86.0),
            "WEST_BENGAL": (21.0, 88.0),
            "ANDAMAN": (11.5, 92.5),
            "NICOBAR": (7.5, 93.5),
            "LAKSHADWEEP": (10.5, 72.5),
        }

        best_sector = "KERALA"
        best_dist = float("inf")
        for sector, (s_lat, s_lon) in sector_centers.items():
            dist = abs(lat - s_lat) + abs(lon - s_lon)
            if dist < best_dist:
                best_dist = dist
                best_sector = sector
        return best_sector

    # --------------------------------------------------------------- warnings
    async def fetch_warnings(
        self, *, lat: float = None, lon: float = None, **kw
    ) -> List[MarineWarning]:
        self._ensure_configured("warnings")

        # Scrape INCOIS RSMC warnings page.
        raw_warnings = await scrape_incois_warnings()

        results: List[MarineWarning] = []
        for item in raw_warnings:
            try:
                w_type_str = item.get("warning_type", "other")
                warning_type = _map_warning_type(w_type_str)

                sev_str = item.get("severity", "unknown")
                severity = _map_severity(sev_str)

                results.append(MarineWarning(
                    warning_id=item.get("warning_id", f"incois-warn-{hash(str(item)) & 0xFFFFFF:06x}"),
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
            except Exception as exc:
                logger.debug("incois_warn_parse_skip", error=str(exc))
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
    for severity in (WarningSeverity.CRITICAL, WarningSeverity.HIGH,
                     WarningSeverity.MODERATE, WarningSeverity.LOW):
        if severity.value in lowered:
            return severity
    return WarningSeverity.UNKNOWN
