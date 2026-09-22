# Phase 5 - first-class DYNAMIC RESTRICTIONS.
#
# Runtime restrictions (NAVAREA/NAVTEX advisories, naval/firing exercises,
# temporary closures) are authoritative official inputs with validity windows.
# They follow the SAME window semantics as static restrictions but are live:
# only a refreshed, still-valid window may ever be treated as active.  Expired
# restrictions must never remain active.  Phase 9 adds authoritative
# cancellation (a withdrawn notice never binds a route) and change detection.
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from app.models.common import utcnow
from app.models.marine_contract import DataClass
from app.models.warnings import WarningStatus, evaluate_window_status


# Fields that can change on refresh and are safety-relevant.  A change to any
# of these upgrades the severity of a route/point decision and is recorded.
CHANGE_SENSITIVE_FIELDS: Tuple[str, ...] = (
    "geometry", "valid_from", "valid_until", "severity", "description",
    "restriction_type", "name", "status", "cancelled", "expired",
)


def detect_changes(old: "DynamicRestriction",
                   new: "DynamicRestriction",
                   at: Optional[datetime] = None) -> Set[str]:
    """Return the set of safety-relevant fields that differ old -> new.

    Used by the stores so an update is never a blind append: a source that
    tightens a window, moves a geometry or upgrades severity is flagged,
    preserving source history where appropriate.  `status` is compared as the
    resolved window status at a reference time, not as a bound method.
    """
    at = at or utcnow()
    changed: Set[str] = set()
    for f in CHANGE_SENSITIVE_FIELDS:
        if f == "status":
            if old.status(at) != new.status(at):
                changed.add(f)
            continue
        a = getattr(old, f, None)
        b = getattr(new, f, None)
        if a != b:
            changed.add(f)
    return changed


@dataclass
class DynamicRestriction:
    source: str
    source_record_id: str
    restriction_id: str
    name: str
    restriction_type: str
    severity: str
    geometry: Dict[str, Any]
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    issued_at: Optional[datetime] = None
    official: bool = True
    data_class: str = DataClass.ADVISORY.value
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: Optional[datetime] = None
    refreshed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expired: bool = False
    cancelled: bool = False

    def natural_key(self) -> Tuple[str, str]:
        return (self.source, self.source_record_id)

    def status(self, at: Optional[datetime] = None) -> WarningStatus:
        if self.cancelled:
            return WarningStatus.CANCELLED
        if self.expired:
            return WarningStatus.EXPIRED
        return evaluate_window_status(
            self.valid_from, self.valid_until, at or utcnow())

    def distance_to(self, lat: float, lon: float) -> Optional[float]:
        """Approximate distance (m) to this restriction geometry (0 when inside)."""
        from app.services.geospatial_service import point_to_polygon_distance_m
        return point_to_polygon_distance_m(lat, lon, self.geometry or {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "source_record_id": self.source_record_id,
            "restriction_id": self.restriction_id,
            "name": self.name,
            "restriction_type": self.restriction_type,
            "severity": self.severity,
            "geometry": self.geometry,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "issued_at": self.issued_at.isoformat() if self.issued_at else None,
            "official": self.official,
            "data_class": self.data_class,
            "description": self.description,
            "metadata": self.metadata,
            "ingested_at": self.ingested_at.isoformat() if self.ingested_at else None,
            "refreshed_at": self.refreshed_at.isoformat() if self.refreshed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "expired": self.expired,
            "cancelled": self.cancelled,
        }