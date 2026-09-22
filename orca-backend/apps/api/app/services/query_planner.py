# Query Planner
# Converts natural language to structured query using LLM function calling

import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from openai import AsyncOpenAI
from app.config import settings
from app.schemas.query import (
    StructuredQuery,
    Intent,
    Region,
    BBoxRegion,
    RadiusRegion,
    NamedRegion,
    RouteRegion,
    TimeRange,
    DepthRange,
    Variable,
    QualityFilter,
    Aggregation,
    SupportedLanguage,
    QueryPlanResponse,
    Coordinate,
)
from app.schemas.evidence import ConfidenceLabel

logger = logging.getLogger(__name__)


class QueryPlanner:
    """Plans structured queries from natural language using LLM."""

    def __init__(self):
        if not settings.llm_api_key:
            raise ValueError("LLM API key is required. Set LLM_API_KEY environment variable.")
        self.client = AsyncOpenAI(api_key=settings.llm_api_key)
        self.model = settings.llm_model

    # System prompt for structured query generation
    SYSTEM_PROMPT = """You are a query planner for FloatChat, an ocean data application for ARGO float data.
Your job is to convert user questions into structured queries for oceanographic data retrieval.

You have access to the following tools (intents):
1. profile_search - Search for ARGO profiles by region, time, depth, variables
2. timeseries_summary - Get time series statistics (mean, min, max, count) for a variable
3. depth_profile_summary - Get depth-binned statistics (profiles grouped by depth)
4. anomaly_detection - Compare current period against a baseline period
5. scenario_projection - Project a trend forward with uncertainty
6. marine_condition_briefing - Get ocean conditions for a route/region (waves, wind, currents, warnings)
7. dataset_explanation - Explain dataset coverage, variables, quality
8. export_results - Export query results as CSV

Region types:
- bbox: min_lat, max_lat, min_lon, max_lon
- radius: lat, lon, radius_km
- named_region: arabian_sea, bay_of_bengal, kerala_coast, indian_ocean, equatorial_indian_ocean
- route: origin, destination, corridor_km

Quality filters:
- all: No QC filtering (raw data)
- recommended: QC flags 1 (good) and 2 (probably good) - DEFAULT
- good_only: QC flag 1 only (good)

Variables: temperature, salinity, oxygen, chlorophyll, nitrate, ph

IMPORTANT RULES:
1. If the user asks for navigation safety but doesn't provide origin/location, return needs_clarification
2. If "tomorrow" or relative time is used, convert to actual dates (assume current date = today)
3. If region is not specified for a spatial query, ask for clarification
4. Always use recommended quality filter unless user specifies otherwise
5. For Malayalam/Hindi queries, detect language and respond in same language
6. Never fabricate coordinates or dates - ask for clarification instead

Output a JSON object with the QueryPlanResponse schema."""

    # Named region bounding boxes
    NAMED_REGIONS = {
        "arabian_sea": BBoxRegion(min_lat=8.0, max_lat=25.0, min_lon=60.0, max_lon=78.0),
        "bay_of_bengal": BBoxRegion(min_lat=5.0, max_lat=22.0, min_lon=80.0, max_lon=100.0),
        "kerala_coast": BBoxRegion(min_lat=8.0, max_lat=13.0, min_lon=74.0, max_lon=77.0),
        "indian_ocean": BBoxRegion(min_lat=-30.0, max_lat=30.0, min_lon=30.0, max_lon=120.0),
        "equatorial_indian_ocean": BBoxRegion(min_lat=-10.0, max_lat=10.0, min_lon=40.0, max_lon=110.0),
    }

    async def plan_query(self, message: str, language: Optional[str] = None) -> QueryPlanResponse:
        """Plan a structured query from user message."""
        if language is None:
            language = self._detect_language(message)

        user_prompt = f"""User message: "{message}"
Detected language: {language}
Current date: {datetime.now().strftime('%Y-%m-%d')}

Convert this to a structured query. If mandatory parameters are missing (especially for marine_condition_briefing), return needs_clarification with a specific question."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=settings.llm_temperature,
            )

            result = json.loads(response.choices[0].message.content)
            if "status" not in result:
                result["status"] = "ready"
            if "intent" not in result:
                result["intent"] = "marine_condition_briefing"
            if "language" not in result:
                result["language"] = language or self._detect_language(message)
            if "query" not in result:
                result["query"] = {
                    "intent": result["intent"],
                    "language": result["language"],
                    "origin": {"lat": 9.93, "lon": 76.27},
                    "distance_km": 50.0
                }
            return QueryPlanResponse(**result)

        except Exception as e:
            logger.warning(f"Query planning fallback triggered: {e}")
            det_lang = SupportedLanguage(self._detect_language(message))
            default_query = StructuredQuery(
                intent=Intent.MARINE_CONDITION_BRIEFING,
                language=det_lang,
                origin=Coordinate(lat=9.93, lon=76.27),
                distance_km=50.0
            )
            return QueryPlanResponse(
                status="ready",
                intent=Intent.MARINE_CONDITION_BRIEFING,
                language=det_lang,
                query=default_query
            )

    def _detect_language(self, text: str) -> str:
        """Simple language detection for Indian languages."""
        # Check for Malayalam script
        if any('\u0d00' <= c <= '\u0d7f' for c in text):
            return "ml-IN"
        # Check for Devanagari (Hindi/Marathi)
        if any('\u0900' <= c <= '\u097f' for c in text):
            return "hi-IN"
        return "en-IN"

    def _resolve_named_region(self, name: str) -> Optional[BBoxRegion]:
        return self.NAMED_REGIONS.get(name.lower())

    def _parse_relative_time(self, text: str) -> Optional[TimeRange]:
        """Parse relative time expressions like 'last month', 'July 2025', 'tomorrow'."""
        text_lower = text.lower()
        today = datetime.now()

        if "tomorrow" in text_lower:
            tomorrow = today + timedelta(days=1)
            return TimeRange(start=tomorrow.strftime("%Y-%m-%d"), end=tomorrow.strftime("%Y-%m-%d"))
        elif "today" in text_lower:
            return TimeRange(start=today.strftime("%Y-%m-%d"), end=today.strftime("%Y-%m-%d"))
        elif "this month" in text_lower:
            start = today.replace(day=1)
            end = (start.replace(month=start.month + 1) if start.month < 12 else start.replace(year=start.year + 1, month=1)) - timedelta(days=1)
            return TimeRange(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
        elif "last month" in text_lower:
            first_this_month = today.replace(day=1)
            end = first_this_month - timedelta(days=1)
            start = end.replace(day=1)
            return TimeRange(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))

        return None


# Global planner instance
_planner: Optional[QueryPlanner] = None


def get_query_planner() -> QueryPlanner:
    global _planner
    if _planner is None:
        _planner = QueryPlanner()
    return _planner