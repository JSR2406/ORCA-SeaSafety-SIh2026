# Phase 10 - contract fixtures (Part 33).
#
# Twelve canonical examples covering the full frontend-facing surface.  Each
# fixture is labeled "CONTRACT FIXTURE" and pairs a request with the internal
# orchestrator-style response dict plus the canonical contract assertions it
# must satisfy after normalization.  The same fixtures drive:
#   * JSON-Schema validation (every internal dict -> canonical response must
#     be a valid instance of the published OrchestrationResponse schema);
#   * backward-compatibility checks (legacy fields remain present);
#   * the frontend integration contract doc examples.
#
# Internal response shape mirrors app/orchestration/synthesis.synthesize().
from app.contracts.orchestration import (
    LocationSource, OrchestrationRequest, RouteRequest, ScenarioRequest,
    UserLocation)
from app.contracts.response import RiskClassification, RunStatus

FIXTURE_LABEL = "CONTRACT FIXTURE"


def _base_internal(**overrides):
    base = {
        "request_id": "fixture-run",
        "conversation_id": "conv-1",
        "intent": "pfz",
        "language": "en",
        "status": "success",
        "message": "",
        "answer": "",
        "sections": [],
        "verification": {"all_verified": True},
        "tool_calls": 3,
        "duration_ms": 120,
        "phase_timings": {},
        "confidence": {"score": 0.8, "label": "high", "basis": ["verifier"]},
        "risk": {"level": "low", "hard_constraint": False, "assessed": True,
                 "status": "ok"},
        "outputs": {"maps": {"type": "FeatureCollection", "features": [],
                             "generated_at": "2026-08-31T12:00:00Z"},
                    "charts": [], "alerts": [], "route": None},
        "evidence": [],
        "provenance": {"sources": [], "freshness": {"overall": "unknown"}},
        "limitations": [],
        "freshness": {"overall": "fresh"},
        "notes": {},
        "evidence_graph": {},
    }
    base.update(overrides)
    return base


FIXTURES = [
    # 01 - PFZ advisory (success + map)
    {
        "label": f"{FIXTURE_LABEL} 01 - PFZ advisory with map",
        "request": OrchestrationRequest(
            query="where is the PFZ near Kochi?",
            user_location=UserLocation(
                latitude=9.9, longitude=76.3, source=LocationSource.USER)),
        "internal": _base_internal(
            intent="pfz",
            message="Nearest PFZ zone 11 contains 12.4 km from the query point",
            answer="Nearest PFZ zone 11 is 12.4 km from your point.",
            confidence={"score": 0.81, "label": "high", "basis": ["fused"]},
            outputs={
                "maps": {"type": "FeatureCollection",
                         "features": [{"type": "Feature", "properties": {
                             "zone_id": "11", "kind": "pfz"}}],
                         "generated_at": "2026-08-31T12:00:00Z"},
                "charts": [], "alerts": [], "route": None}),
        "assert": {
            "status": RunStatus.COMPLETED,
            "risk.classification": RiskClassification.CAUTION,
            "confidence.level": "high",
            "map.features": 1,
            "evidence_present": False,
        },
    },

    # 02 - marine briefing (charts + provenance)
    {
        "label": f"{FIXTURE_LABEL} 02 - marine briefing with charts",
        "request": OrchestrationRequest(query="marine briefing for fishing trip"),
        "internal": _base_internal(
            intent="briefing",
            message="Briefing prepared for 10.0N 76.0E.",
            answer="SST 28.5C, wave height 1.2 m, wind 12 kn.",
            confidence={"score": 0.72, "label": "medium", "basis": ["fused"]},
            outputs={
                "maps": {"type": "FeatureCollection", "features": [],
                         "generated_at": "2026-08-31T12:00:00Z"},
                "charts": [{"id": "sst", "name": "Sea Surface Temp", "unit": "C",
                            "source": "fused_state",
                            "series": [{"timestamp": "2026-08-31T00:00:00Z",
                                        "value": 28.5}]}],
                "alerts": [], "route": None},
            evidence=[{"claim": "sst=28.5C", "source": "fused_state"}],
            provenance={"sources": ["incois", "argo"],
                        "freshness": {"overall": "fresh"}}),
        "assert": {
            "status": RunStatus.COMPLETED,
            "charts": 1,
            "provenance": 2,
            "evidence": 1,
        },
    },

    # 03 - safety assessment (HIGH_RISK, no hard constraint)
    {
        "label": f"{FIXTURE_LABEL} 03 - marine safety assessment",
        "request": OrchestrationRequest(query="is it safe to go out today?",
                                        language="en"),
        "internal": _base_internal(
            intent="safety",
            message="Safety status: HIGH_RISK. Do not assume a safe condition.",
            answer="HIGH_RISK: rough sea, swell over 3.5 m.",
            risk={"level": "high", "hard_constraint": False, "assessed": True,
                  "status": "warning"},
            verification={"all_verified": True},
            confidence={"score": 0.6, "label": "medium", "basis": ["verifier"]}),
        "assert": {
            "status": RunStatus.COMPLETED,
            "risk.classification": RiskClassification.HIGH_RISK,
            "risk.assessed": True,
        },
    },

    # 04 - hard restriction (RESTRICTED + route blocked)
    {
        "label": f"{FIXTURE_LABEL} 04 - active restriction (RESTRICTED)",
        "request": OrchestrationRequest(
            query="route from Kochi to Panambur",
            route_request=RouteRequest(
                origin_latitude=9.9, origin_longitude=76.3,
                destination_latitude=12.9, destination_longitude=74.8)),
        "internal": _base_internal(
            intent="route",
            message="Route A blocked: active restricted area.",
            answer="Route A is blocked by an active restricted area.",
            status="success",
            risk={"level": "critical", "hard_constraint": True,
                  "assessed": True, "status": "restricted"},
            confidence={"score": 0.9, "label": "high", "basis": ["restriction"]},
            outputs={
                "maps": {"type": "FeatureCollection", "features": [],
                         "generated_at": "2026-08-31T12:00:00Z"},
                "charts": [], "alerts": [],
                "route": {"blocked": True,
                          "blocking_reasons": ["restricted_area_IND-MH-01"],
                          "geometry": None, "alternatives": [],
                          "evidence": [{"rule": "GEO_ZONE_ACTIVE"}]}}),
        "assert": {
            "status": RunStatus.COMPLETED,
            "risk.classification": RiskClassification.RESTRICTED,
            "risk.hard_constraint": True,
            "route.status": "blocked",
            "route.blocked": True,
        },
    },

    # 05 - open route (route contract, not blocked)
    {
        "label": f"{FIXTURE_LABEL} 05 - open route selected",
        "request": OrchestrationRequest(
            query="safe route away from the cyclone",
            route_request=RouteRequest(
                origin_latitude=10.0, origin_longitude=76.0,
                destination_latitude=11.0, destination_longitude=77.0)),
        "internal": _base_internal(
            intent="route",
            message="Route B selected, 45.2 km.",
            answer="Route B is open, 45.2 km.",
            risk={"level": "low", "hard_constraint": False, "assessed": True,
                  "status": "ok"},
            outputs={
                "maps": {"type": "FeatureCollection", "features": [],
                         "generated_at": "2026-08-31T12:00:00Z"},
                "charts": [], "alerts": [],
                "route": {"blocked": False, "blocking_reasons": [],
                          "distance_km": 45.2,
                          "geometry": {"type": "LineString", "coordinates": [
                              [76.0, 10.0], [76.5, 10.5], [77.0, 11.0]]},
                          "alternatives": [], "evidence": []}}),
        "assert": {
            "status": RunStatus.COMPLETED,
            "risk.classification": RiskClassification.CAUTION,
            "route.status": "selected",
            "route.distance_km": 45.2,
        },
    },

    # 06 - productivity / fishing analytics
    {
        "label": f"{FIXTURE_LABEL} 06 - productivity forecast",
        "request": OrchestrationRequest(query="fishing productivity tomorrow"),
        "internal": _base_internal(
            intent="productivity",
            message="Productivity: 0.82 (high).",
            answer="Fishing potential is high (0.82).",
            outputs={"maps": {"type": "FeatureCollection", "features": [],
                              "generated_at": "2026-08-31T12:00:00Z"},
                     "charts": [{"id": "potential", "name": "Potential",
                                 "unit": "", "source": "productivity",
                                 "series": [{"timestamp": "2026-09-01T00:00:00Z",
                                             "value": 0.82}]}],
                     "alerts": [], "route": None}),
        "assert": {
            "status": RunStatus.COMPLETED,
            "charts": 1,
            "confidence.score": 0.8,
        },
    },

    # 07 - knowledge retrieval (document evidence)
    {
        "label": f"{FIXTURE_LABEL} 07 - knowledge retrieval with evidence",
        "request": OrchestrationRequest(query="what do guidance docs say about monsoons?"),
        "internal": _base_internal(
            intent="knowledge",
            message="Guidance: avoid offshore during peak monsoon days.",
            answer="Guidance recommends avoiding offshore trips on peak monsoon days.",
            risk={"level": "unknown", "hard_constraint": False,
                  "assessed": False, "status": "insufficient_data"},
            evidence=[{"claim": "peak monsoon advisories exist", "source": "knowledge.search",
                       "type": "DOCUMENT"}],
            provenance={"sources": ["knowledge.rag"],
                        "freshness": {"overall": "recent"}},
            verification={"all_verified": True}),
        "assert": {
            "status": RunStatus.COMPLETED,
            "evidence": 1,
            "provenance": 1,
            "risk.classification": RiskClassification.UNKNOWN,
        },
    },

    # 08 - scenario exploration (scenario_request)
    {
        "label": f"{FIXTURE_LABEL} 08 - scenario exploration",
        "request": OrchestrationRequest(
            query="compare going now vs tomorrow",
            scenario_request=ScenarioRequest(
                description="departure window",
                options=["now", "tomorrow", "day-after"], max_options=3)),
        "internal": _base_internal(
            intent="scenario",
            message="Options: now (CAUTION), tomorrow (CAUTION), day-after (OK).",
            answer="Tomorrow is marginally better; day-after clears.",
            confidence={"score": 0.68, "label": "medium", "basis": ["fused"]},
            outputs={"maps": {"type": "FeatureCollection", "features": [],
                              "generated_at": "2026-08-31T12:00:00Z"},
                     "charts": [], "alerts": [], "route": None}),
        "assert": {
            "status": RunStatus.COMPLETED,
        },
    },

    # 09 - multilingual (language hint + non-ASCII answer)
    {
        "label": f"{FIXTURE_LABEL} 09 - multilingual response (Hindi)",
        "request": OrchestrationRequest(query="मछली पकड़ने का अच्छा इलाका", language="hi"),
        "internal": _base_internal(
            intent="pfz",
            language="hi",
            message="PFZ क्षेत्र 11 आपके बिंदु से 12.4 किमी दूर है।",
            answer="PFZ क्षेत्र 11 आपके बिंदु से 12.4 किमी दूर है।"),
        "assert": {
            "status": RunStatus.COMPLETED,
            "language": "hi",
            "answer_non_ascii": True,
        },
    },

    # 10 - multi-turn (session_id present, conversation carried)
    {
        "label": f"{FIXTURE_LABEL} 10 - multi-turn session",
        "request": OrchestrationRequest(
            query="and what about Panambur?",
            session_id="sess-42",
            context={"turn": 3}),
        "internal": _base_internal(
            intent="briefing",
            conversation_id="sess-42",
            message="Briefing prepared for Panambur.",
            answer="SST 27.9C off Panambur today.",
            provenance={"sources": ["incois"], "freshness": {"overall": "fresh"}}),
        "assert": {
            "status": RunStatus.COMPLETED,
            "session_id": "sess-42",
        },
    },

    # 11 - degraded source (partial result, honest status)
    {
        "label": f"{FIXTURE_LABEL} 11 - degraded source (partial)",
        "request": OrchestrationRequest(query="marine briefing off Madras"),
        "internal": _base_internal(
            intent="briefing",
            status="partial",
            message="Partial result: 1 capability provider did not respond.",
            answer="SST available; wave data unavailable.",
            errors=["wave source timed out"],
            confidence={"score": 0.45, "label": "low", "basis": ["partial"]},
            freshness={"overall": "stale"},
            limitations=["wave data unavailable"]),
        "assert": {
            "status": RunStatus.PARTIAL,
            "confidence.level": "low",
            "limitations": 1,
        },
    },

    # 12 - needs input (missing location)
    {
        "label": f"{FIXTURE_LABEL} 12 - needs_input (location required)",
        "request": OrchestrationRequest(query="safety check"),
        "internal": _base_internal(
            status="needs_input",
            message="Which location should I check?",
            answer="Which location should I check?"),
        "assert": {
            "status": RunStatus.NEEDS_INPUT,
            "needs_input.questions": 1,
        },
    },
]


def fixture_labels() -> list:
    return [f["label"] for f in FIXTURES]


def fixture_by_index(index: int) -> dict:
    return FIXTURES[index]