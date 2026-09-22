# Scraping utilities for open-source Indian marine data providers.
#
# These scrapers consume publicly available government data portals:
#   - IMD marine APIs (api.imd.gov.in) — JSON, no auth required
#   - INCOIS ERDDAP (erddap.incois.gov.in) — tabular ocean data
#   - INCOIS PFZ text pages (incois.gov.in/MarineFisheries) — HTML scrape
#   - INCOIS RSMC warnings — HTML scrape
#   - NHO NAVAREA VIII warnings (hydrobharat.gov.in) — HTML scrape
#   - MOSDAC satellite products (mosdac.gov.in) — OGC WMS/WFS
#
# All scrapers return raw parsed data; normalization into canonical models
# happens in the adapter layer.  Every scraper is defensive: on failure it
# returns empty results (never raises) so the pipeline degrades gracefully.
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)

_DEFAULT_TIMEOUT = 30.0
_USER_AGENT = (
    "Mozilla/5.0 (compatible; FloatChatBot/1.0; "
    "+https://github.com/floatchat)"
)


def _retry_verify(exc: Exception) -> bool:
    """Retry without TLS verification only on transport/certificate errors."""
    return isinstance(exc, httpx.TransportError)


async def _get(url: str, *, params: dict = None, timeout: float = _DEFAULT_TIMEOUT,
               headers: dict = None) -> Optional[str]:
    """Fetch URL text; returns None on any error.

    Retries once with TLS verification disabled because some government
    endpoints (e.g. INCOIS) use certificate chains missing from the local
    CA store, which makes httpx fail with CERTIFICATE_VERIFY_FAILED.

    `headers` (optional) replaces the default User-Agent; used when a provider
    (e.g. JTWC) 403s bot UAs but serves a real browser UA.
    """
    default_headers = {"User-Agent": _USER_AGENT}
    headers = {**default_headers, **(headers or {})}
    for verify in (True, False):
        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True,
                headers=headers,
                verify=verify,
            ) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.text
        except Exception as exc:
            logger.warning("scraper_fetch_failed", url=url, error=str(exc))
            if not (verify and _retry_verify(exc)):
                break
    return None


async def _get_json(url: str, *, params: dict = None, timeout: float = _DEFAULT_TIMEOUT,
                    headers: dict = None) -> Optional[dict]:
    """Fetch URL as JSON; returns None on any error."""
    default_headers = {"User-Agent": _USER_AGENT}
    headers = {**default_headers, **(headers or {})}
    for verify in (True, False):
        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True,
                headers=headers,
                verify=verify,
            ) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.warning("scraper_json_failed", url=url, error=str(exc))
            if not (verify and _retry_verify(exc)):
                break
    return None


async def _get_bytes(url: str, *, timeout: float = _DEFAULT_TIMEOUT) -> Optional[bytes]:
    """Fetch URL as raw bytes (e.g. PDF); returns None on any error."""
    for verify in (True, False):
        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
                verify=verify,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
        except Exception as exc:
            logger.warning("scraper_bytes_failed", url=url, error=str(exc))
            if not (verify and _retry_verify(exc)):
                break
    return None


# ---------------------------------------------------------------------------
# IMD Marine API scrapers
# ---------------------------------------------------------------------------

async def fetch_imd_sea_bulletin(area_id: str = "") -> List[Dict[str, Any]]:
    """Fetch IMD Sea Area Bulletin (wind, weather, sea state for sea areas)."""
    url = "https://api.imd.gov.in/api/v1/seabulletin"
    params = {"id": area_id} if area_id else {}
    data = await _get_json(url, params=params)
    if not data:
        return []
    if isinstance(data, list):
        return data
    return [data]


async def fetch_imd_coastal_bulletin() -> List[Dict[str, Any]]:
    """Fetch IMD Coastal Bulletin (coastal weather forecast)."""
    url = "https://api.imd.gov.in/api/v1/coastalbulletin"
    data = await _get_json(url)
    if not data:
        return []
    if isinstance(data, list):
        return data
    return [data]


async def fetch_imd_cyclone_track() -> Dict[str, Any]:
    """Fetch IMD Cyclone Track data."""
    url = "https://api.imd.gov.in/api/v1/cyclone_track"
    data = await _get_json(url)
    return data or {}


async def fetch_imd_cyclone_wind() -> Dict[str, Any]:
    """Fetch IMD Cyclone Wind Warning (GeoJSON wind polygons)."""
    url = "https://api.imd.gov.in/api/v1/cyclone_wind"
    data = await _get_json(url)
    return data or {}


async def fetch_imd_port_warning(port_id: str = "") -> List[Dict[str, Any]]:
    """Fetch IMD Port Warning."""
    url = "https://api.imd.gov.in/api/v1/portwarning"
    params = {"id": port_id} if port_id else {}
    data = await _get_json(url, params=params)
    if not data:
        return []
    if isinstance(data, list):
        return data
    return [data]


# ---------------------------------------------------------------------------
# INCOIS ERDDAP scraper
# ---------------------------------------------------------------------------

# Real dataset IDs verified against the live catalog:
# https://erddap.incois.gov.in/erddap/info/index.html
# NOTE: this server runs the ERDDAP 2.18+ URL scheme where griddap
# constraints are given in the query string as  var[(last)][lat][lon].
ERDDAP_BASE = "https://erddap.incois.gov.in/erddap"

ERDDAP_DATASETS = {
    "sst": "NOAA_AVHRR_AMSR_datasets",        # gridded SST (indexed axes)
    "chlorophyll": "IRS_chlorophyll_datasets",
    "wind": "ascat_daily_datasets",
    "current": "incois_valueadded_products_datasets",
    "argo": "Indian_ARGO_Floats",
}

async def _query_argo_near(
    lat: float, lon: float, max_rows: int = 40
) -> Optional[Dict[str, Any]]:
    """Pull the most recent shallow ARGO float profile near a point."""
    url = (
        f"{ERDDAP_BASE}/tabledap/Indian_ARGO_Floats.csv?"
        f"time,latitude,longitude,PRES,TEMP,PSAL"
        f"&latitude>={lat - 1.0}&latitude<={lat + 1.0}"
        f"&longitude>={lon - 1.0}&longitude<={lon + 1.0}"
    )
    text = await _get(url, timeout=25.0)
    if not text:
        return None
    rows = _parse_erddap_csv(text)
    if not rows:
        return None
    rows.sort(key=lambda r: r.get("time") or "", reverse=True)
    recent = rows[0]
    shallow = rows[0]
    for r in rows[:max_rows]:
        try:
            if float(shallow.get("PRES") or 9999) > float(r.get("PRES") or 9999):
                shallow = r
        except (ValueError, TypeError):
            continue
    try:
        return {
            "sst_c": float(recent["TEMP"]),
            "salinity_psu": float(recent["PSAL"]),
            "time": recent.get("time"),
            "latitude": recent.get("latitude"),
            "longitude": recent.get("longitude"),
            "pressure_dbar": float(shallow.get("PRES") or 0),
            "water_temp_c": float(shallow["TEMP"]),
            "quality": "stale",
        }
    except (KeyError, ValueError, TypeError):
        return None


async def fetch_erddap_ocean(
    lat: float, lon: float,
    time_start: Optional[datetime] = None,
    time_end: Optional[datetime] = None,
    variables: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Fetch ocean conditions at a point from INCOIS ERDDAP.

    The INCOIS ERDDAP grid datasets use index-encoded lat/lon axes, so point
    queries are only possible against the ARGO floats tabledap dataset.
    Returns a list with at most one merged row dict from the most recent
    shallow ARGO profile near the point (real in-situ temperature/salinity).

    Returns [] when no ARGO float is near the point.
    """
    now = datetime.now(timezone.utc)
    try:
        argo = await _query_argo_near(lat, lon)
    except Exception:
        argo = None
    if not argo:
        return []

    row: Dict[str, Any] = {
        "sst_c": argo.get("sst_c"),
        "salinity_psu": argo.get("salinity_psu"),
        "time": argo.get("time"),
        "latitude": argo.get("latitude", lat),
        "longitude": argo.get("longitude", lon),
        "argo_pressure_dbar": argo.get("pressure_dbar"),
        "quality": "stale",
    }

    ts = row.get("time")
    if ts:
        try:
            dt_ts = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if dt_ts.tzinfo is None:
                dt_ts = dt_ts.replace(tzinfo=timezone.utc)
            if (now - dt_ts) <= timedelta(days=1):
                row["quality"] = "valid"
        except ValueError:
            pass

    if variables:
        row = {k: v for k, v in row.items() if k in variables or k in ("time", "quality")}

    return [row]


def _is_units_row(header: List[str], values: List[str]) -> bool:
    """ERDDAP CSV row 2 holds units only for time/other columns.

    A units row is one where no cell parses as a number (except the optional
    'UTC' time unit), which distinguishes it from a data row.
    """
    if len(values) != len(header):
        return False
    if not values:
        return True
    for cell in values:
        c = cell.strip()
        if not c or c.lower() in ("nan", "inf", "-inf", "utc", "z", ""):
            continue
        try:
            float(c)
            return False
        except ValueError:
            continue
    return True


def _parse_erddap_csv(text: str) -> List[Dict[str, Any]]:
    """Parse ERDDAP CSV response (header + optional units row + data rows)."""
    lines = [ln for ln in text.strip().split("\n") if ln.strip()]
    if len(lines) < 2:
        return []
    header = [h.strip() for h in lines[0].split(",")]
    start = 1
    if len(lines) > 1 and _is_units_row(header, [c.strip() for c in lines[1].split(",")]):
        start = 2
    rows = []
    for line in lines[start:]:
        values = [v.strip() for v in line.split(",")]
        if len(values) != len(header):
            continue
        row = {}
        for h, v in zip(header, values):
            if h in ("latitude", "longitude"):
                try:
                    row[h] = float(v)
                except (ValueError, TypeError):
                    row[h] = None
            elif h == "time":
                row[h] = v
            else:
                try:
                    row[h] = float(v)
                except (ValueError, TypeError):
                    row[h] = v
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# INCOIS PFZ scraper
# ---------------------------------------------------------------------------

# Sector IDs for INCOIS PFZ text page (mfid parameter)
PFZ_SECTORS = {
    "GUJARAT": 1,
    "MAHARASHTRA": 2,
    "GOA": 3,
    "KARNATAKA": 4,
    "KERALA": 5,
    "SOUTH_TAMILNADU": 6,
    "NORTH_TAMILNADU": 7,
    "SOUTH_ANDHRA_PRADESH": 8,
    "NORTH_ANDHRA_PRADESH": 9,
    "ODISHA": 10,
    "WEST_BENGAL": 11,
    "ANDAMAN": 12,
    "NICOBAR": 13,
    "LAKSHADWEEP": 14,
}


async def scrape_incois_pfz(sector_name: str = "KERALA") -> List[Dict[str, Any]]:
    """Scrape PFZ advisory text from INCOIS Marine Fisheries page.

    Returns list of dicts with keys: lat, lon, sector, species, depth,
    distance_from, direction_from, valid_from, valid_until, raw_text.
    """
    mfid = PFZ_SECTORS.get(sector_name.upper(), PFZ_SECTORS["KERALA"])
    url = "https://incois.gov.in/MarineFisheries/TextDataHome"
    params = {"mfid": str(mfid), "request_locale": "en"}
    html = await _get(url, params=params, timeout=15.0)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []

    # PFZ text data is typically in table rows or structured divs.
    # Try table-based extraction first.
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            text = " ".join(c.get_text(strip=True) for c in cells)
            parsed = _parse_pfz_text_line(text, sector_name)
            if parsed:
                results.append(parsed)

    # Also try div-based extraction for newer layouts.
    for div in soup.find_all("div", class_=re.compile(r"pfz|advisory|data", re.I)):
        text = div.get_text(separator=" ", strip=True)
        parsed = _parse_pfz_text_line(text, sector_name)
        if parsed and parsed not in results:
            results.append(parsed)

    # Fallback: scan all text nodes for lat/lon patterns.
    if not results:
        body_text = soup.get_text(separator="\n")
        for match in re.finditer(
            r"(\d{1,2}[.\d]*)\s*[°]?\s*N.*?(\d{1,3}[.\d]*)\s*[°]?\s*E",
            body_text,
        ):
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
                if 0 <= lat <= 35 and 60 <= lon <= 100:
                    results.append({
                        "lat": lat, "lon": lon, "sector": sector_name,
                        "species": None, "depth": None,
                        "distance_from": None, "direction_from": None,
                        "valid_from": None, "valid_until": None,
                        "raw_text": match.group(0),
                    })
            except (ValueError, IndexError):
                continue

    return results


def _parse_pfz_text_line(text: str, sector: str) -> Optional[Dict[str, Any]]:
    """Try to extract PFZ lat/lon from a text line."""
    # Pattern: lat/lon coordinates anywhere in the text.
    match = re.search(
        r"(\d{1,2}[.\d]*)\s*[°]?\s*N.*?(\d{1,3}[.\d]*)\s*[°]?\s*E",
        text,
    )
    if not match:
        return None
    try:
        lat = float(match.group(1))
        lon = float(match.group(2))
    except ValueError:
        return None
    if not (0 <= lat <= 35 and 60 <= lon <= 100):
        return None

    # Try to extract species.
    species = None
    sp_match = re.search(r"(?:species|fish)[:\s]+([\w\s,]+)", text, re.I)
    if sp_match:
        species = sp_match.group(1).strip()

    return {
        "lat": lat, "lon": lon, "sector": sector,
        "species": species, "depth": None,
        "distance_from": None, "direction_from": None,
        "valid_from": None, "valid_until": None,
        "raw_text": text[:500],
    }


# ---------------------------------------------------------------------------
# INCOIS RSMC / warnings scraper
# ---------------------------------------------------------------------------

async def scrape_incois_warnings() -> List[Dict[str, Any]]:
    """Scrape marine warnings from INCOIS RSMC page.

    Returns list of dicts with keys: warning_id, warning_type, severity,
    description, valid_from, valid_until, geometry (GeoJSON or None).
    """
    url = "https://incois.gov.in/oceanservices/rsmc.jsp"
    html = await _get(url, timeout=15.0)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []

    # Look for warning/advisory entries in the page.
    for tag in soup.find_all(["div", "tr", "li", "p"]):
        text = tag.get_text(separator=" ", strip=True)
        if not text or len(text) < 20:
            continue
        # Match warning-like text: cyclone, storm, fishing, warning, advisory.
        if re.search(r"(cyclone|storm|warning|advisory|fishing|gale|squall)", text, re.I):
            results.append({
                "warning_id": f"incois-{hash(text) & 0xFFFFFF:06x}",
                "warning_type": _classify_warning_type(text),
                "severity": _classify_severity(text),
                "description": text[:500],
                "valid_from": None,
                "valid_until": None,
                "geometry": None,
            })

    return results[:50]  # Bound output


# ---------------------------------------------------------------------------
# NHO NAVAREA VIII scraper
# ---------------------------------------------------------------------------

async def scrape_nho_navarea_warnings() -> List[Dict[str, Any]]:
    """Scrape NAVAREA VIII in-force warnings from NHO website.

    The NHO publishes in-force NAVAREA VIII warnings as a PDF document.
    We discover the document link from the warnings page, download the
    PDF, extract its text and parse individual warnings.

    Returns list of dicts with keys: warning_id, warning_type, severity,
    description, geometry (GeoJSON or None), valid_from, valid_until.
    """
    page_url = "https://hydrobharat.gov.in/navarea-warnings"
    html = await _get(page_url, timeout=20.0)
    if not html:
        return []

    # Discover the in-force warnings document (Liferay document link).
    doc_url = None
    soup = BeautifulSoup(html, "lxml")
    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")
        text = a_tag.get_text(" ", strip=True)
        if re.search(r"in[- ]force|navarea", text + " " + href, re.I):
            candidate = href if href.startswith("http") else (
                "https://hydrobharat.gov.in" + href if href.startswith("/") else href)
            if "documents/d/" in candidate or candidate.endswith(".pdf"):
                doc_url = candidate
                break

    if not doc_url:
        return []

    pdf_bytes = await _get_bytes(doc_url, timeout=30.0)
    if not pdf_bytes:
        return []

    text = _extract_pdf_text(pdf_bytes)
    if not text:
        return []

    warnings = _parse_navarea_pdf_text(text)
    for w in warnings:
        w["source_url"] = doc_url
    return warnings


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract all text from a PDF byte payload."""
    try:
        from io import BytesIO
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")
        return "\n".join(pages)
    except Exception as exc:
        logger.warning("scraper_pdf_extract_failed", error=str(exc))
        return ""


def _parse_navarea_pdf_text(text: str) -> List[Dict[str, Any]]:
    """Parse NAVAREA VIII warnings out of extracted PDF text.

    Each warning block looks like:
        171006Z/FEB 23
        NAVAREA VIII -161/23
        <separator>
        <warning body, possibly multi-line>
        <separator or next timestamp>
    """
    pattern = re.compile(
        r"(?P<time>\d{6}Z/[A-Z]{3} \d{2})\s*\n\s*NAVAREA VIII\s*[-–]\s*(?P<num>\d+/\d+)",
        re.IGNORECASE,
    )
    positions = [m.start() for m in pattern.finditer(text)]
    if not positions:
        return []

    results = []
    headers = list(pattern.finditer(text))
    for i, header in enumerate(headers):
        warning_id = f"NAVAREA-VIII-{header.group('num')}"
        start = header.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[start:end].strip()
        # Normalize multiple separator lines / dashes.
        body = re.sub(r"-{5,}", "", body).strip()
        body = re.sub(r"\s+", " ", body).strip()
        if not body:
            continue
        results.append({
            "warning_id": warning_id,
            "warning_type": _classify_navarea_type(body),
            "severity": _classify_navarea_severity(body),
            "description": body[:500],
            "valid_from": None,
            "valid_until": None,
            "geometry": _extract_navarea_geometry(body),
            "issued_at": header.group("time"),
        })

    # If extraction is noisy, fall back to broad search over the raw text.
    if len(results) < 3:
        for m in re.finditer(r"NAVAREA\s*VIII\s*[-–]\s*(\d+/\d+)", text, re.I):
            if not any(r["warning_id"].endswith(m.group(1)) for r in results):
                start = m.end()
                body = text[start:start + 500].strip()
                body = re.sub(r"-{5,}", "", body).strip()
                body = re.sub(r"\s+", " ", body)[:500]
                results.append({
                    "warning_id": f"NAVAREA-VIII-{m.group(1)}",
                    "warning_type": _classify_navarea_type(body),
                    "severity": _classify_navarea_severity(body),
                    "description": body,
                    "valid_from": None,
                    "valid_until": None,
                    "geometry": _extract_navarea_geometry(body),
                })

    # Deduplicate by warning_id.
    seen = set()
    deduped = []
    for r in results:
        if r["warning_id"] not in seen:
            seen.add(r["warning_id"])
            deduped.append(r)

    return deduped[:100]  # Bound output


async def scrape_nho_notices_to_mariners() -> List[Dict[str, Any]]:
    """Scrape Indian Notices to Mariners from NHO."""
    url = "https://hydrobharat.gov.in/"
    html = await _get(url, timeout=15.0)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []

    for a_tag in soup.find_all("a", href=True):
        text = a_tag.get_text(strip=True)
        href = a_tag["href"]
        if re.search(r"notice|mariner|notam", text, re.I):
            results.append({
                "notice_id": f"NTM-{hash(text) & 0xFFFFFF:06x}",
                "title": text[:200],
                "url": href,
                "source": "nho",
            })

    return results[:50]


# ---------------------------------------------------------------------------
# MOSDAC satellite product scraper
# ---------------------------------------------------------------------------

async def fetch_mosdac_wms(
    lat: float, lon: float,
    layers: Optional[List[str]] = None,
    width: int = 256, height: int = 256,
) -> Optional[Dict[str, Any]]:
    """Fetch MOSDAC WMS GetFeatureInfo for SST/chlorophyll at a point.

    Uses OGC WMS 1.1.1 GetFeatureInfo to get pixel values at lat/lon.
    """
    if layers is None:
        layers = ["sst", "chlorophyll"]

    # Calculate approximate BBOX for the point (small window).
    delta = 0.5
    bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"

    url = "https://mosdac.gov.in/geoserver/wms"
    results = {}

    for layer in layers:
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.1.1",
            "REQUEST": "GetFeatureInfo",
            "LAYERS": layer,
            "QUERY_LAYERS": layer,
            "SRS": "EPSG:4326",
            "BBOX": bbox,
            "WIDTH": str(width),
            "HEIGHT": str(height),
            "X": str(width // 2),
            "Y": str(height // 2),
            "INFO_FORMAT": "application/json",
            "FEATURE_COUNT": "1",
        }
        data = await _get_json(url, params=params, timeout=15.0)
        if data and "features" in data and data["features"]:
            props = data["features"][0].get("properties", {})
            results[layer] = props

    return results if results else None


async def fetch_mosdac_catalog_search(query: str = "") -> List[Dict[str, Any]]:
    """Search MOSDAC dataset catalog."""
    url = "https://mosdac.gov.in/catalog-app/satellite.php"
    html = await _get(url, timeout=15.0)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []

    for tag in soup.find_all(["tr", "div"], class_=re.compile(r"dataset|product", re.I)):
        text = tag.get_text(separator=" ", strip=True)
        if query and query.lower() not in text.lower():
            continue
        results.append({"name": text[:200], "source": "mosdac"})

    return results[:30]


# ---------------------------------------------------------------------------
# Open-Meteo marine + forecast (keyless open API)
# ---------------------------------------------------------------------------

OPEN_METEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


async def fetch_open_meteo_marine(
    lat: float, lon: float,
) -> Optional[Dict[str, Any]]:
    """Fetch live wave conditions from Open-Meteo Marine API.

    Returns dict with keys: wave_height_m, wave_period_s, wave_direction_deg,
    observation_time (ISO string).
    """
    params = {
        "latitude": str(lat),
        "longitude": str(lon),
        "current": ",".join([
            "wave_height", "wave_period", "wave_direction",
        ]),
        "timezone": "UTC",
    }
    data = await _get_json(OPEN_METEO_MARINE_URL, params=params, timeout=20.0)
    if not data:
        return None
    current = data.get("current") or {}
    try:
        return {
            "wave_height_m": float(current["wave_height"]),
            "wave_period_s": float(current["wave_period"]),
            "wave_direction_deg": float(current["wave_direction"]),
            "observation_time": current.get("time"),
            "latitude": data.get("latitude", lat),
            "longitude": data.get("longitude", lon),
        }
    except (KeyError, ValueError, TypeError):
        return None


async def fetch_open_meteo_forecast(
    lat: float, lon: float,
) -> Optional[Dict[str, Any]]:
    """Fetch live weather from Open-Meteo forecast API.

    Returns dict with keys: temperature_c, humidity_pct, precipitation_mm,
    pressure_hpa, wind_speed_ms, wind_direction_deg, observation_time,
    hourly (list of hourly forecast dicts).
    Wind is km/h from the API; converted to m/s.
    """
    params = {
        "latitude": str(lat),
        "longitude": str(lon),
        "current": ",".join([
            "temperature_2m", "relative_humidity_2m", "apparent_temperature",
            "precipitation", "pressure_msl", "wind_speed_10m",
            "wind_direction_10m", "weather_code",
        ]),
        "hourly": ",".join([
            "temperature_2m", "precipitation_probability",
        ]),
        "forecast_days": "1",
        "timezone": "UTC",
    }
    data = await _get_json(OPEN_METEO_FORECAST_URL, params=params, timeout=20.0)
    if not data:
        return None
    current = data.get("current") or {}
    try:
        speed_kmh = float(current["wind_speed_10m"])
        hourly = data.get("hourly") or {}
        return {
            "temperature_c": float(current["temperature_2m"]),
            "humidity_pct": float(current["relative_humidity_2m"]),
            "precipitation_mm": float(current.get("precipitation") or 0),
            "pressure_hpa": float(current.get("pressure_msl") or 0),
            "wind_speed_ms": round(speed_kmh / 3.6, 3),
            "wind_direction_deg": float(current.get("wind_direction_10m") or 0),
            "weather_code": current.get("weather_code"),
            "observation_time": current.get("time"),
            "latitude": data.get("latitude", lat),
            "longitude": data.get("longitude", lon),
            "hourly_forecast": [
                {"time": t, "temperature_c": temp, "precip_probability_pct": p}
                for t, temp, p in zip(
                    hourly.get("time", []),
                    hourly.get("temperature_2m", []),
                    hourly.get("precipitation_probability", []),
                )
            ],
        }
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("open_meteo_parse_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------------
# NOAA CoastWatch ERDDAP (keyless near-real-time satellite products)
# ---------------------------------------------------------------------------

COASTWATCH_BASE = "https://coastwatch.pfeg.noaa.gov/erddap"

# MUR SST (GHRSST) - near-real-time, 0.01 deg, real lat/lon axes.
JPL_MUR_SST_DATASET = "jplMURSST41"
# VIIRS chlorophyll (global 4km NRT) - often served from a restricted host,
# so callers degrade gracefully when it 403s.
VIIRS_CHL_DATASET = "nesdisVHNchlaDaily"


async def fetch_coastwatch_sst_point(
    lat: float, lon: float, dataset: str = JPL_MUR_SST_DATASET,
) -> Optional[Dict[str, Any]]:
    """Fetch a single near-real-time MUR SST value at (lat, lon).

    Returns dict with keys: sst_c, time, latitude, longitude, source.
    Returns None when the point is masked (e.g. over land/clouds) or the
    endpoint is unavailable.
    """
    url = (
        f"{COASTWATCH_BASE}/griddap/{dataset}.csv?"
        f"analysed_sst%5B(last)%5D%5B({lat})%5D%5B({lon})%5D"
    )
    text = await _get(url, timeout=25.0)
    if not text:
        return None
    rows = _parse_erddap_csv(text)
    if not rows:
        return None
    row = rows[0]
    sst = row.get("analysed_sst")
    if sst is None:
        return None
    try:
        sst_f = float(sst)
    except (ValueError, TypeError):
        return None
    if math.isnan(sst_f):
        return None
    return {
        "sst_c": sst_f,
        "time": row.get("time"),
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "source": "noaa_coastwatch",
        "dataset": dataset,
    }


async def fetch_coastwatch_chlorophyll_point(
    lat: float, lon: float, dataset: str = VIIRS_CHL_DATASET,
) -> Optional[Dict[str, Any]]:
    """Fetch a single VIIRS chlorophyll value at (lat, lon).

    The near-real-time VIIRS datasets on CoastWatch may be served from a
    restricted host (403); this returns None in that case so callers can
    fall back to other sources.
    Returns dict with keys: chlorophyll, time, latitude, longitude, source.
    """
    url = (
        f"{COASTWATCH_BASE}/griddap/{dataset}.csv?"
        f"chlor_a%5B(last)%5D%5B(0.0)%5D%5B({lat})%5D%5B({lon})%5D"
    )
    text = await _get(url, timeout=25.0)
    if not text:
        return None
    rows = _parse_erddap_csv(text)
    if not rows:
        return None
    row = rows[0]
    chl = row.get("chlor_a")
    if chl is None:
        return None
    try:
        chl_f = float(chl)
    except (ValueError, TypeError):
        return None
    if math.isnan(chl_f):
        return None
    return {
        "chlorophyll": chl_f,
        "time": row.get("time"),
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "source": "noaa_coastwatch",
        "dataset": dataset,
    }


async def fetch_coastwatch_sst_front_grid(
    lat: float, lon: float,
    radius_deg: float = 0.75,
    step_deg: float = 0.25,
    dataset: str = JPL_MUR_SST_DATASET,
) -> List[Dict[str, Any]]:
    """Sample MUR SST over a small grid to locate thermal fronts.

    PFZ advisories in the Indian region are drawn from chlorophyll/SST
    fronts.  When INCOIS's JS-rendered PFZ page is unreachable, this grid
    of real satellite SST lets us derive likely fronts (still flagged in
    metadata as derived/estimated, never presented as official risk).

    Returns list of dicts with keys: latitude, longitude, sst_c, time.
    Cells that are NaN (masked) are dropped.
    """
    points = []
    la = lat - radius_deg
    while la <= lat + radius_deg + 1e-9:
        lo = lon - radius_deg
        while lo <= lon + radius_deg + 1e-9:
            points.append((round(la, 4), round(lo, 4)))
            lo += step_deg
        la += step_deg

    grid = []
    for pla, plo in points:
        row = await fetch_coastwatch_sst_point(pla, plo, dataset=dataset)
        if row and row.get("sst_c") is not None:
            grid.append(row)
    return grid


def derive_pfz_fronts_from_grid(
    grid: List[Dict[str, Any]],
    *,
    min_front_deg_c: float = 0.35,
) -> List[Dict[str, Any]]:
    """Identify PFZ-like locations from a sampled SST grid.

    A 'front' is a cell whose SST differs from any neighbour by at least
    min_front_deg_c over one grid step - the thermal signal satellites use
    to flag productive water (PFZ).  The result is real satellite data
    with an explicit 'estimated' flag; it is NOT the official INCOIS PFZ
    advisory.

    Returns list of dicts with keys: lat, lon, sst_c, front_delta_c,
    estimated (True).
    """
    if len(grid) < 4:
        return []
    by_cell = {}
    for row in grid:
        try:
            la = float(row.get("latitude"))
            lo = float(row.get("longitude"))
            sst = float(row.get("sst_c"))
        except (ValueError, TypeError):
            continue
        by_cell[(round(la, 4), round(lo, 4))] = sst

    fronts = []
    for (la, lo), sst in by_cell.items():
        delta = 0.0
        for dla in (-0.25, 0.0, 0.25):
            for dlo in (-0.25, 0.0, 0.25):
                if dla == 0 and dlo == 0:
                    continue
                neighbour = by_cell.get((round(la + dla, 4), round(lo + dlo, 4)))
                if neighbour is None:
                    continue
                delta = max(delta, abs(sst - neighbour))
        if delta >= min_front_deg_c:
            fronts.append({
                "lat": la,
                "lon": lo,
                "sst_c": sst,
                "front_delta_c": round(delta, 3),
                "estimated": True,
                "basis": "noaa_coastwatch_mur_sst_front",
            })
    return fronts


# ---------------------------------------------------------------------------
# OpenWeatherMap scrapers (keyed API)
# ---------------------------------------------------------------------------

OPENWEATHER_BASE = "https://api.openweathermap.org/data"
# geodesic helpers ported locally to avoid a scipy dependency in scrapers
_EARTH_R_KM = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import radians, sin, cos, asin, sqrt

    p = radians(lat1)
    q = radians(lat2)
    a = 0.5 - cos(p - q) / 2 + cos(p) * cos(q) * (1 - cos(radians(lon1 - lon2))) / 2
    return 2 * _EARTH_R_KM * asin(sqrt(a))


def _ow_units(units: str = "metric") -> str:
    return units if units in ("metric", "imperial", "standard") else "metric"


async def fetch_openweather_current(
    lat: float, lon: float, api_key: str, units: str = "metric",
) -> Optional[Dict[str, Any]]:
    """Fetch current weather from OpenWeatherMap /data/2.5/weather.

    Returns dict with keys: temperature_c, feels_like_c, humidity_pct,
    pressure_hpa, wind_speed_ms, wind_direction_deg, visibility_m, clouds_pct,
    condition, condition_code, precipitation_mm (rain/snow within last hour),
    observation_time, sunrise, sunset, icon.
    """
    if not api_key:
        return None
    params = {"lat": str(lat), "lon": str(lon), "appid": api_key,
              "units": _ow_units(units)}
    data = await _get_json(f"{OPENWEATHER_BASE}/2.5/weather", params=params, timeout=20.0)
    if not data:
        return None
    try:
        main = data.get("main") or {}
        wind = data.get("wind") or {}
        clouds = data.get("clouds") or {}
        weather = (data.get("weather") or [{}])[0]
        rain = data.get("rain") or {}
        snow = data.get("snow") or {}
        precipitation_mm = rain.get("1h") or snow.get("1h")
        # OpenWeather w/ metric returns wind in m/s, visibility in m, temp in C.
        temp = main.get("temp")
        if _ow_units(units) == "imperial" and temp is not None:
            temp = (float(temp) - 32) * 5 / 9
            wind_speed = (wind.get("speed") or 0) * 0.44704
            visibility = (data.get("visibility") or 0) * 1609.344
        else:
            wind_speed = wind.get("speed")
            visibility = data.get("visibility")
        return {
            "temperature_c": float(temp) if temp is not None else None,
            "feels_like_c": main.get("feels_like"),
            "humidity_pct": main.get("humidity"),
            "pressure_hpa": main.get("pressure"),
            "wind_speed_ms": float(wind_speed) if wind_speed is not None else None,
            "wind_direction_deg": wind.get("deg"),
            "visibility_m": float(visibility) if visibility else None,
            "clouds_pct": clouds.get("all"),
            "condition": weather.get("description"),
            "condition_code": weather.get("id"),
            "condition_group": weather.get("main"),
            "precipitation_mm": float(precipitation_mm) if precipitation_mm else None,
            "observation_time": data.get("dt"),
            "sunrise": data.get("sys", {}).get("sunrise"),
            "sunset": data.get("sys", {}).get("sunset"),
            "icon": weather.get("icon"),
            "latitude": data.get("coord", {}).get("lat"),
            "longitude": data.get("coord", {}).get("lon"),
        }
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("openweather_current_parse_failed", error=str(exc))
        return None


async def fetch_openweather_forecast(
    lat: float, lon: float, api_key: str, units: str = "metric",
) -> Optional[Dict[str, Any]]:
    """Fetch 5-day /3h forecast from OpenWeatherMap /data/2.5/forecast.

    Returns dict with keys: temp_min_c, temp_max_c, wind_speed_ms,
    wind_direction_deg, pressure_hpa, humidity_pct, and a list of hourly
    forecast dicts under 'entries'.
    """
    if not api_key:
        return None
    params = {"lat": str(lat), "lon": str(lon), "appid": api_key,
              "units": _ow_units(units)}
    data = await _get_json(f"{OPENWEATHER_BASE}/2.5/forecast", params=params, timeout=20.0)
    if not data:
        return None
    try:
        entries = []
        temps_min, temps_max = [], []
        for item in data.get("list", []):
            main = item.get("main") or {}
            wind = item.get("wind") or {}
            weather = (item.get("weather") or [{}])[0]
            temp_c = main.get("temp")
            temp_min = main.get("temp_min")
            temp_max = main.get("temp_max")
            if _ow_units(units) == "imperial":
                if temp_c is not None:
                    temp_c = (float(temp_c) - 32) * 5 / 9
                if temp_min is not None:
                    temp_min = (float(temp_min) - 32) * 5 / 9
                if temp_max is not None:
                    temp_max = (float(temp_max) - 32) * 5 / 9
                wind_speed = (wind.get("speed") or 0) * 0.44704
            else:
                wind_speed = wind.get("speed")
            entries.append({
                "time": item.get("dt_txt"),
                "temperature_c": temp_c,
                "temp_min_c": temp_min,
                "temp_max_c": temp_max,
                "pressure_hpa": main.get("pressure"),
                "humidity_pct": main.get("humidity"),
                "wind_speed_ms": float(wind_speed) if wind_speed is not None else None,
                "wind_direction_deg": wind.get("deg"),
                "condition": weather.get("description"),
                "condition_code": weather.get("id"),
                "precipitation_mm": float(item.get("pop") or 0) * 100,
            })
            if temp_min is not None:
                temps_min.append(float(temp_min))
            if temp_max is not None:
                temps_max.append(float(temp_max))
        return {
            "temp_min_c": min(temps_min) if temps_min else None,
            "temp_max_c": max(temps_max) if temps_max else None,
            "wind_speed_ms": entries[0].get("wind_speed_ms") if entries else None,
            "wind_direction_deg": entries[0].get("wind_direction_deg") if entries else None,
            "pressure_hpa": entries[0].get("pressure_hpa") if entries else None,
            "humidity_pct": entries[0].get("humidity_pct") if entries else None,
            "observation_time": data.get("list", [{}])[0].get("dt"),
            "entries": entries,
        }
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("openweather_forecast_parse_failed", error=str(exc))
        return None


async def fetch_openweather_onecall(
    lat: float, lon: float, api_key: str, units: str = "metric",
) -> Optional[Dict[str, Any]]:
    """Fetch OpenWeatherMap One Call 3.0 (current + minutely + hourly + daily).

    Requires the paid 'One Call by Call' subscription on a 1.3 key; if the
    401/403 comes back this returns None so callers fall back gracefully.
    Returns dict with keys: current (dict), hourly (list), daily (list).
    """
    if not api_key:
        return None
    params = {"lat": str(lat), "lon": str(lon), "appid": api_key,
              "units": _ow_units(units), "exclude": "minutely"}
    data = await _get_json(f"{OPENWEATHER_BASE}/3.0/onecall", params=params, timeout=20.0)
    if not data:
        return None
    return data


async def fetch_openweather_marine(
    lat: float, lon: float, api_key: str, units: str = "metric",
) -> Optional[Dict[str, Any]]:
    """Fetch marine weather from OpenWeatherMap Marine Weather API.

    1.3 keys get /data/2.5/weather (over sea) - surface wind/pressure.
    Returns dict with keys: wind_speed_ms, wind_direction_deg, gust_ms,
    pressure_hpa, sea_level_pressure_hpa, temp_c, visibility_m, and the
    unix observation time.
    """
    if not api_key:
        return None
    data = await fetch_openweather_current(lat, lon, api_key, units)
    if not data:
        return None
    # OpenWeather /weather over ocean returns the "main" block plus wind.
    wind = data
    return {
        **data,
        "sea_level_pressure_hpa": data.get("pressure_hpa"),
    }


def _nearest_array_index(lat: float, lon: float, lats, lons) -> Optional[int]:
    """Return index of nearest (lat, lon) pair in parallel arrays."""
    best_idx = None
    best_km = float("inf")
    for i, (la, lo) in enumerate(zip(lats, lons)):
        try:
            d = _haversine_km(lat, lon, float(la), float(lo))
        except (ValueError, TypeError):
            continue
        if d < best_km:
            best_km = d
            best_idx = i
    if best_km < 200.0:
        return best_idx
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classify_warning_type(text: str) -> str:
    """Classify warning type from text content."""
    lower = text.lower()
    if "cyclone" in lower:
        return "cyclone"
    if "storm" in lower or "gale" in lower:
        return "storm_warning"
    if "fishing" in lower or "fish" in lower:
        return "fishing_warning"
    if "squall" in lower:
        return "squall"
    if "fog" in lower:
        return "fog_warning"
    if "tsunami" in lower:
        return "tsunami"
    return "other"


def _classify_severity(text: str) -> str:
    """Classify severity from text content."""
    lower = text.lower()
    if any(w in lower for w in ("extreme", "dangerous", "severe", "red")):
        return "critical"
    if any(w in lower for w in ("high", "orange", "warning", "strong")):
        return "high"
    if any(w in lower for w in ("moderate", "yellow", "watch")):
        return "moderate"
    if any(w in lower for w in ("low", "green", "advisory")):
        return "low"
    return "unknown"


def _classify_navarea_type(text: str) -> str:
    """Classify NAVAREA warning type."""
    lower = text.lower()
    if "firing" in lower or "exercise" in lower:
        return "firing_exercise"
    if "submarine" in lower:
        return "submarine_operation"
    if "mine" in lower:
        return "mine_hazard"
    if "wreck" in lower:
        return "wreck"
    if "buoy" in lower or "mark" in lower:
        return "aid_to_navigation"
    return "navigational_warning"


def _classify_navarea_severity(text: str) -> str:
    """Classify NAVAREA warning severity."""
    lower = text.lower()
    if any(w in lower for w in ("danger", "dangerous", "immediate")):
        return "critical"
    if any(w in lower for w in ("caution", "warning")):
        return "high"
    if "information" in lower:
        return "low"
    return "moderate"


def _extract_navarea_geometry(text: str) -> Optional[Dict[str, Any]]:
    """Try to extract polygon coordinates from NAVAREA warning text.

    Common formats:
      (A) 21-24.00N 067-05.00E, 21-03.29N 067-36.00E, ...
      18-09.47N 070-45.41E, 17-06.18N 071-05.04E, ...
    """
    # Match coordinate pairs like 21-24.00N 067-05.00E
    coord_pattern = r"(\d{1,2})[- ](\d{1,2}(?:\.\d+)?)\s*[Nn]\s+(\d{1,3})[- ](\d{1,2}(?:\.\d+)?)\s*[Ee]"
    matches = re.findall(coord_pattern, text)

    if not matches:
        return None

    coords = []
    for lat_d, lat_m, lon_d, lon_m in matches:
        try:
            lat = float(lat_d) + float(lat_m) / 60.0
            lon = float(lon_d) + float(lon_m) / 60.0
            coords.append([lon, lat])  # GeoJSON is [lon, lat]
        except (ValueError, ZeroDivisionError):
            continue

    if len(coords) < 3:
        return None

    # Close the polygon if not already closed.
    if coords[0] != coords[-1]:
        coords.append(coords[0])

    return {
        "type": "Polygon",
        "coordinates": [coords],
    }


# ---------------------------------------------------------------------------
# JTWC cyclone warnings (keyless public feed)
# ---------------------------------------------------------------------------

# metoc.navy.mil 403s bot user-agents but serves a desktop browser UA.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

JTWC_RSS_PATH = "jtwc/rss/jtwc.rss"
JTWC_PRODUCTS_PATH = "jtwc/products/"

# Storm name lines look like: "Tropical Depression 22W (Krovanh) Warning #26"
_STORM_NAME_RE = re.compile(
    r"(Tropical\s+(?:Depression|Storm)|Typhoon|Super\s+Typhoon|"
    r"Tropical\s+Cyclone|Invest)\b[^<]*?"
    r"(\d{2}[A-Z])\b[^<]*?(?:\(([^)<]+)\))?\s*Warning\s*#\s*(\d+)",
    re.IGNORECASE,
)

# Forecast track lines: "INIT 08/1200Z 18.8N 123.2E   25 KT 35 KT" /
# "12HRS 09/0000Z 18.7N 121.9E   30 KT 40 KT"
_TRACK_POSITION_RE = re.compile(
    r"(?:INIT|(\d+)\s*HRS)\s+(\d{2})/(\d{4})Z\s+"
    r"(\d{1,2}(?:\.\d+)?)\s*N\s+(\d{1,3}(?:\.\d+)?)\s*E",
    re.IGNORECASE,
)
_WIND_KT_RE = re.compile(
    r"MAXIMUM\s+SUSTAINED\s+(?:SURFACE\s+)?WINDS?\s+"
    r"(?:ARE\s+)?(?:ESTIMATED\s+)?(?:AT\s+)?(\d{2,3})\s*KNOTS?",
    re.IGNORECASE,
)
_WIND_KT_DASH_RE = re.compile(
    r"MAX\s+SUSTAINED\s+WINDS?\s*[-=]\s*(\d{2,3})\s*KT", re.IGNORECASE,
)
_WIND_KT_GUST_RE = re.compile(
    r"WINDS?\s+(\d{2,3})\s*KT\s*,?\s*GUSTS?\s+(\d{2,3})\s*KT", re.IGNORECASE,
)
_PRESSURE_MB_RE = re.compile(
    r"MINIMUM\s+SEA\s+LEVEL\s+PRESSURE\s+IS\s+ESTIMATED\s+AT\s+(\d{3,4})\s*MB",
    re.IGNORECASE,
)


def _maxto_decimal(value: str) -> Optional[float]:
    """Convert deg+min DDMM.M or NW-style coordinate pieces to decimal."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _degrade_storm_wind_knots(text: str) -> Optional[int]:
    for pattern in (_WIND_KT_RE, _WIND_KT_DASH_RE, _WIND_KT_GUST_RE):
        match = pattern.search(text)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                pass
    return None


def _degrade_storm_bulletin(text: str) -> Dict[str, Any]:
    """Extract track/wind/pressure metadata from a JTWC warning bulletin."""
    positions: List[Dict[str, Any]] = []
    for hh, day, time, lat_s, lon_s in _TRACK_POSITION_RE.findall(text):
        lat = _maxto_decimal(lat_s)
        lon = _maxto_decimal(lon_s)
        if lat is None or lon is None:
            continue
        positions.append({
            "time": f"{day}/{time}Z",
            "lat": lat,
            "lon": lon,
            "lead_hours": int(hh) if hh else 0,
        })
    return {
        "positions": positions,
        "max_wind_kt": _degrade_storm_wind_knots(text),
        "pressure_mb": _degrade_pressure(text),
        "text": text,
    }


def _degrade_pressure(text: str) -> Optional[int]:
    match = _PRESSURE_MB_RE.search(text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


async def fetch_jtwc_cyclone_warnings(base_url: str) -> List[Dict[str, Any]]:
    """Fetch active tropical cyclone warnings from the public JTWC RSS feed.

    The RSS item descriptions carry the storm names and links to the full
    warning bulletins; each bulletin is fetched and parsed for the current +
    forecast track positions, max sustained winds and central pressure.

    Returns list of dicts with keys:
      storm_name, warning_id, warning_number, basin, issued_at (ISO),
      bulletin_url, positions (list of {lat, lon, lead_hours, time}),
      max_wind_kt, pressure_mb, description.
    Empty list on any failure (never raises).
    """
    rss_url = f"{base_url.rstrip('/')}/{JTWC_RSS_PATH}"
    rss_text = await _get(rss_url, timeout=30.0,
                          headers={"User-Agent": _BROWSER_UA})
    if not rss_text:
        logger.warning("jtwc_rss_unavailable")
        return []

    warnings: List[Dict[str, Any]] = []

    def walk_items():
        # Parse without external libs if possible (ElementTree), else bs4.
        import xml.etree.ElementTree as ET
        root = ET.fromstring(rss_text)
        for item in list(root.iter("item")):
            title = (item.findtext("title") or "").strip()
            desc = (item.findtext("description") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            yield title, desc, pub

    try:
        for _title, desc, pub in walk_items():
            basina = ""
            m = re.search(r"([A-Za-z ]+)\*?\s+Tropical Systems",
                          _title or "")
            if m:
                basina = m.group(1).strip()
            storms = _STORM_NAME_RE.findall(desc)
            # Bulletin links use a single-quoted href in the RSS description.
            links = re.findall(r"""href=['"]([^'"]+)['"]""", desc)
            bulletin_by_storm = [
                u for u in links if re.search(r'(?:web|fix)\.txt$', u)
            ]
            for idx, (kind, codeletter, name, num) in enumerate(storms):
                name = (name or "").strip() or codeletter
                warning_id = f"{codeletter.lower()}-{name.lower().replace(' ', '-')}"
                bulletin_rel = None
                if idx < len(bulletin_by_storm):
                    bulletin_rel = bulletin_by_storm[idx]
                if bulletin_rel and bulletin_rel.startswith("http"):
                    bulletin_url = bulletin_rel
                elif bulletin_rel:
                    bulletin_url = (
                        f"{base_url.rstrip('/')}/{JTWC_PRODUCTS_PATH}/"
                        f"{bulletin_rel.split('/')[-1]}"
                    )
                else:
                    bulletin_url = None

                issued_at = _parse_rfc2822(pub)

                # Fetch + parse the full bulletin for track/wind.
                text = ""
                if bulletin_url:
                    text = await _get(bulletin_url, timeout=30.0,
                                      headers={"User-Agent": _BROWSER_UA}) or ""
                meta = _degrade_storm_bulletin(text) if text else {}

                warnings.append({
                    "storm_name": name,
                    "kind": kind,
                    "warning_id": f"{warning_id}-#{num}",
                    "warning_number": int(num) if num.isdigit() else None,
                    "basin": basina,
                    "issued_at": issued_at,
                    "bulletin_url": bulletin_url,
                    "positions": meta.get("positions", []),
                    "max_wind_kt": meta.get("max_wind_kt"),
                    "pressure_mb": meta.get("pressure_mb"),
                    "description": _storm_description(meta),
                })
    except Exception as exc:
        logger.warning("jtwc_rss_parse_failed", error=str(exc))
        return warnings

    return warnings


def _parse_rfc2822(value: str) -> Optional[str]:
    """RFC-2822 pubDate to ISO UTC string (or None)."""
    if not value:
        return None
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def _storm_description(meta: Dict[str, Any]) -> str:
    parts = []
    if meta.get("max_wind_kt"):
        parts.append(f"Max winds {meta['max_wind_kt']} kt at center")
    if meta.get("pressure_mb"):
        parts.append(f"central pressure {meta['pressure_mb']} mb")
    else:
        parts.append("tropical cyclone warning; see JTWC bulletin")
    return ", ".join(parts) + "."


# ---------------------------------------------------------------------------
# GDACS cyclone warnings (keyless public framework feed)
# ---------------------------------------------------------------------------

GDACS_RSS_URL = "https://www.gdacs.org/xml/rss.xml"
_GDACS_NS = "http://www.gdacs.org"
_GEO_NS = "http://www.w3.org/2003/01/geo/wgs84_pos#"
_GEORSS_NS = "http://www.georss.org/georss"


async def fetch_gdacs_cyclone_warnings() -> List[Dict[str, Any]]:
    """Fetch active tropical cyclone events from the public GDACS RSS feed.

    GDACS is public domain (EU, CC BY 4.0).  Each current TC item carries the
    centre point, affected-area bbox, validity window and severity.

    Returns list of dicts with keys: storm_name, warning_id, severity_kmh,
    alertlevel, valid_from, valid_until, issued_at, center {lat, lon},
    bbox [min_lon, max_lon, min_lat, max_lat], link, description.
    Empty list on any failure (never raises).
    """
    rss_text = await _get(GDACS_RSS_URL, timeout=30.0)
    if not rss_text:
        logger.warning("gdacs_rss_unavailable")
        return []

    import xml.etree.ElementTree as ET
    outbreaks: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(rss_text)
        items = list(root.iter("item")) + list(root.iter(
            "{http://www.w3.org/2005/Atom}entry"))
        geo_lt = f"{{{_GEO_NS}}}lat"
        geo_ln = f"{{{_GEO_NS}}}long"
        for item in items:
            ev_type = _gdacs_child(item, "eventtype") or ""
            if ev_type.lower() != "tc":
                continue
            if (_gdacs_child(item, "iscurrent") or "").strip().lower() != "true":
                continue
            center = {"lat": None, "lon": None}
            pt = item.find(f"{{{_GEO_NS}}}Point")
            if pt is not None:
                center["lat"] = _gdacs_text(pt, "lat") or _gdacs_text(pt, geo_lt)
                center["lon"] = _gdacs_text(pt, "long") or _gdacs_text(pt, geo_ln)
            if center["lat"] is None:
                georss_pt = _gdacs_text(item, f"{{{_GEORSS_NS}}}point")
                if georss_pt:
                    parts = georss_pt.split()
                    if len(parts) == 2:
                        center = {"lat": parts[0], "lon": parts[1]}

            bbox = _parse_gdacs_bbox(_gdacs_child(item, "bbox"))
            eventid = (_gdacs_child(item, "eventid") or "").strip()
            severity_value = _gdacs_attr(item, "severity", "value")
            outbreaks.append({
                "storm_name": (_gdacs_child(item, "eventname") or "").strip() or f"TC-{eventid}",
                "warning_id": f"gdacs-{eventid}",
                "severity_kmh": severity_value,
                "alertlevel": (_gdacs_child(item, "alertlevel") or "Green").strip(),
                "valid_from": _gdacs_rfc(item, "fromdate"),
                "valid_until": _gdacs_rfc(item, "todate"),
                "issued_at": _gdacs_rfc(item, "dateadded") or _gdacs_rfc(item, "pubDate"),
                "center": center,
                "bbox": bbox,
                "link": (_gdacs_child(item, "link") or "").strip(),
                "description": _gdacs_item_description(item),
            })
    except Exception as exc:
        logger.warning("gdacs_rss_parse_failed", error=str(exc))
        return outbreaks
    return outbreaks


def _gdacs_child(item, localname: str) -> Optional[str]:
    for key in (f"{{{_GDACS_NS}}}{localname}", f"{{{_GDACS_NS}}}{localname.capitalize()}",
                localname):
        value = item.findtext(key)
        if value:
            return value
    return None


def _gdacs_text(el, key: str) -> Optional[str]:
    value = el.findtext(key)
    return (value or "").strip() or None


def _gdacs_attr(item, localname: str, attr: str) -> Optional[str]:
    for key in (f"{{{_GDACS_NS}}}{localname}", localname):
        el = item.find(key)
        if el is not None:
            return el.get(attr)
    return None


def _gdacs_rfc(item, localname: str) -> Optional[str]:
    raw = _gdacs_child(item, localname)
    if not raw:
        return None
    return _parse_rfc2822(raw)


def _gdacs_item_description(item) -> str:
    raw = _gdacs_child(item, "description")
    if raw:
        return " ".join(raw.split())[:500]
    title = _gdacs_child(item, "title")
    return (" ".join(title.split())[:300]) if title else "Tropical cyclone advisory"


def _parse_gdacs_bbox(value: Optional[str]) -> Optional[List[float]]:
    """GDACS bbox: minLon maxLon minLat maxLat (floats); None when malformed."""
    if not value:
        return None
    parts = value.split()
    if len(parts) != 4:
        return None
    try:
        return [float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])]
    except (ValueError, TypeError):
        return None
