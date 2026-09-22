# Response synthesis (Phase 4 / Phase 6).
#
# Everything surfaced in the answer is read from the executor's evidence -
# the same values the verifier traced.  Safety guidance is derived from the
# risk profile's hard constraint flag, never from a fabricated verdict.
#
# Phase 6 adds a canonical response contract: every channel (chat/map/chart/
# alert) renders from the SAME execution evidence via the shared builders, the
# operational phrasing is localized deterministically, and confidence/risk/
# provenance/limitations are computed - never predicted.
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.orchestration.models import ExecutionResult, Intent, IntentName
from app.services.alert_model import build_alerts
from app.services.chart_payload import build_chart_payload
from app.services.evidence_helpers import risk_level
from app.services.localization import localize_response
from app.services.map_payload import build_map_payload

_LABELS = {
    "low": "LOW",
    "moderate": "MODERATE",
    "elevated": "ELEVATED",
    "unavailable": "UNAVAILABLE",
}

# Phase 7: canonical safety vocabulary.  A hard constraint is ALWAYS
# "restricted" regardless of the engine level; anything unassessed/unavailable
# is "insufficient_data".  The platform deliberately NEVER certifies "safe":
# a healthy analytics "low" risk is still presented as "caution", so no valid
# response path can claim a false SAFE verdict.
_SAFETY_STATUS = {
    "elevated": "high_risk",
    "high_risk": "high_risk",
    "critical": "critical",
    "moderate": "caution",
    "caution": "caution",
    "low": "caution",
    "unavailable": "insufficient_data",
    "unknown": "insufficient_data",
}


def _safety_status(payload: Dict[str, Any]) -> str:
    level = str(payload.get("level") or "unknown").lower()
    if payload.get("hard_constraint") or level == "restricted":
        return "restricted"
    return _SAFETY_STATUS.get(level, "insufficient_data")


def _all_dicts(evidence: Dict[str, Any]):
    """Yield every dict one level deep in the evidence (handler bundles often
    nest per-tool output under the task's primary tool key)."""
    for value in evidence.values():
        yield value if isinstance(value, dict) else {}
        if isinstance(value, dict):
            for sub in value.values():
                if isinstance(sub, dict) or isinstance(sub, list):
                    if isinstance(sub, list):
                        for item in sub:
                            if isinstance(item, dict):
                                yield item
                    else:
                        yield sub


def _unwrap(value: Dict[str, Any]) -> Dict[str, Any]:
    if "data" in value and isinstance(value.get("data"), dict):
        return value["data"]
    return value


def _find(evidence: Dict[str, Any], *keys: str) -> Dict[str, Any]:
    """Locate a dict payload at the top level or nested one level deep."""
    for key in keys:
        for bucket in _all_dicts(evidence):
            if isinstance(bucket, dict) and key in bucket \
                    and isinstance(bucket[key], dict):
                return _unwrap(bucket[key])
        value = evidence.get(key)
        if isinstance(value, dict):
            return _unwrap(value)
    return {}


def _find_list(evidence: Dict[str, Any], key: str) -> List[Any]:
    for bucket in _all_dicts(evidence):
        if isinstance(bucket, dict) and key in bucket \
                and isinstance(bucket[key], list):
            return bucket[key]
    value = evidence.get(key)
    return value if isinstance(value, list) else []


def _fused_lines(payload: Dict[str, Any]) -> List[str]:
    variables = payload.get("variables") or {}
    lines = [f"{name}={value}" for name, value in sorted(variables.items())]
    if payload.get("missing"):
        lines.append("missing: " + ", ".join(payload["missing"]))
    if payload.get("limitations"):
        lines.append("limitations: " + "; ".join(payload["limitations"]))
    return lines or ["no marine state variables available"]


def _fused_freshness(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Read the freshness envelope from the fused-state evidence (never invents)."""
    fused = _find(evidence, "fused_state", "marine.get_fused_state")
    freshness = fused.get("freshness") if isinstance(fused, dict) else None
    if isinstance(freshness, dict):
        return freshness
    payloads = [p for p in _all_dicts(evidence)
                if isinstance(p, dict) and p.get("freshness")]
    if payloads:
        return payloads[0]["freshness"]
    return {"overall": "unknown", "threshold_seconds": None, "per_source": {}}


def _evidence_graph(intent: Intent, execution: ExecutionResult) -> Dict[str, Any]:
    """Compact provenance graph: numeric claims -> tool -> source/freshness.

    Every node is drawn from actual tool-returned evidence; nothing fabricated.
    """
    from app.services.evidence_graph import EvidenceGraph

    def _numbers(value: Any, prefix: str):
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            yield prefix, value
        elif isinstance(value, dict):
            for k, v in value.items():
                yield from _numbers(v, f"{prefix}:{k}" if prefix else str(k))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from _numbers(item, f"{prefix}[{index}]")

    graph = EvidenceGraph()
    try:
        claims = []
        for key, payload in execution.evidence.items():
            if not isinstance(payload, dict):
                continue
            for name, value in payload.items():
                if name.startswith("_") or isinstance(value, bool):
                    continue
                label = f"{key}:{name}"
                for claim_name, num in _numbers(value, label):
                    claims.append({"name": claim_name, "value": num})
        freshness = _fused_freshness(execution.evidence)
        overall = freshness.get("overall", "unknown")
        for claim in claims[:40]:
            graph.add_claim(
                claim=claim["name"],
                value=claim["value"],
                unit="(tool output)",
                source="tool_output",
                freshness=overall,
                verified=True,
            )
    except Exception:  # noqa: BLE001 - the graph is best-effort, never fatal
        return {"nodes": [], "sources": []}
    return graph.to_dict()


def _citation_lines(chunks: List[Any]) -> List[str]:
    lines = []
    for chunk in chunks or []:
        source = chunk.get("source_reference") or chunk.get("document") or "n.a."
        mode = chunk.get("retrieval_source") or "n.a."
        lines.append(f"[citation] {source} ({mode})")
    return lines


def _safety_guidance(payload: Dict[str, Any]) -> str:
    level = (payload.get("level") or "unavailable").lower()
    if payload.get("hard_constraint"):
        return ("ELEVATED RISK (hard constraint): an active warning or "
                "restricted area applies. Avoid the area and follow official "
                "warnings; do not proceed.")
    return f"Risk level {_LABELS.get(level, level.upper())} for this point."


def _route_output(intent: Intent, evidence: Dict[str, Any]) -> Any:
    """Phase 6 route object: deterministic risk score from the Phase 5 route
    evaluator (hard constraint blocks the route regardless of score)."""
    if intent.name != IntentName.ROUTE or not intent.route:
        return None
    from app.services.route_evaluator import evaluate_route

    restrictions = _find(evidence, "restrictions_near_route",
                         "geospatial.restrictions_near_route")
    data = restrictions.get("data") if isinstance(restrictions.get("data"), dict) \
        else restrictions
    intersections = data.get("intersections") if isinstance(data, dict) else []
    dynamic = []
    for dyn in _find_list(evidence, "dynamic_restrictions"):
        unwrapped = _unwrap(dyn) if isinstance(dyn, dict) else {}
        dynamic.extend(unwrapped.get("active_dynamic") or [])
    try:
        detail = evaluate_route(
            intent.route, restrictions=intersections, dynamic=dynamic).to_dict()
    except Exception:  # noqa: BLE001 - best effort, never fatal
        count = int(data.get("route_intersects_restricted_count") or 0)
        detail = {"intersection_count": count, "intersections": intersections,
                  "hard_constraint": count > 0, "blocked": count > 0,
                  "route_score": 0.0 if count > 0 else 1.0,
                  "recommended": count == 0, "basis": []}
    blocked = bool(detail.get("hard_constraint"))
    score = float(detail.get("route_score") or 0.0)
    return {
        "kind": "route",
        "waypoints": [list(p) for p in intent.route],
        "source": "user",
        "status": "blocked" if blocked
        else ("caution" if score < 0.6 else "clear"),
        "risk_score": 1.0 if blocked else round(max(0.0, 1.0 - score), 3),
        "recommended": bool(detail.get("recommended")),
        "length_km": detail.get("route_length_km"),
        "intersections": detail.get("intersections") or [],
        "basis": detail.get("basis") or [],
    }


def _outputs(intent: Intent, evidence: Dict[str, Any],
             language: str) -> Dict[str, Any]:
    """Phase 6 structured, machine-consumable artifacts derived ONLY from the
    evidence synthesis already rendered - never recomputed from user text."""
    maps = build_map_payload(intent, evidence, language)
    charts = build_chart_payload(intent, evidence, language)
    alerts = build_alerts(intent, evidence, language)
    return {
        "maps": maps,
        "charts": charts,
        "alerts": alerts,
        "route": _route_output(intent, evidence),
    }


def _compute_confidence(execution: ExecutionResult) -> Dict[str, Any]:
    """Deterministic response confidence: verifier outcome, completeness,
    freshness and failure count feed a fixed rule, not a model."""
    value = 1.0
    basis = []
    verification = execution.verification
    if verification is None:
        value -= 0.15
        basis.append("no verifier step in plan")
    elif verification.get("all_verified") is not True:
        value -= 0.35
        basis.append("verifier rejected claims")
    else:
        basis.append("all numeric claims verifier-traced")
    if not execution.evidence:
        value *= 0.4
        basis.append("no evidence produced")
    if execution.errors:
        value -= 0.30
        basis.append(f"{len(execution.errors)} failed task(s)")
    overall = str(_fused_freshness(execution.evidence).get("overall", "unknown"))
    penalty = {"fresh": 0.0, "recent": 0.05, "aging": 0.20, "stale": 0.50,
               "unknown": 0.60, "expired": 0.70}.get(overall.lower(), 0.60)
    value -= penalty
    if penalty:
        basis.append(f"freshness: {overall}")
    score = round(max(0.05, min(0.98, value)), 2)
    label = "high" if score >= 0.7 else ("medium" if score >= 0.4 else "low")
    return {"score": score, "label": label, "basis": basis[:6]}


def _risk_summary(execution: ExecutionResult) -> Dict[str, Any]:
    risk = _find(execution.evidence, "risk_profile", "analytics.risk_profile")
    if not risk:
        return {"level": "unknown", "hard_constraint": False, "assessed": False,
                "status": "insufficient_data"}
    return {"level": str(risk.get("level") or "unknown").lower(),
            "hard_constraint": bool(risk.get("hard_constraint")),
            "assessed": True,
            "status": _safety_status(risk)}


def _evidence_summary(execution: ExecutionResult) -> List[Dict[str, Any]]:
    records = []
    for key, payload in list(execution.evidence.items())[:12]:
        if not isinstance(payload, dict):
            continue
        data = payload.get("data") if isinstance(payload.get("data"), dict) \
            else payload
        if not isinstance(data, dict):
            continue
        for name, value in list(data.items())[:6]:
            if name.startswith("_") or isinstance(value, (dict, list, bool)):
                continue
            records.append({"claim": f"{name}={value}", "source": key})
    return records[:30]


def _provenance(intent: Intent, execution: ExecutionResult) -> Dict[str, Any]:
    fused = _find(execution.evidence, "fused_state", "marine.get_fused_state")
    sources = [str(s) for s in (fused.get("sources") or [])]
    search = _find(execution.evidence, "knowledge.search")
    retrieval = search.get("mode") if isinstance(search, dict) else None
    dynamic = _find(execution.evidence, "dynamic_restrictions",
                    "restriction.dynamic_active")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "freshness": _fused_freshness(execution.evidence),
        "verification": execution.verification,
        "retrieval_mode": retrieval,
        "dynamic_layer": "wired" if dynamic else "not_wired",
        "strategy": _plan_strategy(execution),
    }


def _limitations(intent: Intent, execution: ExecutionResult) -> List[str]:
    evidence = execution.evidence
    fused = _find(evidence, "fused_state", "marine.get_fused_state")
    limits = []
    missing = fused.get("missing") or []
    if missing:
        limits.append(f"{len(missing)} marine variable(s) unavailable: "
                      + ", ".join(str(v) for v in missing[:4]))
    for limitation in (fused.get("limitations") or [])[:3]:
        limits.append(str(limitation))
    if intent.name == IntentName.SAFETY:
        safety = _find(evidence, "marine_safety_check",
                       "safety.marine_safety_check")
        if not safety:
            limits.append("safety verdict unavailable: safety data not returned")
        if risk_level(evidence) == "unknown":
            limits.append("risk could not be assessed (UNKNOWN)")
    overall = _fused_freshness(evidence).get("overall", "unknown")
    if str(overall).lower() in ("stale", "expired"):
        limits.append(f"ocean observation data is {overall}")
    return limits[:6]


def synthesize(intent: Intent, execution: ExecutionResult,
               request_id: str = "", conversation_id: str = "") -> Dict[str, Any]:
    evidence = execution.evidence
    lines: List[str] = []
    sections: List[Dict[str, Any]] = []

    if execution.status == "aborted":
        lines.append("The request could not be completed; no agent responses "
                     "were produced.")
    elif execution.errors:
        lines.append("Partial result: some capability providers did not respond "
                     f"({len(execution.errors)} failed task(s)).")

    name = intent.name

    if name == IntentName.SAFETY:
        safety = _find(evidence, "marine_safety_check",
                       "safety.marine_safety_check")
        risk = _find(evidence, "risk_profile", "analytics.risk_profile")
        fused = _find(evidence, "fused_state", "marine.get_fused_state")
        if risk:
            sections.append({"title": "Risk profile",
                             "lines": [
                                 _safety_guidance(risk),
                                 f"Safety status: {_safety_status(risk).upper()}",
                                 *[f"  {s['variable']}: value={s['value']} "
                                   f"risk={_LABELS.get(str(s.get('risk')).lower(), s.get('risk'))}"
                                   for s in (risk.get("scores") or [])],
                             ]})
        if safety:
            suggested = safety.get("suggested", "")
            sections.append({"title": "Safety check",
                             "lines": [
                                 f"suggested: {suggested}",
                                 f"inside_restricted_area: "
                                 f"{safety.get('inside_restricted_area', False)}",
                             ]})
        if fused:
            sections.append({"title": "Fused marine state",
                             "lines": _fused_lines(fused)})
        if name == IntentName.SAFETY and risk:
            lines.append(_safety_guidance(risk))
        else:
            lines.append("Safety verdict: data unavailable - do not assume a "
                         "safe condition.")

    elif name == IntentName.BRIEFING:
        fused = _find(evidence, "fused_state", "marine.get_fused_state")
        sections.append({"title": "Marine briefing",
                         "lines": _fused_lines(fused)})
        lines.append(f"Briefing prepared for "
                     f"{_point_label(intent)}.")

    elif name == IntentName.FISHING:
        favorability = _find(evidence, "favorability",
                             "analytics.favorability")
        fused = _find(evidence, "fused_state", "marine.get_fused_state")
        if favorability:
            lines.append(
                f"Favorability index: "
                f"{favorability.get('score', 'unavailable')} "
                f"(target: {favorability.get('target', 'fishing')})")
        sections.append({"title": "Fused marine state",
                         "lines": _fused_lines(fused)})

    elif name == IntentName.PFZ:
        pfz = _find(evidence, "pfz_nearest", "marine.pfz_nearest")
        candidates = pfz.get("candidates") or []
        potentials = [_unwrap(p) for p in _find_list(evidence, "potentials")]
        states = [_unwrap(s) for s in _find_list(evidence, "states")]
        if candidates:
            top = candidates[0]
            zone_line = (f"Nearest PFZ zone {top.get('zone_id')} "
                         f"{'contains' if top.get('inside') else 'at'} "
                         f"{top.get('distance_km')} km from the query point")
            sections.append({"title": "PFZ advisory (nearest)",
                             "lines": [
                                 zone_line,
                                 f"zone generated: {top.get('generated_at')}",
                                 f"valid until: {top.get('valid_until')}",
                                 f"suite: {top.get('suite')}",
                             ]})
            lines.append(zone_line)
        for potential in potentials[:1]:
            if potential.get("potential") is None:
                continue
            lines.append(
                f"Fishing potential at the zone: "
                f"{potential['potential']} ({potential.get('level')})")
            sections.append({
                "title": "Fishing potential",
                "lines": [
                    f"potential: {potential.get('potential')} "
                    f"[{potential.get('level')}]",
                    *[f"  {c.get('variable')}: value={c.get('value')} "
                      f"favorability={c.get('favorability')}"
                      for c in (potential.get("contributions") or [])],
                    f"caveat: {potential.get('caveat')}",
                ],
            })
        for index, state in enumerate(states[:1], start=1):
            sections.append({"title": "Zone marine state",
                             "lines": _fused_lines(state)})

    elif name == IntentName.PRODUCTIVITY:
        prod = _find(evidence, "productivity", "analytics.productivity")
        fused = _find(evidence, "fused_state", "marine.get_fused_state")
        if prod.get("productivity") is None:
            sections.append({
                "title": "Productivity",
                "lines": [prod.get("note", "insufficient real data")],
            })
        else:
            lines.append(
                f"Productivity index: {prod['productivity']} "
                f"({prod.get('label')})")
            sections.append({
                "title": "Productivity index",
                "lines": [
                    f"index: {prod['productivity']} [{prod.get('label')}]"
                    f" at lat {prod.get('location', {}).get('lat')}, "
                    f"lon {prod.get('location', {}).get('lon')}",
                    *[f"  {c.get('variable')}: value={c.get('value')} "
                      f"favorability={c.get('favorability')}"
                      for c in (prod.get("contributions") or [])],
                    f"caveat: {prod.get('note')}",
                ],
            })
        sections.append({"title": "Fused marine state",
                         "lines": _fused_lines(fused)})

    elif name == IntentName.ROUTE:
        restrictions = _find(evidence, "restrictions_near_route",
                             "geospatial.restrictions_near_route")
        endpoint_states = _find_list(evidence, "endpoint_states")
        data = restrictions.get("data") or restrictions
        sections.append({"title": "Route restrictions",
                         "lines": [
                             "no restricted-area intersections reported"
                             if data.get("route_intersects_restricted_count", 0) == 0
                             else (f"{data.get('route_intersects_restricted_count')} "
                                   "restricted-area intersection(s) on route"),
                         ]})
        for index, state in enumerate(endpoint_states[:2], start=1):
            sections.append({"title": f"Endpoint {index} marine state",
                             "lines": _fused_lines(state)})

    elif name == IntentName.SCENARIO:
        states = _find_list(evidence, "states")
        sections.append({"title": "Scenario comparison",
                         "lines": [
                             f"compared {len(states)} state(s)",
                         ]})
        for index, state in enumerate(states[:2], start=1):
            sections.append({"title": f"Option {index}",
                             "lines": _fused_lines(state)})

    elif name == IntentName.KNOWLEDGE:
        search = _find(evidence, "knowledge.search")
        chunks = search.get("chunks") or []
        sections.append({
            "title": "Knowledge summary",
            "lines": [
                f"retrieval mode: {search.get('mode', 'hybrid')}",
                *_citation_lines(chunks),
            ],
        })

    if not lines and not sections and execution.status == "success":
        lines.append("No synthesis was produced from the available evidence.")

    message = "\n".join(lines)
    response = {
        "request_id": request_id,
        "conversation_id": conversation_id if conversation_id else None,
        "intent": name.value,
        "language": intent.language,
        "status": execution.status,
        "message": message,
        "answer": message,
        "sections": sections,
        "verification": execution.verification,
        "tool_calls": execution.tool_calls,
        "duration_ms": execution.duration_ms,
        "phase_timings": {"intent_ms": 0, "plan_ms": 0, "execute_ms": 0,
                          "synthesize_ms": 0},
        "confidence": _compute_confidence(execution),
        "risk": _risk_summary(execution),
        "notes": {
            "strategy": _plan_strategy(execution),
            "merged_from_context": intent.merged_from_context,
        },
        "outputs": _outputs(intent, evidence, intent.language),
        "evidence": _evidence_summary(execution),
        "provenance": _provenance(intent, execution),
        "limitations": _limitations(intent, execution),
        "evidence_graph": _evidence_graph(intent, execution),
        "freshness": _fused_freshness(evidence),
    }
    return localize_response(response, intent.language)


def _point_label(intent: Intent) -> str:
    if not intent.location:
        return "the requested point"
    return f"lat {intent.location['lat']}, lon {intent.location['lon']}"


def _plan_strategy(execution: ExecutionResult) -> str:
    return "capability_matrix"