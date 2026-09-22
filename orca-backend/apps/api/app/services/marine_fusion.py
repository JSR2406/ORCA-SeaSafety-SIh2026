# MarineDataFusion + FusedMarineState - the canonical, single fused view of the
# marine environment for a location and time.
#
# Fusion NEVER invents values: a variable appears in `variables` only when at
# least one real stored observation provided it.  Otherwise it is listed in
# `missing` and the state records which provider was unavailable in
# `limitations`.  All provider provenance is kept per variable.
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.common import DataStatus, utcnow
from app.models.result import MarineDataResult
from app.services.freshness import evaluate_freshness

OCEAN_VARIABLES = [
    "wave_height_m", "wave_period_s", "wave_direction_deg",
    "wind_speed_ms", "wind_direction_deg",
    "current_speed_ms", "current_direction_deg",
    "sst_c", "salinity_psu", "chlorophyll",
]
WEATHER_VARIABLES = [
    "temperature_c", "wind_speed_ms", "wind_direction_deg",
    "precipitation_mm", "pressure_hpa", "humidity_pct",
    "visibility_m", "condition", "lightning",
]

_HEALTHY = (DataStatus.LIVE, DataStatus.RECENT, DataStatus.STALE)


@dataclass
class FusedMarineState:
    lat: float
    lon: float
    requested_at: datetime = field(default_factory=utcnow)
    data_time: Optional[datetime] = None
    status: str = DataStatus.UNAVAILABLE.value
    sources: List[str] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    providers: Dict[str, List[dict]] = field(default_factory=dict)
    confidence: Optional[float] = None
    missing: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    freshness: Dict[str, Any] = field(default_factory=dict)
    conflicts: List[dict] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lat": self.lat,
            "lon": self.lon,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "data_time": self.data_time.isoformat() if self.data_time else None,
            "status": self.status,
            "sources": sorted(self.sources),
            "variables": self.variables,
            "providers": self.providers,
            "confidence": self.confidence,
            "missing": self.missing,
            "limitations": self.limitations,
            "freshness": self.freshness,
            "conflicts": self.conflicts,
        }


class MarineDataFusion:
    """Fuse ocean + weather observations into one canonical marine state."""

    def __init__(self, marine=None):
        from app.config import get_settings
        from app.datasources.registry import build_registry
        from app.db.client import get_session
        from app.services.marine_data_service import MarineDataService

        self.settings = get_settings()
        if marine is None:
            sources = build_registry(self.settings)
            marine = MarineDataService(self.settings, sources, get_session)
        self.marine = marine

    async def fused_state(
        self,
        lat: float,
        lon: float,
        time: Optional[datetime] = None,
        radius_km: float = 50.0,
    ) -> FusedMarineState:
        """Build the fused state at a point from real stored observations."""
        ocean = await self.marine.get_ocean_conditions(
            lat, lon, time=time, radius_km=radius_km, limit=5)
        weather = await self.marine.get_weather_observation(
            lat, lon, time=time, radius_km=radius_km, limit=5)

        state = FusedMarineState(lat=lat, lon=lon)
        confidences: List[float] = []
        self._merge(state, ocean, OCEAN_VARIABLES, confidences,
                    not_configured_label="ocean data source(s)")
        self._merge(state, weather, WEATHER_VARIABLES, confidences,
                    not_configured_label="weather data source(s)")

        state.sources = sorted({
            s for var_providers in state.providers.values()
            for p in var_providers for s in [p["source"]]
        })
        state.conflicts = self._detect_conflicts(state)
        for conflict in state.conflicts:
            state.limitations.append(conflict["limitation"])
        if confidences:
            state.confidence = round(sum(confidences) / len(confidences), 3)
        if not state.variables:
            state.status = self._no_data_status(ocean, weather)
            if not state.limitations:
                state.limitations.append(
                    "No real marine observations available for fusion")
        else:
            state.status = self._status_of(ocean, weather)
        state.freshness = self._compute_freshness(state)
        return state

    @staticmethod
    def _compute_freshness(state: "FusedMarineState") -> Dict[str, Any]:
        """Per-source freshness (latest observation per source) with overall.

        Ocean observations are judged against the ocean freshness threshold.
        Labels follow freshness.evaluate_freshness (fresh/aging/stale/
        expired/unknown) - never fabricated, never silently downgraded.
        """
        from app.config import get_settings

        threshold = float(get_settings().ocean_freshness_seconds)
        per_source: Dict[str, datetime] = {}
        for providers in state.providers.values():
            for p in providers:
                ts = p.get("observation_time")
                if not ts:
                    continue
                source = p.get("source") or "unknown"
                if source not in per_source or ts > per_source[source]:
                    per_source[source] = ts
        now = utcnow()
        table: Dict[str, Dict[str, Any]] = {}
        overall: Optional[str] = None
        _rank = {"fresh": 0, "aging": 1, "stale": 2, "expired": 3, "unknown": 4}
        for source, ts in per_source.items():
            label, reason = evaluate_freshness(ts, threshold, now=now)
            table[source] = {
                "freshness": label.value,
                "observation_time": ts.isoformat(),
                "reason": reason,
            }
            if overall is None or _rank[label.value] > _rank[overall]:
                overall = label.value
        return {
            "overall": overall if overall is not None else "unknown",
            "threshold_seconds": threshold,
            "per_source": table,
        }

    # ------------------------------------------------------------------ merge
    @staticmethod
    def _row_provider(row: dict, result: MarineDataResult) -> dict:
        return {
            "source": row.get("source") or ",".join(result.sources or []),
            "source_record_id": row.get("source_record_id"),
            "observation_time": row.get("observation_time") or row.get("valid_time"),
        }

    def _merge(
        self,
        state: FusedMarineState,
        result: MarineDataResult,
        candidates: List[str],
        confidences: List[float],
        not_configured_label: str,
    ) -> None:
        rows = result.data
        if result.status not in _HEALTHY or not rows:
            for var in candidates:
                if var not in state.variables and var not in state.missing:
                    state.missing.append(var)
            if result.status == DataStatus.NOT_CONFIGURED:
                state.limitations.append(
                    f"{not_configured_label} not configured; only available "
                    "sources contributed to the fused state")
            elif result.status in (DataStatus.ERROR, DataStatus.UNAVAILABLE):
                state.limitations.append(
                    f"{not_configured_label} reported an error; only available "
                    "sources contributed to the fused state")
            return

        if result.confidence is not None:
            confidences.append(float(result.confidence))

        # First pass: value selection (first real row wins) with full per-variable
        # provider provenance (both ocean and weather rows are recorded).
        values: Dict[str, Any] = dict(state.variables)
        providers: Dict[str, List[dict]] = {
            k: list(v) for k, v in state.providers.items()}
        for row in rows:
            if not isinstance(row, dict):
                continue
            provider = self._row_provider(row, result)
            for var in candidates:
                value = row.get(var)
                if value is None:
                    continue
                if var not in values:
                    values[var] = value
                record = dict(provider)
                record["value"] = value
                providers.setdefault(var, []).append(record)
        state.variables = values
        state.providers = providers

        # Second pass: missing + data_time.
        for var in candidates:
            if var not in state.variables:
                if var not in state.missing:
                    state.missing.append(var)
        for row in rows:
            if not isinstance(row, dict):
                continue
            ts = row.get("observation_time") or row.get("valid_time")
            if ts:
                if state.data_time is None or ts > state.data_time:
                    state.data_time = ts

    @staticmethod
    def _values_disagree(a: Any, b: Any) -> bool:
        """Deterministic conflict rule for two provider-reported values.

        Categorical (string/bool) values disagree when they differ.  Numeric
        values disagree only when the divergence is material (>=10% relative
        AND >0.05 absolute); tiny inter-provider jitter is NOT a conflict so
        the normal healthy path stays clean.
        """
        if (isinstance(a, bool) or isinstance(b, bool)
                or not (isinstance(a, (int, float))
                        and isinstance(b, (int, float)))):
            return bool(a != b)
        af, bf = float(a), float(b)
        scale = max(abs(af), abs(bf), 1e-3)
        return abs(af - bf) / scale >= 0.10 and abs(af - bf) > 0.05

    @classmethod
    def _detect_conflicts(cls, state: "FusedMarineState") -> List[dict]:
        """Phase 7 - surface material source disagreements.

        Every real observation is already preserved per variable in
        ``providers`` (with the literal value each source reported).  When two
        or more distinct values for the same variable disagree materially, we
        record the conflict - variable, values with their sources - so the
        response can say the data conflicts instead of silently keeping the
        first row.  Both values remain in ``providers`` (nothing is discarded).
        """
        conflicts: List[dict] = []
        for var in sorted(state.providers):
            distinct: List[dict] = []
            for prov in state.providers[var]:
                value = prov.get("value")
                if value is None:
                    continue
                if any(e["value"] == value for e in distinct):
                    continue
                distinct.append({"value": value, "source": prov.get("source")})
            if len(distinct) < 2:
                continue
            disagrees = any(
                cls._values_disagree(distinct[i]["value"],
                                     distinct[j]["value"])
                for i in range(len(distinct))
                for j in range(i + 1, len(distinct)))
            if not disagrees:
                continue
            detail = "; ".join(
                f"{e['value']} ({e['source']})" for e in distinct)
            conflicts.append({
                "variable": var,
                "values": distinct,
                "limitation": f"source conflict for {var}: {detail} - "
                              "values preserved from all sources",
            })
        return conflicts

    @staticmethod
    def _no_data_status(ocean: MarineDataResult, weather: MarineDataResult) -> str:
        if (ocean.status == DataStatus.NOT_CONFIGURED
                and weather.status == DataStatus.NOT_CONFIGURED):
            return DataStatus.NOT_CONFIGURED.value
        if (ocean.status == DataStatus.ERROR or weather.status == DataStatus.ERROR):
            return DataStatus.ERROR.value
        return DataStatus.UNAVAILABLE.value

    @staticmethod
    def _status_of(ocean: MarineDataResult, weather: MarineDataResult) -> str:
        present = [r for r in (ocean, weather) if r.status in _HEALTHY and r.data]
        if not present:
            return DataStatus.UNAVAILABLE.value
        statuses = {r.status for r in present}
        if DataStatus.LIVE in statuses:
            return DataStatus.LIVE.value
        if DataStatus.RECENT in statuses:
            return DataStatus.RECENT.value
        return DataStatus.STALE.value


_fusion: Optional[MarineDataFusion] = None


def get_marine_data_fusion() -> MarineDataFusion:
    global _fusion
    if _fusion is None:
        _fusion = MarineDataFusion()
    return _fusion