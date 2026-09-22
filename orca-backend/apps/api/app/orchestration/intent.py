# Deterministic intent parsing + language detection for the orchestrator.
#
# Keyword scoring is fully transparent and language-agnostic in structure; the
# multi-turn merge pulls location/context from the conversation record only when
# the user did not supply it in this turn.  Nothing here calls an LLM or network.
import math
import re
from typing import Any, Dict, List, Optional

from app.orchestration.models import Intent, IntentName

_LAT_LON_RE = re.compile(
    r"(?:lat(?:itude)?|at|coordinates?)[\s:=]*"
    r"([-+]?\d{1,2}(?:\.\d+)?)\s*[,;]\s*"
    r"(?:lon(?:gitude)?|long)?[\s:=]*"
    r"([-+]?\d{1,3}(?:\.\d+)?)", re.IGNORECASE)
_COORD_RE = re.compile(
    r"([-+]?\d{1,2}\.\d+)\s*,\s*([-+]?\d{1,3}\.\d+)")

# Deterministic region -> {lat, lon} (approximate geographic constants only;
# never fabricated - these are well-known port/coast anchors).
_REGIONS: Dict[str, Dict[str, Any]] = {
    "goa": {"lat": 15.499, "lon": 73.826, "label": "Goa coast"},
    "mumbai": {"lat": 18.938, "lon": 72.836, "label": "Mumbai coast"},
    "kochi": {"lat": 9.931, "lon": 76.267, "label": "Kochi coast"},
    "chennai": {"lat": 13.083, "lon": 80.283, "label": "Chennai coast"},
    "kolkata": {"lat": 21.594, "lon": 88.237, "label": "Kolkata coast"},
    "vishakhapatnam": {"lat": 17.688, "lon": 83.219, "label": "Visakhapatnam coast"},
    "visakhapatnam": {"lat": 17.688, "lon": 83.219, "label": "Visakhapatnam coast"},
    "vizag": {"lat": 17.688, "lon": 83.219, "label": "Visakhapatnam coast"},
    "tuticorin": {"lat": 8.806, "lon": 78.157, "label": "Tuticorin coast"},
    "porbandar": {"lat": 21.642, "lon": 69.605, "label": "Porbandar coast"},
    "ratnagiri": {"lat": 16.995, "lon": 73.333, "label": "Ratnagiri coast"},
    "kandla": {"lat": 23.033, "lon": 70.217, "label": "Kandla coast"},
    "lakshadweep": {"lat": 10.566, "lon": 72.642, "label": "Lakshadweep waters"},
    "andaman": {"lat": 11.740, "lon": 92.659, "label": "Andaman waters"},
}

_INTENT_KEYWORDS: Dict[IntentName, List[str]] = {
    IntentName.SAFETY: [
        "safe", "safety", "risk", "danger", "dangerous", "warning",
        "hazard", "voyage safety", "should i go",
    ],
    IntentName.FISHING: [
        "fish", "fisher", "fishing", "catch", "trawl", "favorab",
        "day out", "landing", "operations",
    ],
    IntentName.ROUTE: [
        "route", "course", "sail from", "navigate from", "passage",
        "waypoint", "heading from",
    ],
    IntentName.SCENARIO: [
        "what if", "scenario", "simulate", "suppose", "compare",
        "if i", "how would",
    ],
    IntentName.KNOWLEDGE: [
        "what is", "how to", "rules", "regulation", "advisory",
        "guideline", "manual", "why", "allowed", "restricted",
    ],
    IntentName.BRIEFING: [
        "condition", "brief", "status", "report", "how is the sea",
        "weather at", "ocean state", "overview", "current situation",
        "what is the sea",
    ],
    IntentName.PFZ: [
        "pfz", "potential fishing zone", "potential fishing zones",
        "fishing zone advisory",
    ],
    IntentName.PRODUCTIVITY: [
        "productivity", "productive waters", "phytoplankton",
        "chlorophyll", "upwelling",
    ],
}

_TIME_WORDS = {
    "tomorrow": "tomorrow",
    "tonight": "tonight",
    "today": "today",
    "now": "now",
    "monsoon": "monsoon",
}

_REGION_MENTION_RE = re.compile(r"(\w{3,})", re.UNICODE)


class LanguageDetector:
    """Script-based language detection for the response language (en-IN,
    hi-IN, ml-IN, ta-IN, te-IN, kn-IN, ur-IN).  Deterministic, no network.
    Marathi shares the Devanagari script with Hindi and is detected as hi-IN."""

    @staticmethod
    def detect(text: str) -> str:
        if any("\u0d00" <= c <= "\u0d7f" for c in text):
            return "ml-IN"
        if any("\u0b80" <= c <= "\u0bff" for c in text):
            return "ta-IN"
        if any("\u0c00" <= c <= "\u0c7f" for c in text):
            return "te-IN"
        if any("\u0c80" <= c <= "\u0cff" for c in text):
            return "kn-IN"
        if any("\u0900" <= c <= "\u097f" for c in text):
            return "hi-IN"
        if any("\u0600" <= c <= "\u06ff" for c in text):
            return "ur-IN"
        return "en-IN"


# Rules/advisory questions are the canonical knowledge use-case: a mention
# must never be downgraded to a quantitative fishing/favorability answer.
_STRONG_KNOWLEDGE = {"rules", "regulation", "advisory", "guideline", "how to"}


def _score_intents(text: str) -> Dict[IntentName, int]:
    lowered = text.lower()
    scores = {}
    for name, keywords in _INTENT_KEYWORDS.items():
        scores[name] = sum(
            3 if kw in _STRONG_KNOWLEDGE else 1
            for kw in keywords if kw in lowered)
    return scores


def _pick_intent(scores: Dict[IntentName, int]):
    """Highest score wins; on a tie the LOWER tie-break value wins (safety
    first).  Returns (name, bare) where bare flags zero keyword matches - the
    turn then inherits the conversation's last operational intent."""
    best = max(scores, key=lambda k: (scores[k], -_tie_break(k)))
    return best, scores[best] == 0


def _tie_break(name: IntentName) -> int:
    # Safety always wins ties; knowledge absorbs sub-questions; new intents rank
    # after knowledge so PFZ keywords never hijack "what is ... rules" queries.
    order = {
        IntentName.SAFETY: 0,
        IntentName.FISHING: 1,
        IntentName.ROUTE: 2,
        IntentName.SCENARIO: 3,
        IntentName.KNOWLEDGE: 4,
        IntentName.PFZ: 5,
        IntentName.BRIEFING: 6,
        IntentName.PRODUCTIVITY: 7,
    }
    return order.get(name, 8)


def _parse_location(text: str, region_names: bool = True) -> Optional[Dict[str, Any]]:
    match = _LAT_LON_RE.search(text)
    if match:
        return {
            "lat": float(match.group(1)),
            "lon": float(match.group(2)),
            "label": "user coordinates",
        }
    match = _COORD_RE.search(text)
    if match:
        return {
            "lat": float(match.group(1)),
            "lon": float(match.group(2)),
            "label": "user coordinates",
        }
    if region_names:
        lowered = text.lower()
        for name, anchor in _REGIONS.items():
            if name in lowered:
                return dict(anchor)
    return None


_FROM_TO_RE = re.compile(
    r"\bfrom\s+([a-z]+)\s+to\s+([a-z]+)\b", re.IGNORECASE)

# "20 km south of Mumbai", "50km north of kochi", "10 km east of the port",
# and bare follow-ups like "20 km south." (anchor resolved from context later).
_OFFSET_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*kms?\s*(north|south|east|west)"
    r"(?:\s+of\s+([a-z]+))?",
    re.IGNORECASE)

_KM_PER_DEG_LAT = 111.32


def _parse_offset(text: str) -> Optional[Dict[str, Any]]:
    match = _OFFSET_RE.search(text.lower())
    if not match:
        return None
    return {
        "km": float(match.group(1)),
        "direction": match.group(2),
        "anchor_label": match.group(3),
    }


def _apply_offset(location: Dict[str, Any],
                  offset: Optional[Dict[str, Any]],
                  anchor: Dict[str, Any]) -> Dict[str, Any]:
    """Shift a resolved anchor by a (km, direction) offset.  Deterministic."""
    if not offset:
        return location
    km = offset["km"]
    dlat = km / _KM_PER_DEG_LAT
    dlon = km / (_KM_PER_DEG_LAT * math.cos(math.radians(anchor["lat"])))
    direction = offset["direction"].lower()
    if direction == "north":
        lat, lon = anchor["lat"] + dlat, anchor["lon"]
    elif direction == "south":
        lat, lon = anchor["lat"] - dlat, anchor["lon"]
    elif direction == "east":
        lat, lon = anchor["lat"], anchor["lon"] + dlon
    else:
        lat, lon = anchor["lat"], anchor["lon"] - dlon
    anchor_name = offset.get("anchor_label") or anchor.get("label") or ""
    return {
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "label": f"{km:g} km {direction} of {anchor_name}",
    }


def _parse_route(text: str) -> Optional[Dict[str, Any]]:
    """Parse 'from X to Y' into origin/destination region anchors."""
    match = _FROM_TO_RE.search(text)
    if not match:
        return None
    origin = _REGIONS.get(match.group(1).lower())
    destination = _REGIONS.get(match.group(2).lower())
    if not origin or not destination:
        return None
    return {"origin": dict(origin), "destination": dict(destination)}


def _parse_time(text: str) -> str:
    lowered = text.lower()
    for word, value in _TIME_WORDS.items():
        if word in lowered:
            return value
    return "now"


# Operations a bare multi-turn follow-up ("and how does it look there?" /
# "20 km south.") may inherit from the previous turn.
_INHERITABLE_OPERATIONS = {
    IntentName.SAFETY, IntentName.FISHING, IntentName.ROUTE,
    IntentName.SCENARIO, IntentName.PFZ, IntentName.PRODUCTIVITY,
}


class IntentParser:
    """Parse a user turn into a structured @Intent, merging multi-turn context."""

    def parse(self, message: str, context: Optional[Any] = None,
              user_location: Optional[Dict[str, Any]] = None) -> Intent:
        language = LanguageDetector.detect(message)
        name, bare = _pick_intent(_score_intents(message))
        if bare:
            name = IntentName.BRIEFING

        location = _parse_location(message)
        route = _parse_route(message)
        waypoints = None
        if name == IntentName.ROUTE and route:
            location = dict(route["destination"])
            waypoints = [
                [route["origin"]["lat"], route["origin"]["lon"]],
                [route["destination"]["lat"], route["destination"]["lon"]],
            ]

        # Offset is parsed but NOT applied here: for a bare follow-up the
        # anchor is the context-resolved location, which the context merge
        # below performs first (Phase 6 multi-turn).
        offset = _parse_offset(message)
        coord_match = bool(_LAT_LON_RE.search(message)
                           or _COORD_RE.search(message))
        time_value = _parse_time(message)

        # ------------------------------------------------ context merge first
        context_location = None
        merged_location = False
        prior_time_label = None
        prior_intent_name = None
        if context is not None:
            context_location = getattr(context, "resolved_location", None)
            last_intent = getattr(context, "last_intent", None)
            if isinstance(last_intent, dict):
                prior_intent_name = last_intent.get("name")
            if not location and context_location:
                location = dict(context_location)
                merged_location = True
            prior_time_label = getattr(context, "resolved_time", None)
            prior_language = getattr(context, "language", None)
            if prior_language and prior_language != "en-IN":
                language = prior_language

        # user_location from request (priority: message coords > user_location > context)
        if not location and user_location:
            u_lat = getattr(user_location, "latitude", None) if not isinstance(user_location, dict) else user_location.get("latitude")
            u_lon = getattr(user_location, "longitude", None) if not isinstance(user_location, dict) else user_location.get("longitude")
            u_src = getattr(user_location, "source", "USER") if not isinstance(user_location, dict) else user_location.get("source", "USER")
            location = {
                "lat": u_lat,
                "lon": u_lon,
                "label": f"user location ({u_src})",
            }
            merged_location = True

        # Inherit the previous operational intent when this turn is a bare
        # follow-up (zero intent keywords).
        if bare and prior_intent_name is not None:
            try:
                prior = IntentName(prior_intent_name)
            except ValueError:
                prior = None
            if prior in _INHERITABLE_OPERATIONS:
                name = prior

        # Apply the offset against whichever anchor resolved (message anchor,
        # or the context location for a bare follow-up).
        offset_used = None
        if offset and location and name != IntentName.ROUTE and not coord_match:
            shifted = _apply_offset(dict(location), offset, location)
            offset_used = {**offset, "applied": True, "origin": dict(location)}
            location = shifted
        elif offset:
            offset_used = {**offset, "applied": False, "origin": None}

        # Resolved time: keep an explicit time-word, else inherit the last
        # resolved reference so a bare follow-up stays on the same schedule.
        resolved_time = time_value
        if time_value == "now" and isinstance(prior_time_label, dict) \
                and prior_time_label.get("label"):
            resolved_time = prior_time_label["label"]

        needs: List[str] = []
        if name in (IntentName.BRIEFING, IntentName.SAFETY, IntentName.FISHING,
                    IntentName.PFZ, IntentName.PRODUCTIVITY) and not location:
            needs.append("location")
        if name == IntentName.ROUTE and not route:
            needs.append("route")

        intent = Intent(
            name=name,
            language=language,
            location=location,
            origin=route.get("origin") if route else None,
            time=resolved_time,
            query=message,
            needs=needs,
            confidence=0.95 if needs else 0.8,
            origin_raw=message,
            offset=offset_used,
            route=waypoints,
        )
        if context is not None and merged_location:
            intent.merged_from_context = True
        return intent


class IntentValidator:
    """Checks that an intent is executable (location present when needed)."""

    def is_resolvable(self, intent: Intent) -> bool:
        return "location" not in intent.needs or intent.location is not None