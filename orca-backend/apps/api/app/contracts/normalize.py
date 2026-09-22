# Normalizer: internal orchestrator dict -> canonical OrchestrationResponse.
#
# This is the ONLY place the public contract is derived from the internal
# response.  It is additive and defensive: unknown/missing internal fields
# never crash the boundary - they degrade to a safe UNKNOWN/empty value rather
# than leaking an internal error to the frontend.
from typing import Any, Dict, List, Optional

from app.contracts.orchestration import OrchestrationRequest
from app.contracts.response import (
    AlertItem, ChartSeries, ConfidenceContract, ConfidenceLevel, EvidenceItem,
    EvidenceType, MapContract, NeedsInputContract, OrchestrationResponse,
    ProvenanceItem, Question, RiskClassification, RiskContract, RouteContract,
    RunStatus,
)
from app.contracts.versions import contract_meta


def _status_map(internal: Optional[str]) -> RunStatus:
    value = (internal or "").lower()
    mapping = {
        "success": RunStatus.COMPLETED,
        "completed": RunStatus.COMPLETED,
        "needs_input": RunStatus.NEEDS_INPUT,
        "partial": RunStatus.PARTIAL,
        "degraded": RunStatus.DEGRADED,
        "error": RunStatus.FAILED,
        "failed": RunStatus.FAILED,
        "timeout": RunStatus.TIMEOUT,
        "aborted": RunStatus.FAILED,
        "unavailable": RunStatus.DEGRADED,
        "invalid": RunStatus.FAILED,
    }
    return mapping.get(value, RunStatus.COMPLETED if value == "success" else RunStatus.COMPLETED)


def _risk_classification(internal_risk: Optional[Dict[str, Any]]) -> RiskClassification:
    if not internal_risk:
        return RiskClassification.UNKNOWN
    level = str(internal_risk.get("level") or "").lower()
    hard = bool(internal_risk.get("hard_constraint"))
    status = str(internal_risk.get("status") or "").lower()
    if hard or status == "restricted":
        return RiskClassification.RESTRICTED
    if level == "low":
        return RiskClassification.CAUTION
    if level in ("moderate", "medium"):
        return RiskClassification.CAUTION
    if level in ("high", "elevated"):
        return RiskClassification.HIGH_RISK
    if level in ("critical",):
        return RiskClassification.CRITICAL
    if status == "insufficient_data":
        return RiskClassification.UNKNOWN
    return RiskClassification.UNKNOWN


def _confidence_level(label: Optional[str]) -> ConfidenceLevel:
    mapping = {
        "very_low": ConfidenceLevel.VERY_LOW,
        "low": ConfidenceLevel.LOW,
        "medium": ConfidenceLevel.MEDIUM,
        "high": ConfidenceLevel.HIGH,
        "very_high": ConfidenceLevel.VERY_HIGH,
    }
    return mapping.get((label or "medium").lower(), ConfidenceLevel.MEDIUM)


def _default_risk_reason(classification: RiskClassification,
                         internal_risk: Optional[Dict[str, Any]]) -> str:
    if classification == RiskClassification.RESTRICTED:
        return "An active restriction or hard constraint binds this request."
    status = str((internal_risk or {}).get("status") or "")
    if status == "insufficient_data":
        return "Risk could not be assessed from the available data."
    return classification.value


_EVIDENCE_TYPE_MAP = {
    "OBSERVATION": EvidenceType.OBSERVATION,
    "FORECAST": EvidenceType.FORECAST,
    "ADVISORY": EvidenceType.ADVISORY,
    "RESTRICTION": EvidenceType.RESTRICTION,
    "MODEL": EvidenceType.MODEL,
    "DOCUMENT": EvidenceType.DOCUMENT,
    "DERIVED": EvidenceType.DERIVED,
}


def normalize_evidence(records: List[Any]) -> List[EvidenceItem]:
    out: List[EvidenceItem] = []
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        out.append(EvidenceItem(
            id=str(rec.get("id", "")),
            type=_EVIDENCE_TYPE_MAP.get(str(rec.get("type", "")).upper(), EvidenceType.DERIVED),
            source=str(rec.get("source", "")),
            source_reference=str(rec.get("source_reference", "")),
            timestamp=rec.get("timestamp"),
            validity=rec.get("validity"),
            claim=str(rec.get("claim", "")),
            value=rec.get("value"),
            unit=rec.get("unit"),
            confidence=rec.get("confidence"),
        ))
    return out[:30]


def normalize_provenance(provenance: Dict[str, Any]) -> List[ProvenanceItem]:
    items: List[ProvenanceItem] = []
    sources = (provenance or {}).get("sources") or []
    for src in sources[:20]:
        items.append(ProvenanceItem(source=str(src)))
    freshness_map = {
        "fresh": "fresh",
        "stale": "stale",
        "aging": "fresh",
        "recent": "fresh",
        "unknown": "unknown",
        "expired": "stale",
    }
    overall = str(((provenance or {}).get("freshness") or {}).get("overall", "unknown")).lower()
    if not items and provenance:
        items.append(ProvenanceItem(
            source=str((provenance or {}).get("strategy", "backend")),
            freshness=freshness_map.get(overall, "unknown")))
    if items:
        items[0].freshness = freshness_map.get(overall, "unknown")
    return items


def _normalize_charts(charts: Any) -> List[ChartSeries]:
    out: List[ChartSeries] = []
    if not isinstance(charts, list):
        return out
    for chart in charts:
        if not isinstance(chart, dict):
            continue
        out.append(ChartSeries(
            id=str(chart.get("id", chart.get("variable", ""))),
            name=str(chart.get("name", chart.get("title", ""))),
            unit=str(chart.get("unit", "")),
            source=str(chart.get("source", "")),
            timestamps=[str(p.get("timestamp")) for p in (chart.get("series") or [])
                        if p.get("timestamp")],
            values=[p.get("value") for p in (chart.get("series") or [])
                    if "value" in p],
            validity=chart.get("metadata", {}).get("freshness") if isinstance(
                chart.get("metadata"), dict) else None,
            quality=chart.get("status"),
            confidence=chart.get("metadata", {}).get("confidence") if isinstance(
                chart.get("metadata"), dict) and chart.get("metadata", {}).get("confidence") is not None else None,
        ))
    return out


def _normalize_alerts(alerts: Any) -> List[AlertItem]:
    out: List[AlertItem] = []
    if not isinstance(alerts, list):
        return out
    type_map = {
        "cyclone": "CYCLONE", "lightning": "LIGHTNING", "high_waves": "WAVE",
        "strong_wind": "WEATHER", "marine_warning": "WEATHER",
        "restriction": "RESTRICTION", "geofence": "GEOFENCE",
        "route": "ROUTE", "data_quality": "DATA_QUALITY",
    }
    for alert in alerts[:30]:
        if not isinstance(alert, dict):
            continue
        atype = type_map.get(str(alert.get("type", "")).lower(), "DATA_QUALITY")
        out.append(AlertItem(
            id=str(alert.get("alert_id", "")),
            type=atype,
            severity=str(alert.get("severity", "info")),
            title=str(alert.get("title", "")),
            message=str(alert.get("message", "")),
            location=alert.get("location") if isinstance(alert.get("location"), dict) else None,
            geometry=alert.get("geometry") if isinstance(alert.get("geometry"), dict) else None,
            valid_from=alert.get("valid_from"),
            valid_to=alert.get("valid_until", alert.get("valid_to")),
            source=str(alert.get("source", "")),
            confidence=alert.get("confidence"),
            evidence=alert.get("evidence") if isinstance(alert.get("evidence"), list) else [],
            status=str(alert.get("status", "active")),
        ))
    return out


def _normalize_route(route: Any) -> RouteContract:
    if not isinstance(route, dict):
        return RouteContract()
    blocked = bool(route.get("blocked"))
    geometry = route.get("geometry")
    reasons = [str(r) for r in (route.get("blocking_reasons") or [])]
    return RouteContract(
        status="blocked" if blocked else ("selected" if geometry else "none"),
        selected_geometry=geometry if isinstance(geometry, dict) else None,
        distance_km=route.get("distance_km"),
        risk=_risk_classification({"level": route.get("risk")}).value,
        blocked=blocked,
        blocking_reasons=reasons,
        alternatives=route.get("alternatives") if isinstance(route.get("alternatives"), list) else [],
        evidence=route.get("evidence") if isinstance(route.get("evidence"), list) else [],
    )


def normalize_response(internal: Dict[str, Any],
                       request: Optional[OrchestrationRequest] = None) -> OrchestrationResponse:
    internal = internal or {}
    status = _status_map(internal.get("status"))
    risk_internal = internal.get("risk") if isinstance(internal.get("risk"), dict) else None
    classification = _risk_classification(risk_internal)

    outputs = internal.get("outputs") if isinstance(internal.get("outputs"), dict) else {}
    maps = outputs.get("maps") if isinstance(outputs.get("maps"), dict) else {}
    route_out = outputs.get("route")

    needs = NeedsInputContract()
    if status == RunStatus.NEEDS_INPUT:
        needs = NeedsInputContract(questions=[
            Question(id="location", type="location",
                     question=str(internal.get("message") or
                                  "What location should I use?"))])

    confidence = internal.get("confidence") if isinstance(internal.get("confidence"), dict) else {}
    error = None
    if status in (RunStatus.FAILED, RunStatus.TIMEOUT):
        notes = internal.get("notes") if isinstance(internal.get("notes"), dict) else {}
        error_code = "INTERNAL_ERROR"
        if status == RunStatus.TIMEOUT:
            error_code = "ORCHESTRATION_TIMEOUT"
        error = {
            "code": error_code,
            "message": str(internal.get("message") or "orchestration failed"),
            "retryable": True,
            "run_id": internal.get("run_id") or internal.get("request_id") or "",
            "detail": notes.get("error") if notes.get("error") else None,
        }

    provenance_internal = internal.get("provenance") if isinstance(internal.get("provenance"), dict) else {}

    return OrchestrationResponse(
        request_id=str(internal.get("request_id", "")),
        run_id=str(internal.get("run_id") or internal.get("request_id", "")),
        session_id=request.session_id if request else internal.get("conversation_id"),
        status=status,
        language=str(internal.get("language") or "en"),
        answer=str(internal.get("answer") or internal.get("message") or ""),
        confidence=ConfidenceContract(
            score=float(confidence.get("score", 0.5)),
            level=_confidence_level(confidence.get("label")),
            basis=[str(b) for b in (confidence.get("basis") or [])],
        ),
        risk=RiskContract(
            classification=classification,
            reason=_default_risk_reason(classification, risk_internal) or
                   str((risk_internal or {}).get("status") or ""),
            hard_constraint=bool((risk_internal or {}).get("hard_constraint")),
            assessed=bool((risk_internal or {}).get("assessed", True)),
        ),
        needs_input=needs,
        evidence=normalize_evidence(internal.get("evidence") or []),
        provenance=normalize_provenance(provenance_internal),
        limitations=[str(l) for l in (internal.get("limitations") or [])],
        map=MapContract(
            features=[f for f in (maps.get("features") or []) if isinstance(f, dict)],
            generated_at=maps.get("generated_at"),
        ),
        charts=_normalize_charts(outputs.get("charts")),
        alerts=_normalize_alerts(outputs.get("alerts")),
        route=_normalize_route(route_out),
        execution={
            "intent": internal.get("intent"),
            "tool_calls": internal.get("tool_calls"),
            "duration_ms": internal.get("duration_ms"),
            "phase_timings": internal.get("phase_timings"),
            "verification": internal.get("verification"),
            "freshness": internal.get("freshness"),
            "notes": internal.get("notes"),
        },
        error=error,
    )
