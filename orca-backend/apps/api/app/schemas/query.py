# API Schemas - Query
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Union, Annotated
from datetime import datetime
from enum import Enum


class SupportedLanguage(str, Enum):
    EN_IN = "en-IN"
    HI_IN = "hi-IN"
    ML_IN = "ml-IN"
    TA_IN = "ta-IN"
    TE_IN = "te-IN"
    BN_IN = "bn-IN"
    GU_IN = "gu-IN"
    MR_IN = "mr-IN"
    OR_IN = "or-IN"
    KN_IN = "kn-IN"


class Intent(str, Enum):
    PROFILE_SEARCH = "profile_search"
    TIMESERIES_SUMMARY = "timeseries_summary"
    DEPTH_PROFILE_SUMMARY = "depth_profile_summary"
    ANOMALY_DETECTION = "anomaly_detection"
    SCENARIO_PROJECTION = "scenario_projection"
    MARINE_CONDITION_BRIEFING = "marine_condition_briefing"
    DATASET_EXPLANATION = "dataset_explanation"
    EXPORT_RESULTS = "export_results"
    ROUTE_ANALYSIS = "route_analysis"
    HAZARD_ASSESSMENT = "hazard_assessment"


class RegionType(str, Enum):
    BBOX = "bbox"
    RADIUS = "radius"
    POLYGON = "polygon"
    NAMED_REGION = "named_region"
    ROUTE = "route"


class BBoxRegion(BaseModel):
    type: Literal[RegionType.BBOX] = RegionType.BBOX
    min_lat: float = Field(ge=-90, le=90)
    max_lat: float = Field(ge=-90, le=90)
    min_lon: float = Field(ge=-180, le=180)
    max_lon: float = Field(ge=-180, le=180)


class RadiusRegion(BaseModel):
    type: Literal[RegionType.RADIUS] = RegionType.RADIUS
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=5000)


class PolygonRegion(BaseModel):
    type: Literal[RegionType.POLYGON] = RegionType.POLYGON
    coordinates: List[List[List[float]]]  # GeoJSON polygon


class NamedRegion(BaseModel):
    type: Literal[RegionType.NAMED_REGION] = RegionType.NAMED_REGION
    name: Literal["arabian_sea", "bay_of_bengal", "kerala_coast", "indian_ocean", "equatorial_indian_ocean"]


class RouteRegion(BaseModel):
    type: Literal[RegionType.ROUTE] = RegionType.ROUTE
    origin: "Coordinate"
    destination: "Coordinate"
    corridor_km: Optional[float] = Field(default=None, gt=0)


class Coordinate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


Region = Annotated[
    Union[BBoxRegion, RadiusRegion, PolygonRegion, NamedRegion, RouteRegion],
    Field(discriminator="type"),
]


class TimeRange(BaseModel):
    start: str  # ISO 8601
    end: str    # ISO 8601


class DepthRange(BaseModel):
    min: float = Field(ge=0, le=6000)
    max: float = Field(ge=0, le=6000)


class Variable(str, Enum):
    TEMPERATURE = "temperature"
    SALINITY = "salinity"
    OXYGEN = "oxygen"
    CHLOROPHYLL = "chlorophyll"
    NITRATE = "nitrate"
    PH = "ph"


class QualityFilter(str, Enum):
    ALL = "all"
    RECOMMENDED = "recommended"
    GOOD_ONLY = "good_only"


class Aggregation(str, Enum):
    PROFILE = "profile"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    DEPTH_BIN = "depth_bin"


class ModelType(str, Enum):
    LINEAR_TREND = "linear_trend"
    POLYNOMIAL = "polynomial"
    THEIL_SEN = "theil_sen"


class ExportFormat(str, Enum):
    PROFILES = "profiles"
    OBSERVATIONS = "observations"
    SUMMARY = "summary"


class StructuredQuery(BaseModel):
    intent: Intent
    language: SupportedLanguage = SupportedLanguage.EN_IN
    region: Optional[Region] = None
    time_range: Optional[TimeRange] = None
    depth_range_m: Optional[DepthRange] = None
    variables: Optional[List[Variable]] = None
    quality_filter: QualityFilter = QualityFilter.RECOMMENDED
    aggregation: Aggregation = Aggregation.PROFILE
    limit: int = Field(default=500, ge=1, le=5000)

    # Marine condition briefing
    distance_km: Optional[float] = Field(default=None, gt=0)
    origin: Optional[Coordinate] = None
    destination: Optional[Coordinate] = None
    departure_time: Optional[str] = None
    vessel_type: Optional[str] = None
    include_forecast: bool = True

    # Anomaly detection
    reference_period: Optional[TimeRange] = None
    analysis_period: Optional[TimeRange] = None
    depth_m: Optional[float] = Field(default=None, ge=0, le=6000)
    threshold_std: float = Field(default=2.0, gt=0)

    # Scenario projection
    trend_window: Optional[TimeRange] = None
    projection_years: Optional[int] = Field(default=None, ge=1, le=50)
    model: ModelType = ModelType.LINEAR_TREND
    assumptions: List[str] = Field(default_factory=list)

    # Export
    export_format: ExportFormat = ExportFormat.PROFILES


class QueryPlanRequest(BaseModel):
    message: str
    language: Optional[SupportedLanguage] = None


class QueryPlanResponse(BaseModel):
    status: Literal["ready", "needs_clarification", "unsupported"]
    intent: Intent
    language: SupportedLanguage
    query: StructuredQuery
    clarification_question: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)