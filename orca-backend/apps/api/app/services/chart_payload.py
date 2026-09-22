# Phase 6 - chart payload builder.
#
# Charts are read from the same fused/analytics evidence synthesis renders:
# observation ("current/fused") series for marine variables.  Every point is
# {timestamp, value, unit, source, status}, labels are language-neutral, and no
# value is invented - a chart is only emitted for a variable the tools returned.
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.orchestration.models import Intent, IntentName
from app.services.evidence_helpers import find, find_list, fused_freshness, fused_source
from app.services.localization import t

VARIABLE_SPECS = {
    "sst_c": ("output.chart.sst", "deg C"),
    "chlorophyll": ("output.chart.chlorophyll", "mg/m3"),
    "wave_height_m": ("output.chart.wave_height", "m"),
    "wave_period_s": ("output.chart.wave_period", "s"),
    "wind_speed_ms": ("output.chart.wind", "m/s"),
    "current_speed_ms": ("output.chart.current", "m/s"),
}


def _obs_point(value: Any, unit: str, source: str, status: str,
               at: datetime) -> Dict[str, Any]:
    return {
        "timestamp": at.isoformat(),
        "value": value,
        "unit": unit,
        "source": source,
        "status": status,
    }


def build_chart_payload(intent: Intent, evidence: Dict[str, Any],
                        language: str = "en-IN",
                        at: datetime = None) -> List[Dict[str, Any]]:
    at = at or datetime.now(timezone.utc)
    charts: List[Dict[str, Any]] = []

    fused = find(evidence, "fused_state", "marine.get_fused_state")
    freshness = fused_freshness(evidence)
    overall = str(freshness.get("overall") or "fresh")
    source = fused_source(evidence)
    variable_status = "stale" if overall.lower() in ("stale", "expired") else "fresh"

    variables = fused.get("variables") if isinstance(fused, dict) else {}
    if isinstance(variables, dict):
        for name, (title_key, unit) in sorted(VARIABLE_SPECS.items()):
            value = variables.get(name)
            if value is None:
                continue
            charts.append({
                "type": "chart",
                "kind": "observation",
                "title": t(language, title_key),
                "unit": unit,
                "variable": name,
                "source": source,
                "status": variable_status,
                "series": [_obs_point(value, unit, source, variable_status, at)],
                "metadata": {
                    "aggregate": "fused",
                    "freshness": overall,
                },
            })

    if intent.name == IntentName.SAFETY:
        risk = find(evidence, "risk_profile", "analytics.risk_profile")
        risk_score = risk.get("point_risk_score")
        if risk_score is not None:
            charts.append({
                "type": "chart",
                "kind": "model_prediction",
                "title": t(language, "output.chart.marine_risk"),
                "unit": "score",
                "variable": "risk_score",
                "source": "analytics.risk_profile",
                "status": variable_status,
                "series": [_obs_point(risk_score, "score",
                                      "analytics.risk_profile",
                                      variable_status, at)],
                "metadata": {"level": risk.get("level")},
            })

    if intent.name == IntentName.PFZ:
        potentials = [p.get("data") if isinstance(p.get("data"), dict) else p
                      for p in find_list(evidence, "potentials")]
        for potential in potentials[:1]:
            if not isinstance(potential, dict) or potential.get("potential") is None:
                continue
            charts.append({
                "type": "chart",
                "kind": "model_prediction",
                "title": t(language, "output.chart.fishing_potential"),
                "unit": "score",
                "variable": "fishing_potential",
                "source": "analytics.fishing_potential",
                "status": variable_status,
                "series": [_obs_point(potential["potential"], "score",
                                      "analytics.fishing_potential",
                                      variable_status, at)],
                "metadata": {"level": potential.get("level")},
            })
    elif intent.name == IntentName.FISHING:
        favorability = find(evidence, "favorability", "analytics.favorability")
        score = favorability.get("score")
        if score is not None:
            charts.append({
                "type": "chart",
                "kind": "model_prediction",
                "title": t(language, "output.chart.fishing_potential"),
                "unit": "score",
                "variable": "favorability",
                "source": "analytics.favorability",
                "status": variable_status,
                "series": [_obs_point(score, "score", "analytics.favorability",
                                      variable_status, at)],
                "metadata": {"target": favorability.get("target")},
            })

    if intent.name == IntentName.PRODUCTIVITY:
        prod = find(evidence, "productivity", "analytics.productivity")
        if prod.get("productivity") is not None:
            charts.append({
                "type": "chart",
                "kind": "model_prediction",
                "title": t(language, "output.chart.productivity"),
                "unit": "index",
                "variable": "productivity",
                "source": "analytics.productivity",
                "status": variable_status,
                "series": [_obs_point(prod["productivity"], "index",
                                      "analytics.productivity",
                                      variable_status, at)],
                "metadata": {"label": prod.get("label")},
            })

    return charts