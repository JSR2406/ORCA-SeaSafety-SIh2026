# Intent Agent
# Extracts intent, entities, and parameters from natural language queries

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from app.config import settings
from app.schemas.provenance import SourceType, DataFreshness, EvidenceBundle
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
)
from app.schemas.query import QueryPlanResponse
from app.agents import BaseAgent, ExecutionContext
from app.services.provenance import get_provenance_service

logger = logging.getLogger(__name__)


class IntentAgent(BaseAgent):
    """
    Extracts intent, entities, and structured parameters from natural language queries.
    Uses LLM for NLU with deterministic post-processing for dates/coordinates.
    """

    def __init__(self):
        super().__init__("intent_agent")
        if not settings.llm_api_key:
            raise ValueError("LLM API key is required. Set LLM_API_KEY environment variable.")
        self.client = AsyncOpenAI(api_key=settings.llm_api_key)
        self.model = settings.llm_model

        # Register tools
        self.register_tool("extract_intent", self._extract_intent)
        self.register_tool("extract_entities", self._extract_entities)
        self.register_tool("parse_time", self._parse_time)
        self.register_tool("parse_coordinates", self._parse_coordinates)

    def get_required_inputs(self) -> List[str]:
        return []

    def get_output_types(self) -> List[SourceType]:
        return []

    # System prompt for structured query generation
    SYSTEM_PROMPT = """You are an intent classifier and entity extractor for ORCA, a marine intelligence platform.
Your job is to convert user questions into structured queries for oceanographic data retrieval.

SUPPORTED INTENTS:
1. profile_search - Search for ARGO profiles by region, time, depth, variables
2. timeseries_summary - Get time series statistics (mean, min, max, count) for a variable
3. depth_profile_summary - Get depth-binned statistics (profiles grouped by depth)
4. anomaly_detection - Compare current period against a baseline period
5. scenario_projection - Project a trend forward with uncertainty
6. marine_condition_briefing - Get ocean conditions for a route/region (waves, wind, currents, warnings)
7. route_analysis - Analyze a vessel route for safety and conditions
8. hazard_assessment - Check for hazards (cyclones, warnings, geofences) in an area
9. dataset_explanation - Explain dataset coverage, variables, quality
10. export_results - Export query results as CSV

REGION TYPES:
- bbox: min_lat, max_lat, min_lon, max_lon
- radius: lat, lon, radius_km
- named_region: arabian_sea, bay_of_bengal, kerala_coast, indian_ocean, equatorial_indian_ocean
- route: origin, destination, corridor_km

QUALITY FILTERS:
- all: No QC filtering (raw data)
- recommended: QC flags 1 (good) and 2 (probably good) - DEFAULT
- good_only: QC flag 1 only (good)

VARIABLES: temperature, salinity, oxygen, chlorophyll, nitrate, ph

IMPORTANT RULES:
1. If the user asks for navigation safety or route analysis but doesn't provide origin/location, return needs_clarification
2. If "tomorrow" or relative time is used, convert to actual dates (current date provided)
3. If region is not specified for a spatial query, ask for clarification
4. Always use recommended quality filter unless user specifies otherwise
5. For Indian language queries, detect language and respond in same language
6. Never fabricate coordinates or dates - ask for clarification instead

Output a JSON object with the QueryPlanResponse schema."""

    async def execute(self, context: ExecutionContext) -> List[Any]:
        """
        Main execution: extract intent and entities from user query.
        Returns empty list (this agent produces structured query, not evidence).
        """
        # Plan the query
        plan_result = await self._plan_query(
            context.user_query,
            context.detected_language,
        )

        # Store structured query in context
        context.structured_query = plan_result.query.model_dump() if plan_result.query else {}
        context.detected_language = plan_result.language.value if plan_result.language else "en-IN"

        # If clarification needed, store it
        if plan_result.status == "needs_clarification":
            context.add_warning(f"Clarification needed: {plan_result.clarification_question}")

        return []

    def get_required_inputs(self) -> List[str]:
        return []

    def get_output_types(self) -> List[SourceType]:
        return []

    async def _plan_query(
        self,
        message: str,
        language: Optional[str] = None,
    ) -> QueryPlanResponse:
        """Plan a structured query from user message."""
        # Detect language if not provided
        if language is None:
            language = self._detect_language(message)

        # Build user prompt
        user_prompt = f"""User message: "{message}"
Detected language: {language}
Current date: {datetime.now().strftime('%Y-%m-%d')}

Convert this to a structured query. If mandatory parameters are missing (especially for marine_condition_briefing or route_analysis), return needs_clarification with a specific question."""

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
            return QueryPlanResponse(**result)

        except Exception as e:
            logger.error(f"Query planning failed: {e}")
            raise

    def _detect_language(self, text: str) -> str:
        """Detect language from text."""
        # Check for Malayalam script
        if any('\u0d00' <= c <= '\u0d7f' for c in text):
            return "ml-IN"
        # Check for Devanagari (Hindi/Marathi)
        if any('\u0900' <= c <= '\u097f' for c in text):
            return "hi-IN"
        # Check for Tamil
        if any('\u0b80' <= c <= '\u0bff' for c in text):
            return "ta-IN"
        # Check for Telugu
        if any('\u0c00' <= c <= '\u0c7f' for c in text):
            return "te-IN"
        # Check for Bengali
        if any('\u0980' <= c <= '\u09ff' for c in text):
            return "bn-IN"
        # Check for Gujarati
        if any('\u0a80' <= c <= '\u0aff' for c in text):
            return "gu-IN"
        # Check for Kannada
        if any('\u0c80' <= c <= '\u0cff' for c in text):
            return "kn-IN"
        # Check for Odia
        if any('\u0b00' <= c <= '\u0b7f' for c in text):
            return "or-IN"
        # Check for Punjabi
        if any('\u0a00' <= c <= '\u0a7f' for c in text):
            return "pa-IN"
        # Check for Urdu
        if any('\u0600' <= c <= '\u06ff' for c in text):
            return "ur-IN"
        return "en-IN"

    # --- Tool implementations ---

    async def _extract_intent(
        self,
        context: ExecutionContext,
        input_bundles: List[Any],
    ) -> List[Any]:
        """Extract intent from user query."""
        # This is handled in _plan_query
        return []

    async def _extract_entities(
        self,
        context: ExecutionContext,
        input_bundles: List[Any],
    ) -> List[Any]:
        """Extract entities (coordinates, regions, dates, variables) from query."""
        return []

    async def _parse_time(
        self,
        context: ExecutionContext,
        input_bundles: List[Any],
    ) -> List[Any]:
        """Parse relative time expressions."""
        return []

    async def _parse_coordinates(
        self,
        context: ExecutionContext,
        input_bundles: List[Any],
    ) -> List[Any]:
        """Parse coordinate expressions."""
        return []

    # --- Deterministic parsing helpers ---

    NAMED_REGIONS = {
        "arabian_sea": {"min_lat": 8.0, "max_lat": 25.0, "min_lon": 60.0, "max_lon": 78.0},
        "bay_of_bengal": {"min_lat": 5.0, "max_lat": 22.0, "min_lon": 80.0, "max_lon": 100.0},
        "kerala_coast": {"min_lat": 8.0, "max_lat": 13.0, "min_lon": 74.0, "max_lon": 77.0},
        "indian_ocean": {"min_lat": -30.0, "max_lat": 30.0, "min_lon": 30.0, "max_lon": 120.0},
        "equatorial_indian_ocean": {"min_lat": -10.0, "max_lat": 10.0, "min_lon": 40.0, "max_lon": 110.0},
    }

    def _parse_relative_time(self, text: str) -> Optional[TimeRange]:
        """Parse relative time expressions."""
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
        elif "next week" in text_lower:
            start = today + timedelta(days=(7 - today.weekday()))
            end = start + timedelta(days=6)
            return TimeRange(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
        elif "this week" in text_lower:
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
            return TimeRange(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))

        # Check for month year patterns
        month_pattern = r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})'
        match = re.search(month_pattern, text_lower)
        if match:
            month_name = match.group(1)
            year = int(match.group(2))
            month_num = ["january", "february", "march", "april", "may", "june",
                         "july", "august", "september", "october", "november", "december"].index(month_name) + 1
            start = datetime(year, month_num, 1)
            if month_num == 12:
                end = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                end = datetime(year, month_num + 1, 1) - timedelta(days=1)
            return TimeRange(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))

        return None

    def _resolve_named_region(self, name: str) -> Optional[BBoxRegion]:
        """Resolve named region to bounding box."""
        return self.NAMED_REGIONS.get(name.lower())

    def _parse_coordinates_from_text(self, text: str) -> Optional[Tuple[float, float]]:
        """Parse lat/lon from text like '19.0760, 72.8777' or '19.0760°N, 72.8777°E'."""
        # Pattern for decimal degrees
        coord_pattern = r'([+-]?\d+\.?\d*)\s*[,]\s*([+-]?\d+\.?\d*)'
        match = re.search(coord_pattern, text)
        if match:
            lat = float(match.group(1))
            lon = float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return (lat, lon)
        return None


# Export
__all__ = ["IntentAgent"]