"""Deterministic Risk Engine — overrides ML whenever authoritative data demands it.

Statuses: HARD_RESTRICTION > OFFICIAL_WARNING > HIGH_RISK > MODERATE_RISK > LOW_RISK > UNKNOWN.
Never return SAFE/LOW when required safety data is unavailable.
"""
from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

Status = Literal["HARD_RESTRICTION", "OFFICIAL_WARNING", "HIGH_RISK", "MODERATE_RISK", "LOW_RISK", "UNKNOWN"]


class RiskDecision(BaseModel):
    status: Status
    reason_codes: List[str] = Field(default_factory=list)
    risk_drivers: List[str] = Field(default_factory=list)
    overrides: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    decided_at: datetime = Field(default_factory=datetime.utcnow)


def decide(ml_risk: float, official_warning: bool = False, geofence_hit: Optional[str] = None,
           data_fresh: bool = True, wave_m: float = 0.0, wind_ms: float = 0.0) -> RiskDecision:
    reasons, overrides, drivers, sources = [], [], [], ["ml:marine_risk"]
    if not data_fresh:
        return RiskDecision(status="UNKNOWN", reason_codes=["STALE_DATA"],
                            risk_drivers=["data freshness unknown"], sources=sources)
    if geofence_hit:
        return RiskDecision(status="HARD_RESTRICTION", reason_codes=["GEOFENCE_HIT"],
                            risk_drivers=[f"restricted zone: {geofence_hit}"],
                            overrides=["geofence overrides ML"], sources=sources + ["postgis:geofence"])
    if official_warning:
        return RiskDecision(status="OFFICIAL_WARNING", reason_codes=["OFFICIAL_WARNING_ACTIVE"],
                            risk_drivers=["authoritative warning active"],
                            overrides=["official warning overrides ML"],
                            sources=sources + ["imd/incois:warning"])
    if wave_m >= 4.5 or wind_ms >= 20.0:
        return RiskDecision(status="HIGH_RISK", reason_codes=["HARD_WX_LIMIT"],
                            risk_drivers=["wave/wind hard limit"], sources=sources)
    if ml_risk >= 0.6:
        status, reasons = "HIGH_RISK", ["ML_HIGH_RISK"]
    elif ml_risk >= 0.35:
        status, reasons = "MODERATE_RISK", ["ML_MODERATE_RISK"]
    else:
        status, reasons = "LOW_RISK", ["ML_LOW_RISK"]
    drivers.append(f"ml_risk={ml_risk:.2f}")
    return RiskDecision(status=status, reason_codes=reasons, risk_drivers=drivers, sources=sources)


def to_dict(d: RiskDecision) -> Dict:
    return d.model_dump(mode="json")
