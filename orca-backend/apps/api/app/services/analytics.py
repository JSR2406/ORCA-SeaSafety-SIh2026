# AnalyticsService - descriptive marine analytics over REAL stored observations.
#
# Scope discipline: nothing here predicts catch or asserts accuracy that was
# never measured.  What it does:
#   * descriptive_stats - plain summary statistics over returned rows;
#   * favorability_index - a transparent, rule-based 0..1 favorability score
#     with an explicit per-variable contribution and rationale (thresholds
#     documented below; missing inputs are reported, never guessed);
#   * risk_profile - per-variable risk ratings using the RiskEngine's real
#     thresholds; active warnings/restricted areas are hard constraints and
#     force "elevated";
#   * scenario_comparison - descriptive differences across fused states.
import math
from statistics import fmean, stdev
from typing import Any, Dict, List, Optional

from app.services.marine_fusion import FusedMarineState

# Weights + ideal ("best") bands per target. Favorability decays linearly from
# the ideal band to 0 at the zero band, outside which it is 0.
FISHING_BANDS = {
    "sst_c":         (0.30, (25.0, 30.0), 21.0, 34.0),
    "chlorophyll":   (0.25, (0.15, 1.00), 0.02, 3.00),
    "wave_height_m": (0.20, (0.00, 1.50), 0.00, 3.00),
    "wind_speed_ms": (0.15, (0.00, 8.00), 0.00, 20.0),
    "current_speed_ms": (0.10, (0.00, 0.80), 0.00, 1.80),
}
TRANSIT_BANDS = {
    "wave_height_m": (0.40, (0.00, 1.50), 0.00, 3.50),
    "wind_speed_ms": (0.30, (0.00, 10.0), 0.00, 25.0),
    "current_speed_ms": (0.20, (0.00, 1.00), 0.00, 2.00),
    "visibility_m":  (0.10, (8000, 20000), 0.00, 8000),
}
_TARGETS = {"fishing": FISHING_BANDS, "transit": TRANSIT_BANDS}


class AnalyticsService:
    """Descriptive analytics over real marine observations."""

    # ------------------------------------------------------------- descriptive
    @staticmethod
    def descriptive_stats(rows: List[Dict[str, Any]],
                          fields: List[str]) -> Dict[str, Dict[str, Any]]:
        """Summary statistics for numeric fields over real rows."""
        stats: Dict[str, Dict[str, Any]] = {}
        for field in fields:
            values = []
            for row in rows:
                if isinstance(row, dict):
                    value = row.get(field)
                    if isinstance(value, (int, float)):
                        values.append(float(value))
            if not values:
                stats[field] = {"count": 0, "mean": None, "min": None,
                                "max": None, "std": None}
                continue
            stats[field] = {
                "count": len(values),
                "mean": round(fmean(values), 3),
                "min": round(min(values), 3),
                "max": round(max(values), 3),
                "std": round(stdev(values), 3) if len(values) >= 2 else None,
            }
        return stats

    # ------------------------------------------------------------ favorability
    @staticmethod
    def _favorability(value: float, ideal, zero_lo: float, zero_hi: float) -> float:
        """Linear ramp: 1 inside ideal band, 0 at/beyond the zero band."""
        lo, hi = ideal
        if zero_lo <= value < lo:
            span = lo - zero_lo
            return round(min(1.0, (value - zero_lo) / span), 3) if span > 0 else 0.0
        if hi < value <= zero_hi:
            span = zero_hi - hi
            return round(max(0.0, 1.0 - (value - hi) / span), 3) if span > 0 else 0.0
        if lo <= value <= hi:
            return 1.0
        return 0.0

    def favorability_index(
        self,
        state: FusedMarineState,
        target: str = "fishing",
    ) -> Dict[str, Any]:
        """Transparent 0..1 favorability index for a target over present data.

        Only present variables contribute; the weighted average is normalized
        over the contributing weights so stringently documented.  If too few
        inputs are present the score stays None (no invented value).
        """
        bands = _TARGETS.get(target)
        if bands is None:
            return {"target": target, "available": False, "score": None,
                    "error": f"unknown target '{target}'"}
        contributions = []
        present_weights = 0.0
        weighted = 0.0
        missing = []
        for var, (weight, ideal, zero_lo, zero_hi) in bands.items():
            value = state.variables.get(var)
            if value is None:
                missing.append(var)
                continue
            f = self._favorability(float(value), ideal, zero_lo, zero_hi)
            contributions.append({
                "variable": var,
                "value": value,
                "weight": weight,
                "favorability": f,
                "rationale": self._rationale(var, float(value), f),
            })
            present_weights += weight
            weighted += weight * f

        min_inputs = math.ceil(len(bands) / 2)
        if len(contributions) < min_inputs:
            return {
                "target": target,
                "available": False,
                "score": None,
                "contributions": contributions,
                "missing_inputs": missing,
                "note": (f"insufficient real inputs ({len(contributions)} of "
                         f"{min_inputs} required); no score produced"),
            }
        score = round(weighted / present_weights, 3) if present_weights else None
        return {
            "target": target,
            "available": True,
            "score": score,
            "contributions": contributions,
            "missing_inputs": missing,
            "note": "weighted average of per-variable favorability over present "
                    "variables; descriptive, not a fisheries forecast",
        }

    @staticmethod
    def _rationale(var: str, value: float, fav: float) -> str:
        if fav >= 1.0:
            return f"{var}={value} within the ideal band"
        if fav <= 0.0:
            return f"{var}={value} outside the beneficial range"
        return f"{var}={value} partially favorable"

    # ---------------------------------------------------------------- risk
    def risk_profile(
        self,
        state: FusedMarineState,
        active_warnings: Optional[List[dict]] = None,
        active_restrictions: Optional[List[dict]] = None,
    ) -> Dict[str, Any]:
        """Per-variable risk ratings + hard-constraint handling."""
        from app.services.risk_engine import get_risk_engine

        engine = get_risk_engine()
        scores = []
        for var, calc in (("wave_height_m", engine._calc_wave_risk),
                          ("wind_speed_ms", engine._calc_wind_risk),
                          ("current_speed_ms", engine._calc_current_risk)):
            value = state.variables.get(var)
            if value is None:
                continue
            scores.append({"variable": var, "value": value, "risk": calc(value)})

        warnings = active_warnings or []
        restrictions = active_restrictions or []
        hard = bool(warnings or restrictions)

        if not scores and not hard:
            return {"level": "unavailable", "scores": [], "hard_constraint": False,
                    "reasoning": "No environmental or constraint data available"}
        if hard:
            reasons = [f"active warning {w.get('warning_id')}" for w in warnings]
            reasons += [f"restricted area {r.get('area_id')}" for r in restrictions]
            return {"level": "elevated", "scores": scores, "hard_constraint": True,
                    "reasoning": "HARD CONSTRAINT: " + "; ".join(reasons)}

        overall = round(sum(s["risk"] for s in scores) / len(scores), 3)
        return {
            "level": engine._score_to_risk_level(overall),
            "scores": scores,
            "hard_constraint": False,
            "reasoning": "average of present per-variable environmental risk",
        }

    # --------------------------------------------------------- divergence
    @staticmethod
    def scenario_comparison(states: List[FusedMarineState]) -> Dict[str, Any]:
        """Descriptive cross-location/cross-time differences among fused states."""
        if not states:
            return {"states": 0, "variables": []}
        profiles = [s.to_dict() for s in states]
        variables: Dict[str, List[Dict[str, Any]]] = {}
        for state in states:
            for var, value in state.variables.items():
                variables.setdefault(var, []).append({
                    "lat": state.lat, "lon": state.lon,
                    "data_time": (state.data_time.isoformat()
                                  if state.data_time else None),
                    "value": value,
                })
        result_vars = []
        for var, entries in variables.items():
            if len(entries) < 2:
                result_vars.append({"variable": var, "entries": entries,
                                    "min": None, "max": None, "range": None})
                continue
            values = [float(e["value"]) for e in entries
                      if isinstance(e["value"], (int, float))]
            if not values:
                result_vars.append({"variable": var, "entries": entries,
                                    "min": None, "max": None, "range": None})
                continue
            lo, hi = min(values), max(values)
            result_vars.append({"variable": var, "entries": entries,
                                "min": lo, "max": hi, "range": round(hi - lo, 3)})
        result_vars.sort(key=lambda v: v["variable"])
        return {"states": len(states), "profiles": profiles,
                "variables": result_vars}

    # -------------------------------------------------- fishing potential
    @staticmethod
    def _potential_label(score: float) -> str:
        if score >= 0.80:
            return "very_high"
        if score >= 0.60:
            return "high"
        if score >= 0.40:
            return "moderate"
        if score >= 0.20:
            return "low"
        return "none"

    def fishing_potential(self, state: FusedMarineState) -> Dict[str, Any]:
        """Transparent per-location fishing potential over present data.

        Reuses the documented fishing favorability bands and adds a small
        agreement boost only when SST and chlorophyll are BOTH inside their
        ideal bands (a satellite-inferred frontal/retention proxy).  The result
        is descriptive - it never claims measured catch or forecast skill.
        """
        fav = self.favorability_index(state, target="fishing")
        if not fav.get("available"):
            return {
                "location": {"lat": state.lat, "lon": state.lon},
                "potential": None,
                "level": None,
                "contributions": fav.get("contributions", []),
                "note": fav.get("note", "insufficient real inputs"),
            }
        score = float(fav["score"])
        sst = state.variables.get("sst_c")
        chlor = state.variables.get("chlorophyll")
        if (sst is not None and chlor is not None
                and 25.0 <= float(sst) <= 30.0
                and 0.15 <= float(chlor) <= 1.00):
            score = min(1.0, score + 0.05)
        score = round(score, 3)
        return {
            "location": {"lat": state.lat, "lon": state.lon},
            "potential": score,
            "level": self._potential_label(score),
            "contributions": fav.get("contributions", []),
            "caveat": "satellite-inferred potential, not a catch forecast",
        }

    @staticmethod
    def rank_candidates(results: List[Dict[str, Any]],
                        key: str = "potential") -> List[Dict[str, Any]]:
        """Rank several per-location results (best first); non-scores last."""
        scored = [r for r in results if r.get(key) is not None]
        unscored = [r for r in results if r.get(key) is None]
        scored.sort(key=lambda r: r[key], reverse=True)
        return scored + unscored

    # ------------------------------------------------------------ productivity
    PRODUCTIVITY_BANDS = {
        "chlorophyll": (0.45, (0.20, 2.00), 0.01, 6.00),
        "sst_c":       (0.30, (25.0, 30.0), 19.0, 33.0),
        "upwelling":   (0.25, (0.00, 0.80), 0.00, 1.00),
    }

    def productivity(self, state: FusedMarineState) -> Dict[str, Any]:
        """SRP productivity index from chlorophyll + SST + upwelling proxy.

        The upwelling proxy combines wind and current into 0..1; a missing
        proxy is simply not weighted in.  Thresholds map to
        oligotrophic / moderate / productive / highly_productive.
        """
        upwelling = None
        wind = state.variables.get("wind_speed_ms")
        curr = state.variables.get("current_speed_ms")
        if wind is not None:
            upwelling = min(1.0, (float(wind) / 12.0) * 0.6
                            + (float(curr) / 1.5 * 0.4) if curr is not None
                            else (float(wind) / 12.0) * 0.6)
        variables = dict(state.variables)
        if upwelling is not None:
            variables["upwelling"] = round(upwelling, 3)

        contributions = []
        present_weights = 0.0
        weighted = 0.0
        missing = []
        for var, (weight, ideal, zero_lo, zero_hi) in self.PRODUCTIVITY_BANDS.items():
            value = variables.get(var)
            if value is None:
                missing.append(var)
                continue
            fav = self._favorability(float(value), ideal, zero_lo, zero_hi)
            contributions.append({
                "variable": var,
                "value": value,
                "weight": weight,
                "favorability": fav,
                "rationale": self._rationale(var, float(value), fav),
            })
            present_weights += weight
            weighted += weight * fav

        required = len(self.PRODUCTIVITY_BANDS) - 1  # chlorophyll + SST minimum
        if len(contributions) < required or present_weights == 0:
            return {
                "location": {"lat": state.lat, "lon": state.lon},
                "productivity": None,
                "label": None,
                "contributions": contributions,
                "missing_inputs": missing,
                "note": (f"insufficient real inputs ({len(contributions)} of "
                         f"{required} required); no index produced"),
            }
        score = round(weighted / present_weights, 3)
        if score < 0.25:
            label = "oligotrophic"
        elif score < 0.50:
            label = "moderate"
        elif score < 0.75:
            label = "productive"
        else:
            label = "highly_productive"
        return {
            "location": {"lat": state.lat, "lon": state.lon},
            "productivity": score,
            "label": label,
            "contributions": contributions,
            "missing_inputs": missing,
            "note": "SRP index from chlorophyll + SST (+ upwelling proxy); "
                    "satellite-inferred, not a catch forecast",
        }


_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service