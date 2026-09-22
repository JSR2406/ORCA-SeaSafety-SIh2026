# Hazard Schema
# Schema for marine hazard data including cyclones, storms, warnings, and geofences

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


class HazardType(str, Enum):
    """Types of marine hazards."""
    CYCLONE = "cyclone"
    STORM = "storm"
    WARNING = "warning"
    GEOFENCE = "geofence"
    SHALLOW_WATER = "shallow_water"
    ICE = "ice"
    FOG = "fog"


class HazardSeverity(str, Enum):
    """Severity levels for hazards."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class HazardArea(BaseModel):
    """Geographic area affected by a hazard."""
    hazard_id: str
    hazard_type: HazardType
    severity: HazardSeverity
    location: Dict[str, float]  # lat, lon of center
    radius_km: Optional[float] = Field(default=None, ge=0)
    polygon_wkt: Optional[str] = Field(default=None, description="WKT polygon geometry")
    description: str
    valid_from: Optional[datetime] = Field(default=None)
    valid_to: Optional[datetime] = Field(default=None)


class HazardWarning(BaseModel):
    """Individual hazard warning."""
    warning_id: str
    hazard_type: HazardType
    severity: HazardSeverity
    issue_authority: str  # e.g., "India Meteorological Department"
    issue_time: datetime
    expiry_time: datetime
    affected_area: HazardArea
    description: str
    action_recommended: str


class HazardComparison(BaseModel):
    """Comparison of current hazard vs baseline."""
    hazard_id: str
    current_severity: HazardSeverity
    baseline_severity: HazardSeverity
    change: Literal["increasing", "decreasing", "stable"]
    confidence: float
    reasons: str


class HazardReport(BaseModel):
    """Complete hazard report for a region."""
    report_id: str
    region: Dict[str, float]  # lat, lon
    radius_km: float
    generated_at: datetime
    
    # Current hazards
    active_hazards: List[HazardArea]
    warnings: List[HazardWarning]
    
    # Comparison
    comparisons: Optional[List[HazardComparison]] = Field(default_factory=list)
    
    # Summary
    overall_severity: HazardSeverity
    affected_vessels: int = Field(default=0, ge=0)
    recommended_actions: List[str] = Field(default_factory=list)


# Global hazard report instance placeholder
_hazard_reports: Dict[str, HazardReport] = {}


def get_hazard_report(report_id: str) -> Optional[HazardReport]:
    """Get a hazard report by ID."""
    return _hazard_reports.get(report_id)


def create_hazard_report(report_id: str, region: Dict[str, float], 
                         radius_km: float, generated_at: datetime,
                         active_hazards: List[HazardArea],
                         warnings: List[HazardWarning],
                         comparisons: Optional[List[HazardComparison]] = None,
                         overall_severity: HazardSeverity = HazardSeverity.LOW,
                         affected_vessels: int = 0,
                         recommended_actions: Optional[List[str]] = None) -> HazardReport:
    """Create a new hazard report."""
    report = HazardReport(
        report_id=report_id,
        region=region,
        radius_km=radius_km,
        generated_at=generated_at,
        active_hazards=active_hazards,
        warnings=warnings,
        comparisons=comparisons or [],
        overall_severity=overall_severity,
        affected_vessels=affected_vessels,
        recommended_actions=recommended_actions or [],
    )
    _hazard_reports[report_id] = report
    return report