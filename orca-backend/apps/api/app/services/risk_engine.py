# Risk Engine
# Transparent risk scoring for marine conditions

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.schemas.hazard import HazardType, HazardSeverity, HazardArea
from app.schemas.route import RiskAssessment, EnvironmentalConditions
from app.schemas.evidence import ConfidenceScore, ConfidenceComponents, ConfidenceLabel
from app.services.provenance import get_provenance_service

logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Provides transparent risk scoring for marine conditions.
    All calculations are deterministic and explainable.
    """
    
    def __init__(self):
        self.provenance = get_provenance_service()
    
    def assess_risk(
        self,
        environmental_conditions: EnvironmentalConditions,
        active_hazards: Optional[List[HazardArea]] = None,
        geofence_violations: Optional[List[Any]] = None,
        route_context: Optional[Dict[str, Any]] = None,
        hard_constraints: Optional[Dict[str, Any]] = None,
    ) -> RiskAssessment:
        """
        Assess overall risk based on environmental conditions and hazards.
        
        Hard constraints (active restricted areas, active high/critical marine
        warnings) are authoritative: if any are present the final level becomes
        "elevated" regardless of the environmental/ML score.  Machine estimates
        never override a hard constraint.
        
        `hard_constraints` is a dict like::

            {
                "active_restrictions": 1,           # count of active restricted areas
                "high_severity_warnings": 2,        # count of active high/critical warnings
                "restrictions": [...],              # optional details for reasoning
                "warnings": [...],                  # optional details for reasoning
            }

        Returns RiskAssessment with overall score, risk level, component scores,
        and detailed reasoning.
        """
        start_time = datetime.utcnow()
        
        # Initialize component scores
        component_scores = {}
        
        # 1. Wave risk (based on max wave height)
        wave_risk = self._calc_wave_risk(environmental_conditions.max_wave_height)
        component_scores["wave"] = round(wave_risk, 2)
        
        # 2. Wind risk (based on max wind speed)
        wind_risk = self._calc_wind_risk(environmental_conditions.max_wind_speed)
        component_scores["wind"] = round(wind_risk, 2)
        
        # 3. Current risk (based on current speed)
        current_risk = self._calc_current_risk(environmental_conditions.current_speed)
        component_scores["current"] = round(current_risk, 2)
        
        # 4. Hazard risk
        hazard_risk = self._calc_hazard_risk(active_hazards or [])
        component_scores["hazard"] = round(hazard_risk, 2)
        
# 5. Geofence risk
        geofence_risk = self._calc_geofence_risk(geofence_violations or [])
        component_scores["geofence"] = round(geofence_risk, 2)

        # Hard constraints are authoritative and computed before the weighted
        # score so they can force the final level regardless of ML estimates.
        constraints, constraint_reasons = self._evaluate_hard_constraints(
            hard_constraints or {})
        component_scores["hard_constraint"] = 1.0 if constraints else 0.0

        # Weighted overall score
        weights = {
            "wave": 0.35,
            "wind": 0.30,
            "current": 0.15,
            "hazard": 0.13,
            "geofence": 0.02,
            "hard_constraint": 0.05,
        }

        overall_score = sum(
            weights[k] * component_scores[k]
            for k in weights.keys()
            if k in component_scores
        )
        overall_score = round(overall_score, 2)

        # Determine risk level
        risk_level = self._score_to_risk_level(overall_score)

        # Hard constraint wins: machine scores can never lower it.
        forced_elevated = False
        if constraints and risk_level != "elevated":
            risk_level = "elevated"
            overall_score = max(overall_score, 0.75)
            forced_elevated = True

        # Generate reasoning
        reasoning_parts = []
        if forced_elevated:
            reasoning_parts.append(
                "HARD CONSTRAINT: active restricted area(s) / high-severity "
                "warning(s) override environmental scoring")
        reasoning_parts.extend(constraint_reasons)
        if wave_risk > 0.5:
            reasoning_parts.append(f"Wave risk: {wave_risk:.0%}")
        if wind_risk > 0.5:
            reasoning_parts.append(f"Wind risk: {wind_risk:.0%}")
        if current_risk > 0.5:
            reasoning_parts.append(f"Current risk: {current_risk:.0%}")
        if hazard_risk > 0:
            reasoning_parts.append(f"Hazard risk: {hazard_risk:.0%}")
        if geofence_risk > 0:
            reasoning_parts.append(f"Geofence risk: {geofence_risk:.0%}")
        
        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "Standard marine conditions, low risk"
        
        # Calculate confidence based on data completeness
        confidence = self._calc_confidence(environmental_conditions, active_hazards)
        
        # Identify missing data
        missing_data = self._identify_missing_data(environmental_conditions, active_hazards)
        
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Record provenance
        self.provenance.record_execution(
            query_run_id=route_context.get("query_run_id", "") if route_context else "",
            agent_name="risk_engine",
            tool_name="assess_risk",
            input_bundles=[],
            output_bundles=[],  # No evidence bundles directly
            execution_time_ms=int(execution_time),
            status="success",
        )
        
        return RiskAssessment(
            overall_score=overall_score,
            risk_level=risk_level,
            component_scores=component_scores,
            reasoning=reasoning,
            confidence=confidence,
            missing_data=missing_data,
        )
    
    def assess(
        self,
        evidence: Optional[Dict[str, Any]] = None,
        hard: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Phase 5 composite, evidence-driven risk assessment.

        Deterministically combines the four authoritative layers:
          static restrictions + official dynamic restrictions + marine warnings
          + weather/sea-state environment.

        Levels:
          RESTRICTED  - an ACTIVE hard constraint exists (restricted area,
                        official dynamic restriction, or high/critical warning).
                        Authoritative: no score may downgrade it.
          UNKNOWN     - mandatory evidence is missing (we never guess).
          CRITICAL    - environment alone is extreme (score >= 0.80).
          HIGH_RISK   - significant environmental risk (score >= 0.55).
          CAUTION     - moderate risk or advisory-only proximity.
          SAFE        - mandatory evidence complete, clean and score < 0.30.
        """
        evidence = evidence or {}
        env = evidence.get("environmental_conditions") or {}
        hazards = evidence.get("active_hazards")

        restrictions = evidence.get("restrictions") or []
        warnings = evidence.get("warnings") or []
        dynamic_restrictions = evidence.get("dynamic_restrictions") or []
        geofences = evidence.get("geofences") or []

        def _active(items: List[Any]) -> List[Dict[str, Any]]:
            result = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("active") or item.get("status") == "active":
                    result.append(item)
            return result

        active_restrictions = _active(restrictions)
        active_dynamic = _active(dynamic_restrictions)
        active_warnings = [
            w for w in _active(warnings)
            if str(w.get("severity", "")).lower() in ("high", "critical")
        ]
        active_geofences = _active(geofences)

        reasons: List[str] = []
        components: Dict[str, float] = {}

        env_present = bool(
            env.get("max_wave_height") is not None or
            env.get("max_wind_speed") is not None or
            env.get("current_speed") is not None)
        conds = None
        if env_present:
            try:
                conds = EnvironmentalConditions(
                    max_wave_height=float(env.get("max_wave_height") or 0.0),
                    avg_wave_height=float(env.get("avg_wave_height") or 0.0),
                    max_wave_period=float(env.get("max_wave_period") or 0.0),
                    avg_wave_period=float(env.get("avg_wave_period") or 0.0),
                    max_wind_speed=float(env.get("max_wind_speed") or 0.0),
                    avg_wind_speed=float(env.get("avg_wind_speed") or 0.0),
                    current_speed=float(env.get("current_speed") or 0.0),
                    visibility=(
                        float(env["visibility"])
                        if env.get("visibility") is not None else None),
                    precipitation=float(env.get("precipitation") or 0.0),
                )
            except Exception:
                env_present = False

        if active_restrictions or active_dynamic or active_warnings:
            names = [r.get("area_name") or r.get("restriction_id") or r.get("name")
                     for r in active_restrictions + active_dynamic]
            names += [w.get("warning_id") for w in active_warnings]
            reasons.append(
                "RESTRICTED: active constraint(s): "
                + "; ".join(sorted({str(n) for n in names if n})[:5]))
            level = "RESTRICTED"
            components["hard_constraint"] = 1.0
            if conds is not None:
                components["wave"] = self._calc_wave_risk(conds.max_wave_height)
                components["wind"] = self._calc_wind_risk(conds.max_wind_speed)
                components["current"] = self._calc_current_risk(conds.current_speed)
            score = 1.0
        else:
            mandatory_complete = env_present and hazards is not None
            if not mandatory_complete:
                missing = []
                if not env_present:
                    missing.append("environmental_conditions")
                if hazards is None:
                    missing.append("active_hazards")
                reasons.append("UNKNOWN: mandatory evidence missing: "
                               + ", ".join(missing))
                return {
                    "level": "UNKNOWN",
                    "score": None,
                    "components": {},
                    "reasons": reasons,
                    "mandatory_evidence": missing,
                    "hard_constraint": False,
                }

            severity = 0.0
            for item in active_geofences:
                severity = max(
                    severity,
                    {"low": 0.1, "moderate": 0.2, "high": 0.4}.get(
                        str(item.get("severity", "")).lower(), 0.1))
            advisory = sum(
                1 for w in _active(warnings)
                if str(w.get("severity", "")).lower() in ("low", "moderate"))

            env_score = (self._calc_wave_risk(conds.max_wave_height) * 0.5
                         + self._calc_wind_risk(conds.max_wind_speed) * 0.35
                         + self._calc_current_risk(conds.current_speed) * 0.15)
            components["wave"] = round(self._calc_wave_risk(conds.max_wave_height), 2)
            components["wind"] = round(self._calc_wind_risk(conds.max_wind_speed), 2)
            components["current"] = round(self._calc_current_risk(conds.current_speed), 2)
            components["hazard"] = round(
                self._calc_hazard_risk([h for h in hazards or []
                                        if isinstance(h, dict)]), 2)
            components["geofence"] = severity
            score = env_score + severity + (0.15 if advisory else 0.0)
            score = round(max(0.0, min(1.0, score)), 3)

            if score >= 0.80:
                level = "CRITICAL"
            elif score >= 0.55:
                level = "HIGH_RISK"
            elif score >= 0.30 or advisory > 0 or severity > 0:
                level = "CAUTION"
            else:
                level = "SAFE"
            if score <= 0.30 and severity == 0 and advisory == 0:
                reasons.append("environment within safe operating windows")
            elif advisory > 0:
                reasons.append(
                    f"{advisory} active advisory warning(s); conditions "
                    "bear watching")
            elif severity > 0:
                reasons.append("vessel near a static geofence boundary")

        freshness = evidence.get("freshness")
        if isinstance(freshness, dict):
            overall = freshness.get("overall")
            if overall in ("stale", "expired"):
                reasons.append(f"source freshness {overall}; treat as degraded")
            elif overall == "aging":
                reasons.append("source data aging; refresh recommended")

        return {
            "level": level,
            "score": score if level != "RESTRICTED" else None,
            "components": components,
            "reasons": reasons,
            "mandatory_evidence": [],
            "hard_constraint": level == "RESTRICTED",
        }

    def _calc_wave_risk(self, max_wave_height: float) -> float:
        """Calculate wave risk score (0-1, higher = more risk)."""
        if max_wave_height <= 1.0:
            return 0.1  # Low risk
        elif max_wave_height <= 2.0:
            return 0.3  # Moderate risk
        elif max_wave_height <= 3.0:
            return 0.6  # High risk
        elif max_wave_height <= 5.0:
            return 0.8  # Very high risk
        else:
            return 1.0  # Extreme risk
    
    def _calc_wind_risk(self, max_wind_speed: float) -> float:
        """Calculate wind risk score (0-1, higher = more risk)."""
        if max_wind_speed <= 10.0:
            return 0.1  # Low risk
        elif max_wind_speed <= 20.0:
            return 0.3  # Moderate risk
        elif max_wind_speed <= 30.0:
            return 0.6  # High risk
        elif max_wind_speed <= 40.0:
            return 0.8  # Very high risk
        else:
            return 1.0  # Extreme risk
    
    def _calc_current_risk(self, current_speed: float) -> float:
        """Calculate current risk score (0-1, higher = more risk)."""
        if current_speed <= 0.5:
            return 0.1  # Low risk
        elif current_speed <= 1.0:
            return 0.3  # Moderate risk
        elif current_speed <= 1.5:
            return 0.6  # High risk
        elif current_speed <= 2.0:
            return 0.8  # Very high risk
        else:
            return 1.0  # Extreme risk
    
    def _calc_hazard_risk(self, active_hazards: List[Any]) -> float:
        """Calculate hazard risk based on active hazards."""
        if not active_hazards:
            return 0.0
        
        # Weight by severity
        severity_weights = {
            HazardSeverity.LOW: 0.2,
            HazardSeverity.MODERATE: 0.5,
            HazardSeverity.HIGH: 0.8,
            HazardSeverity.CRITICAL: 1.0,
        }
        
        max_weight = max(
            (severity_weights.get(hazard.severity, 0) for hazard in active_hazards),
            default=0
        )
        
        return max_weight

    def _calc_geofence_risk(self, geofence_violations: List[Any]) -> float:
        """Calculate geofence risk based on violations."""
        if not geofence_violations:
            return 0.0

        # Geofence violations are significant
        return 0.5

    def _evaluate_hard_constraints(self, hard_constraints: Dict[str, Any]):
        """Decide whether any hard constraint forces an elevated final level.

        Ground truth comes from database rows, never from machine estimates:
        an active restricted area or an active warning with severity
        high/critical is authoritative.
        """
        active_restrictions = int(hard_constraints.get("active_restrictions") or 0)
        high_warnings = int(hard_constraints.get("high_severity_warnings") or 0)
        reasons: List[str] = []

        restriction_details = hard_constraints.get("restrictions") or []
        for item in restriction_details:
            name = item.get("area_name") if isinstance(item, dict) else str(item)
            reasons.append(f"Inside restricted area: {name}")
        warning_details = hard_constraints.get("warnings") or []
        for item in warning_details:
            name = item.get("warning_id") if isinstance(item, dict) else str(item)
            severity = item.get("severity") if isinstance(item, dict) else "high"
            reasons.append(f"Active warning {name} ({severity})")

        forced = active_restrictions > 0 or high_warnings > 0
        if forced and not reasons:
            reasons.append(
                f"Active hard constraint(s): {active_restrictions} restricted area(s), "
                f"{high_warnings} high-severity warning(s)")
        return forced, reasons
    
    def _score_to_risk_level(self, score: float) -> str:
        """Convert numeric score to risk level string."""
        if score >= 0.7:
            return "elevated"
        elif score >= 0.4:
            return "moderate"
        elif score > 0:
            return "low"
        else:
            return "unavailable"
    
    def _calc_confidence(
        self,
        environmental_conditions: EnvironmentalConditions,
        active_hazards: Optional[List[Any]] = None,
    ) -> float:
        """Calculate confidence score for the risk assessment."""
        confidence = 0.8  # Base confidence
        
        # Reduce confidence if data is limited
        if environmental_conditions.max_wave_height == 0:
            confidence -= 0.2
        if environmental_conditions.max_wind_speed == 0:
            confidence -= 0.2
        if environmental_conditions.current_speed == 0:
            confidence -= 0.1
        
        # Adjust based on hazard data availability
        if active_hazards is not None:
            if len(active_hazards) == 0:
                confidence += 0.1  # No hazards is good news
        
        return max(0.1, min(1.0, confidence))
    
    def _identify_missing_data(
        self,
        environmental_conditions: EnvironmentalConditions,
        active_hazards: Optional[List[Any]] = None,
    ) -> List[str]:
        """Identify what data is missing from the risk assessment."""
        missing = []
        
        if environmental_conditions.max_wave_height is None or environmental_conditions.max_wave_height == 0:
            missing.append("wave height data")
        if environmental_conditions.max_wind_speed is None or environmental_conditions.max_wind_speed == 0:
            missing.append("wind speed data")
        if environmental_conditions.current_speed is None or environmental_conditions.current_speed == 0:
            missing.append("current speed data")
        
        if active_hazards is None:
            missing.append("hazard data")
        
        return missing


# Global risk engine instance
_risk_engine: Optional[RiskEngine] = None


def get_risk_engine() -> RiskEngine:
    global _risk_engine
    if _risk_engine is None:
        _risk_engine = RiskEngine()
    return _risk_engine