# Phase 5 - canonical real-data contracts for marine intelligence.
#
# DataClass distinguishes the ORIGIN of every value surfaced to a user:
# observations come from instruments/records, forecasts from predictive models,
# advisories from official issuers, derived analytics from deterministic
# computation over real values, and model predictions from ML - which NEVER
# overrides safety computation.  DataFreshness states every value's age in a
# query-time vocabulary (fresh/aging/stale/expired/unknown).
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class DataClass(str, Enum):
    OBSERVATION = "observation"
    FORECAST = "forecast"
    ADVISORY = "advisory"
    DERIVED_ANALYTICS = "derived_analytics"
    MODEL_PREDICTION = "model_prediction"


class DataFreshness(str, Enum):
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass
class MarineObservation:
    """Common real-data record: every fact traced to a source + key."""
    source: str
    source_record_id: Optional[str] = None
    observation_time: Optional[datetime] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geometry: Optional[Dict[str, Any]] = None
    parameter: str = ""
    value: Any = None
    unit: Optional[str] = None
    quality: str = "valid"
    confidence: Optional[float] = None
    provenance: List[Dict[str, Any]] = field(default_factory=list)
    data_class: DataClass = DataClass.OBSERVATION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "source_record_id": self.source_record_id,
            "observation_time": _iso(self.observation_time),
            "valid_from": _iso(self.valid_from),
            "valid_until": _iso(self.valid_until),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "geometry": self.geometry,
            "parameter": self.parameter,
            "value": self.value,
            "unit": self.unit,
            "quality": self.quality,
            "confidence": self.confidence,
            "provenance": self.provenance,
            "data_class": self.data_class.value,
        }


@dataclass
class ModelResult:
    """Envelope for computed analytics: identifies itself, its inputs and its
    provenance so a client can always tell a derived number from an
    observation and never mistakes a model estimate for measured truth."""
    output: Dict[str, Any]
    data_class: DataClass = DataClass.DERIVED_ANALYTICS
    delivered_from: str = ""
    source_ids: List[str] = field(default_factory=list)
    provenance: List[Dict[str, Any]] = field(default_factory=list)
    freshness: Optional[str] = None
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output": self.output,
            "data_class": self.data_class.value,
            "delivered_from": self.delivered_from,
            "source_ids": self.source_ids,
            "provenance": self.provenance,
            "freshness": self.freshness,
            "note": self.note,
        }


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None