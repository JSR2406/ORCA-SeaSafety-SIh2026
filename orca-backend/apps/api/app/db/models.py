# Database Models
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, BigInteger, Float, String, DateTime, Text, Index, 
    ForeignKey, UniqueConstraint, JSON, ARRAY, Boolean
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy.types import TypeEngine, UserDefinedType
from sqlalchemy.ext.compiler import compiles
from geoalchemy2 import Geography, Geometry


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VectorType(UserDefinedType):
    """pgvector vector column type.

    Renders as ``VECTOR`` on PostgreSQL (matching the production migration
    ``0f7e1a2b3c4d`` which converts ``knowledge_chunks.embedding`` to
    ``vector(1536)``) and as ``TEXT`` on SQLite so the model still loads for
    non-Postgres runs.  The bind processor accepts either a list of floats or a
    pre-formatted ``[...]`` literal string and emits the pgvector text literal,
    which lets asyncpg bind the parameter against the vector column.
    """
    __visit_name__ = "vector_type"
    cache_ok = True

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            if isinstance(value, (list, tuple)):
                return "[" + ",".join(repr(float(v)) for v in value) + "]"
            return value
        return process

    def get_col_spec(self, **kw):
        return "VECTOR"


@compiles(VectorType, "postgresql")
def _compile_vector_postgresql(type_, compiler, **kw):
    return "VECTOR"


@compiles(VectorType, "sqlite")
def _compile_vector_sqlite(type_, compiler, **kw):
    return "TEXT"


class Base(DeclarativeBase):
    pass


class ArgoProfile(Base):
    __tablename__ = "argo_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    platform_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[str] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    qc_status: Mapped[str] = mapped_column(String(50), nullable=False, default="recommended")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    observations: Mapped[List["ArgoObservation"]] = relationship(back_populates="profile", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("platform_number", "cycle_number", name="uq_platform_cycle"),
        Index("idx_argo_profiles_geom", "geom", postgresql_using="gist"),
    )


class ArgoObservation(Base):
    __tablename__ = "argo_observations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("argo_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    pressure_dbar: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    depth_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salinity_psu: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    oxygen_umol_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    chlorophyll: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temperature_qc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salinity_qc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    oxygen_qc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    profile: Mapped["ArgoProfile"] = relationship(back_populates="observations")

    __table_args__ = (
        Index("idx_argo_obs_profile", "profile_id"),
        Index("idx_argo_obs_temp", "temperature_c", postgresql_where="temperature_c IS NOT NULL"),
        Index("idx_argo_obs_salinity", "salinity_psu", postgresql_where="salinity_psu IS NOT NULL"),
    )


class DatasetSnapshot(Base):
    __tablename__ = "dataset_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dataset_name: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[str] = mapped_column(String(500), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    source_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    record_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    profile_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    float_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")


class QueryRun(Base):
    __tablename__ = "query_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    detected_language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    normalized_intent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    structured_query: Mapped[dict] = mapped_column(JSON, nullable=False)
    tool_calls: Mapped[Optional[List[dict]]] = mapped_column(JSON, nullable=True)
    execution_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    evidence: Mapped[List["EvidenceRecord"]] = relationship(back_populates="query_run", cascade="all, delete-orphan")
    narratives: Mapped[List["Narrative"]] = relationship(back_populates="query_run", cascade="all, delete-orphan")
    scenarios: Mapped[List["ScenarioRun"]] = relationship(back_populates="query_run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_query_runs_session_created", "session_id", "created_at"),
    )


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    query_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("query_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    float_ids: Mapped[List[int]] = mapped_column(ARRAY(Integer), nullable=False, default=[])
    profile_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    observation_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    region: Mapped[dict] = mapped_column(JSON, nullable=False)
    depth_range: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    time_range: Mapped[dict] = mapped_column(JSON, nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, nullable=False)
    data_freshness: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence_label: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_components: Mapped[dict] = mapped_column(JSON, nullable=False)
    limitations: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=[])
    source_identifiers: Mapped[dict] = mapped_column(JSON, nullable=False)
    verified: Mapped[bool] = mapped_column(nullable=False, default=False)
    verification_errors: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    query_run: Mapped["QueryRun"] = relationship(back_populates="evidence")


class Narrative(Base):
    __tablename__ = "narratives"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    query_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("query_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    narrative_text: Mapped[str] = mapped_column(Text, nullable=False)
    numeric_claims: Mapped[List[dict]] = mapped_column(JSON, nullable=False, default=[])
    verified: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    query_run: Mapped["QueryRun"] = relationship(back_populates="narratives")


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    query_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("query_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    variable: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[dict] = mapped_column(JSON, nullable=False)
    baseline: Mapped[dict] = mapped_column(JSON, nullable=False)
    trend_window: Mapped[dict] = mapped_column(JSON, nullable=False)
    projection_horizon: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    assumptions: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=[])
    uncertainty_method: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    query_run: Mapped["QueryRun"] = relationship(back_populates="scenarios")


# ---------------------------------------------------------------------------
# Real-time marine data infrastructure (Phase 1)
# ---------------------------------------------------------------------------
# All timestamps are timezone-aware UTC.  observation/valid/event times carry
# the *physical* time of the data; source_timestamp is what upstream reported;
# ingested_at is when this system stored it.  source_record_id is the natural
# durable key used for idempotent ingestion (unique per source).

class DataSource(Base):
    """Registered marine data source with runtime health."""
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_configured")
    last_successful_fetch: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True)
    latest_data_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    capabilities: Mapped[List["SourceCapability"]] = relationship(
        back_populates="source", cascade="all, delete-orphan")


class SourceCapability(Base):
    __tablename__ = "source_capabilities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data_product: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    config_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    source: Mapped["DataSource"] = relationship(back_populates="capabilities")


class OceanObservation(Base):
    __tablename__ = "ocean_observations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[Optional[str]] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    observation_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True)
    source_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    sst_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    chlorophyll: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wave_height_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wave_period_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wave_direction_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_speed_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_direction_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salinity_psu: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    quality: Mapped[str] = mapped_column(String(20), nullable=False, default="valid")
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "source", "source_record_id",
            name="uq_ocean_source_record",
            postgresql_nulls_not_distinct=True,
        ),
        Index("idx_ocean_obs_geom", "geom", postgresql_using="gist"),
        Index("idx_ocean_obs_time_loc", "observation_time", "latitude", "longitude"),
    )


class WeatherObservation(Base):
    __tablename__ = "weather_observations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[Optional[str]] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    valid_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True)
    source_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_speed_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_direction_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precipitation_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pressure_hpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    humidity_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    visibility_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lightning: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    condition: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    quality: Mapped[str] = mapped_column(String(20), nullable=False, default="valid")
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "source", "source_record_id",
            name="uq_weather_obs_source_record",
            postgresql_nulls_not_distinct=True,
        ),
        Index("idx_weather_obs_geom", "geom", postgresql_using="gist"),
    )


class WeatherForecast(Base):
    __tablename__ = "weather_forecasts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[Optional[str]] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    issue_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    forecast_horizon_h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temperature_min_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temperature_max_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_speed_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_direction_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precipitation_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pressure_hpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    humidity_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    visibility_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lightning: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    condition: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    quality: Mapped[str] = mapped_column(String(20), nullable=False, default="valid")
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "source", "source_record_id",
            name="uq_weather_fc_source_record",
            postgresql_nulls_not_distinct=True,
        ),
        Index("idx_weather_fc_geom", "geom", postgresql_using="gist"),
    )


class TidePrediction(Base):
    __tablename__ = "tide_predictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    location_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[Optional[str]] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    tide_height_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tide_type: Mapped[str] = mapped_column(String(10), nullable=False, default="high")
    is_prediction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    quality: Mapped[str] = mapped_column(String(20), nullable=False, default="valid")
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "source", "source_record_id",
            name="uq_tides_source_record",
            postgresql_nulls_not_distinct=True,
        ),
        Index("idx_tides_geom", "geom", postgresql_using="gist"),
    )


class PFZZone(Base):
    __tablename__ = "pfz_zones"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    geometry: Mapped[Optional[str]] = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True)
    centroid_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    centroid_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    species: Mapped[List[str]] = mapped_column(ARRAY(String(100)), nullable=False, default=[])
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    source_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    quality: Mapped[str] = mapped_column(String(20), nullable=False, default="valid")
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "source", "source_record_id",
            name="uq_pfz_source_record",
            postgresql_nulls_not_distinct=True,
        ),
        Index("idx_pfz_geometry", "geometry", postgresql_using="gist"),
    )


class MarineWarning(Base):
    __tablename__ = "marine_warnings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    warning_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    warning_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    severity: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    geometry: Mapped[Optional[str]] = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    __table_args__ = (
        Index("idx_marine_warnings_geometry", "geometry", postgresql_using="gist"),
    )


class RestrictedArea(Base):
    __tablename__ = "restricted_areas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    area_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    area_name: Mapped[str] = mapped_column(String(300), nullable=False)
    restriction_kind: Mapped[str] = mapped_column(String(30), nullable=False, default="permanent")
    restriction_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    severity: Mapped[str] = mapped_column(String(30), nullable=False, default="moderate")
    geometry: Mapped[Optional[str]] = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    __table_args__ = (
        Index("idx_restricted_areas_geometry", "geometry", postgresql_using="gist"),
    )


class DynamicRestriction(Base):
    """Live, time-windowed official restriction (NAVAREA/NAVTEX, exercises,
    temporary closures).  `expired` is set by the refresh pipeline when a
    source stops publishing a record, so expired restrictions never remain
    active.  Unique per (source, source_record_id) for idempotent refresh."""
    __tablename__ = "dynamic_restrictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_record_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    restriction_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    restriction_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    severity: Mapped[str] = mapped_column(String(30), nullable=False, default="moderate")
    geometry: Mapped[Optional[str]] = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    data_class: Mapped[str] = mapped_column(String(30), nullable=False, default="advisory")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "source", "source_record_id",
            name="uq_dynamic_restrictions_source_record",
            postgresql_nulls_not_distinct=True,
        ),
        Index("idx_dynamic_restrictions_geometry", "geometry", postgresql_using="gist"),
    )


class IngestionRun(Base):
    """One pipeline run for a (source, product) pair; observability + freshness."""
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    product: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    records_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_quality_valid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_quality_suspicious: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_quality_invalid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_duplicates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


# ---------------------------------------------------------------------------
# Knowledge base + marine evidence (Phase 3 foundation)
# ---------------------------------------------------------------------------
# Knowledge documents hold curated, real documentation (regulations, safety
# manuals, operational guides).  embeddings/chunks feed the hybrid RAG path;
# the FTS GIN index and vector(1536) column are created by migration
# 0f7e1a2b3c4d on PostgreSQL (SPDX: pgvector extension).  The ORM maps the
# embedding column via VectorType so INSERT/UPDATE bind against the vector
# column on PostgreSQL (matching the migration) while compiling to TEXT on
# SQLite for non-Postgres runs.

class KnowledgeDocument(Base):
    """A curated knowledge document (never machine-generated)."""
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    tags: Mapped[List[str]] = mapped_column(ARRAY(String(100)), nullable=False, default=[])
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    ingestion_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)

    # Ingestion metadata (Phase 3.5)
    authority: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    publication_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_reference: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    chunks: Mapped[List["KnowledgeChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    """A chunk of a knowledge document with optional vector embedding."""
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[str]] = mapped_column(VectorType, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Structural preservation + embedding bookkeeping (Phase 3.5)
    section: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    heading: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    chunk_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    embedding_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    embedding_dimensions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    embedded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    document: Mapped["KnowledgeDocument"] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_chunk_index"),
    )


class MarineEvidence(Base):
    """Durable evidence for every fact an agent asserts from live marine data."""
    __tablename__ = "marine_evidence"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    query_run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geom: Mapped[Optional[str]] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    observed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_marine_evidence_agent_tool", "agent_name", "tool_name"),
        Index("idx_marine_evidence_geom", "geom", postgresql_using="gist"),
    )


# ---------------------------------------------------------------------------
# Agentic orchestration persistence (Phase 4)
# ---------------------------------------------------------------------------

class ConversationContext(Base):
    """Structured multi-turn conversation context for the orchestrator."""
    __tablename__ = "conversation_contexts"

    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en-IN")
    resolved_location: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    resolved_time: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_intent: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    history: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    preferences: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    active_scenario: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class ExecutionRun(Base):
    """One agentic orchestration execution."""
    __tablename__ = "execution_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    intent: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    plan: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tasks: Mapped[List["ExecutionTask"]] = relationship(
        back_populates="run", cascade="all, delete-orphan")
    events: Mapped[List["ExecutionEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan")


class ExecutionTask(Base):
    """One task inside an execution run."""
    __tablename__ = "execution_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("execution_runs.id", ondelete="CASCADE"),
        nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    agent: Mapped[str] = mapped_column(String(100), nullable=False)
    tool: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dependencies: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=[])
    input_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    result_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped["ExecutionRun"] = relationship(back_populates="tasks")


class ExecutionEvent(Base):
    """Structured trace event for an execution run (observability/explainability)."""
    __tablename__ = "execution_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("execution_runs.id", ondelete="CASCADE"),
        nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    run: Mapped["ExecutionRun"] = relationship(back_populates="events")


# ---------------------------------------------------------------------------
# Phase 11 - proactive marine intelligence (events + alerts)
# ---------------------------------------------------------------------------

class MarineEventRecord(Base):
    """Persisted normalized marine event (idempotent by event_id hash)."""
    __tablename__ = "marine_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    change_state: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geometry: Mapped[Optional[str]] = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    previous_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    current_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    validity: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    event_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AlertRecord(Base):
    """Persisted proactive alert with lifecycle + provenance."""
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    alert_uid: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created", index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    message: Mapped[Text] = mapped_column(Text, nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geometry: Mapped[Optional[str]] = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    freshness: Mapped[str] = mapped_column(String(20), nullable=False, default="live")
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evidence: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    escalation_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    alert_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_alerts_dedupe_created", "dedupe_key", "created_at"),
        Index("idx_alerts_geom", "geometry", postgresql_using="gist"),
    )


class RestrictionLifecycle(Base):
    """Lifecycle tracking for temporary restrictions / geofences."""
    __tablename__ = "restriction_lifecycle"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    restriction_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    lifecycle_state: Mapped[str] = mapped_column(String(30), nullable=False, default="scheduled")
    geometry: Mapped[Optional[str]] = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="scheduled")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    restriction_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("source", "restriction_id", name="uq_restriction_lifecycle"),
        Index("idx_restriction_lifecycle_geom", "geometry", postgresql_using="gist"),
    )


class UserAlertPreference(Base):
    """Per-category alert delivery mode per user."""
    __tablename__ = "user_alert_preferences"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    mode: Mapped[str] = mapped_column(String(30), nullable=False, default="important_only")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_user_alert_pref"),
    )