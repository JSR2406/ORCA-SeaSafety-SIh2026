"""marine data infrastructure

Revision ID: 8f51d7a9c3b2
Revises: 729be30b0cb2
Create Date: 2026-08-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = '8f51d7a9c3b2'
down_revision: Union[str, None] = '729be30b0cb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgresql() -> bool:
    """Check if we're running against PostgreSQL."""
    return op.get_bind().dialect.name == 'postgresql'


def _array_type(item_type: type) -> type:
    """Return ARRAY type for PostgreSQL, JSON for SQLite."""
    if _is_postgresql():
        return sa.ARRAY(item_type)
    return sa.JSON()


def _point_type() -> type:
    if _is_postgresql():
        return geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, dimension=2, spatial_index=False)
    return sa.Text()


def _polygon_type() -> type:
    if _is_postgresql():
        return geoalchemy2.types.Geometry(geometry_type='GEOMETRY', srid=4326, dimension=2, spatial_index=False)
    return sa.Text()


def upgrade() -> None:
    if _is_postgresql():
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    point_type = _point_type()
    polygon_type = _polygon_type()

    op.create_table('sources',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('base_url', sa.String(length=500), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('last_successful_fetch', sa.DateTime(timezone=True), nullable=True),
        sa.Column('latest_data_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_sources_name'), 'sources', ['name'], unique=True)
    op.create_index(op.f('ix_sources_last_successful_fetch'), 'sources', ['last_successful_fetch'], unique=False)

    op.create_table('source_capabilities',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('data_product', sa.String(length=100), nullable=False),
        sa.Column('config_required', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_source_capabilities_source_id'), 'source_capabilities', ['source_id'], unique=False)
    op.create_index(op.f('ix_source_capabilities_data_product'), 'source_capabilities', ['data_product'], unique=False)

    op.create_table('ocean_observations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('source_record_id', sa.String(length=200), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('geom', point_type, nullable=True),
        sa.Column('observation_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sst_c', sa.Float(), nullable=True),
        sa.Column('chlorophyll', sa.Float(), nullable=True),
        sa.Column('wave_height_m', sa.Float(), nullable=True),
        sa.Column('wave_period_s', sa.Float(), nullable=True),
        sa.Column('wave_direction_deg', sa.Float(), nullable=True),
        sa.Column('current_speed_ms', sa.Float(), nullable=True),
        sa.Column('current_direction_deg', sa.Float(), nullable=True),
        sa.Column('salinity_psu', sa.Float(), nullable=True),
        sa.Column('quality', sa.String(length=20), nullable=False),
        sa.Column('raw_payload', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'source_record_id',
                            name='uq_ocean_source_record', postgresql_nulls_not_distinct=True)
    )
    if _is_postgresql():
        op.create_index('idx_ocean_obs_geom', 'ocean_observations', ['geom'], unique=False, postgresql_using='gist')
    else:
        op.create_index('idx_ocean_obs_geom', 'ocean_observations', ['geom'], unique=False)
    op.create_index(op.f('ix_ocean_observations_source'), 'ocean_observations', ['source'], unique=False)
    op.create_index(op.f('ix_ocean_observations_source_record_id'), 'ocean_observations', ['source_record_id'], unique=False)
    op.create_index(op.f('ix_ocean_observations_observation_time'), 'ocean_observations', ['observation_time'], unique=False)
    op.create_index(op.f('ix_ocean_observations_ingested_at'), 'ocean_observations', ['ingested_at'], unique=False)
    op.create_index('idx_ocean_obs_time_loc', 'ocean_observations', ['observation_time', 'latitude', 'longitude'], unique=False)

    op.create_table('weather_observations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('source_record_id', sa.String(length=200), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('geom', point_type, nullable=True),
        sa.Column('valid_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('temperature_c', sa.Float(), nullable=True),
        sa.Column('wind_speed_ms', sa.Float(), nullable=True),
        sa.Column('wind_direction_deg', sa.Float(), nullable=True),
        sa.Column('precipitation_mm', sa.Float(), nullable=True),
        sa.Column('pressure_hpa', sa.Float(), nullable=True),
        sa.Column('humidity_pct', sa.Float(), nullable=True),
        sa.Column('visibility_m', sa.Float(), nullable=True),
        sa.Column('lightning', sa.Boolean(), nullable=True),
        sa.Column('condition', sa.String(length=100), nullable=True),
        sa.Column('quality', sa.String(length=20), nullable=False),
        sa.Column('raw_payload', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'source_record_id',
                            name='uq_weather_obs_source_record', postgresql_nulls_not_distinct=True)
    )
    if _is_postgresql():
        op.create_index('idx_weather_obs_geom', 'weather_observations', ['geom'], unique=False, postgresql_using='gist')
    else:
        op.create_index('idx_weather_obs_geom', 'weather_observations', ['geom'], unique=False)
    op.create_index(op.f('ix_weather_observations_source'), 'weather_observations', ['source'], unique=False)
    op.create_index(op.f('ix_weather_observations_source_record_id'), 'weather_observations', ['source_record_id'], unique=False)
    op.create_index(op.f('ix_weather_observations_valid_time'), 'weather_observations', ['valid_time'], unique=False)
    op.create_index(op.f('ix_weather_observations_ingested_at'), 'weather_observations', ['ingested_at'], unique=False)

    op.create_table('weather_forecasts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('source_record_id', sa.String(length=200), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('geom', point_type, nullable=True),
        sa.Column('issue_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('forecast_horizon_h', sa.Float(), nullable=True),
        sa.Column('source_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('temperature_c', sa.Float(), nullable=True),
        sa.Column('temperature_min_c', sa.Float(), nullable=True),
        sa.Column('temperature_max_c', sa.Float(), nullable=True),
        sa.Column('wind_speed_ms', sa.Float(), nullable=True),
        sa.Column('wind_direction_deg', sa.Float(), nullable=True),
        sa.Column('precipitation_mm', sa.Float(), nullable=True),
        sa.Column('pressure_hpa', sa.Float(), nullable=True),
        sa.Column('humidity_pct', sa.Float(), nullable=True),
        sa.Column('visibility_m', sa.Float(), nullable=True),
        sa.Column('lightning', sa.Boolean(), nullable=True),
        sa.Column('condition', sa.String(length=100), nullable=True),
        sa.Column('quality', sa.String(length=20), nullable=False),
        sa.Column('raw_payload', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'source_record_id',
                            name='uq_weather_fc_source_record', postgresql_nulls_not_distinct=True)
    )
    if _is_postgresql():
        op.create_index('idx_weather_fc_geom', 'weather_forecasts', ['geom'], unique=False, postgresql_using='gist')
    else:
        op.create_index('idx_weather_fc_geom', 'weather_forecasts', ['geom'], unique=False)
    op.create_index(op.f('ix_weather_forecasts_source'), 'weather_forecasts', ['source'], unique=False)
    op.create_index(op.f('ix_weather_forecasts_source_record_id'), 'weather_forecasts', ['source_record_id'], unique=False)
    op.create_index(op.f('ix_weather_forecasts_issue_time'), 'weather_forecasts', ['issue_time'], unique=False)
    op.create_index(op.f('ix_weather_forecasts_valid_from'), 'weather_forecasts', ['valid_from'], unique=False)
    op.create_index(op.f('ix_weather_forecasts_ingested_at'), 'weather_forecasts', ['ingested_at'], unique=False)

    op.create_table('tide_predictions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('source_record_id', sa.String(length=200), nullable=True),
        sa.Column('location_name', sa.String(length=200), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('geom', point_type, nullable=True),
        sa.Column('event_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('tide_height_m', sa.Float(), nullable=True),
        sa.Column('tide_type', sa.String(length=10), nullable=False),
        sa.Column('is_prediction', sa.Boolean(), nullable=False),
        sa.Column('source_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('quality', sa.String(length=20), nullable=False),
        sa.Column('raw_payload', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'source_record_id',
                            name='uq_tides_source_record', postgresql_nulls_not_distinct=True)
    )
    if _is_postgresql():
        op.create_index('idx_tides_geom', 'tide_predictions', ['geom'], unique=False, postgresql_using='gist')
    else:
        op.create_index('idx_tides_geom', 'tide_predictions', ['geom'], unique=False)
    op.create_index(op.f('ix_tide_predictions_source'), 'tide_predictions', ['source'], unique=False)
    op.create_index(op.f('ix_tide_predictions_source_record_id'), 'tide_predictions', ['source_record_id'], unique=False)
    op.create_index(op.f('ix_tide_predictions_event_time'), 'tide_predictions', ['event_time'], unique=False)
    op.create_index(op.f('ix_tide_predictions_ingested_at'), 'tide_predictions', ['ingested_at'], unique=False)

    op.create_table('pfz_zones',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('source_record_id', sa.String(length=200), nullable=True),
        sa.Column('geometry', polygon_type, nullable=True),
        sa.Column('centroid_longitude', sa.Float(), nullable=True),
        sa.Column('centroid_latitude', sa.Float(), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('species', _array_type(sa.String(length=100)), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('source_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('quality', sa.String(length=20), nullable=False),
        sa.Column('raw_payload', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'source_record_id',
                            name='uq_pfz_source_record', postgresql_nulls_not_distinct=True)
    )
    if _is_postgresql():
        op.create_index('idx_pfz_geometry', 'pfz_zones', ['geometry'], unique=False, postgresql_using='gist')
    else:
        op.create_index('idx_pfz_geometry', 'pfz_zones', ['geometry'], unique=False)
    op.create_index(op.f('ix_pfz_zones_source'), 'pfz_zones', ['source'], unique=False)
    op.create_index(op.f('ix_pfz_zones_source_record_id'), 'pfz_zones', ['source_record_id'], unique=False)
    op.create_index(op.f('ix_pfz_zones_generated_at'), 'pfz_zones', ['generated_at'], unique=False)
    op.create_index(op.f('ix_pfz_zones_ingested_at'), 'pfz_zones', ['ingested_at'], unique=False)

    op.create_table('marine_warnings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('source_record_id', sa.String(length=200), nullable=True),
        sa.Column('warning_id', sa.String(length=200), nullable=False),
        sa.Column('warning_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=30), nullable=False),
        sa.Column('geometry', polygon_type, nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('warning_id', name='uq_marine_warning_id')
    )
    if _is_postgresql():
        op.create_index('idx_marine_warnings_geometry', 'marine_warnings', ['geometry'], unique=False, postgresql_using='gist')
    else:
        op.create_index('idx_marine_warnings_geometry', 'marine_warnings', ['geometry'], unique=False)
    op.create_index(op.f('ix_marine_warnings_source'), 'marine_warnings', ['source'], unique=False)
    op.create_index(op.f('ix_marine_warnings_source_record_id'), 'marine_warnings', ['source_record_id'], unique=False)
    op.create_index(op.f('ix_marine_warnings_ingested_at'), 'marine_warnings', ['ingested_at'], unique=False)

    op.create_table('restricted_areas',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('source_record_id', sa.String(length=200), nullable=True),
        sa.Column('area_id', sa.String(length=200), nullable=False),
        sa.Column('area_name', sa.String(length=300), nullable=False),
        sa.Column('restriction_kind', sa.String(length=30), nullable=False),
        sa.Column('restriction_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=30), nullable=False),
        sa.Column('geometry', polygon_type, nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('area_id', name='uq_restricted_area_id')
    )
    if _is_postgresql():
        op.create_index('idx_restricted_areas_geometry', 'restricted_areas', ['geometry'], unique=False, postgresql_using='gist')
    else:
        op.create_index('idx_restricted_areas_geometry', 'restricted_areas', ['geometry'], unique=False)
    op.create_index(op.f('ix_restricted_areas_source'), 'restricted_areas', ['source'], unique=False)
    op.create_index(op.f('ix_restricted_areas_source_record_id'), 'restricted_areas', ['source_record_id'], unique=False)
    op.create_index(op.f('ix_restricted_areas_ingested_at'), 'restricted_areas', ['ingested_at'], unique=False)

    op.create_table('ingestion_runs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('product', sa.String(length=100), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('records_fetched', sa.Integer(), nullable=False),
        sa.Column('records_quality_valid', sa.Integer(), nullable=False),
        sa.Column('records_quality_suspicious', sa.Integer(), nullable=False),
        sa.Column('records_quality_invalid', sa.Integer(), nullable=False),
        sa.Column('records_inserted', sa.Integer(), nullable=False),
        sa.Column('records_duplicates', sa.Integer(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('error_category', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ingestion_runs_source'), 'ingestion_runs', ['source'], unique=False)
    op.create_index(op.f('ix_ingestion_runs_product'), 'ingestion_runs', ['product'], unique=False)
    op.create_index(op.f('ix_ingestion_runs_started_at'), 'ingestion_runs', ['started_at'], unique=False)


def downgrade() -> None:
    op.drop_table('ingestion_runs')
    op.drop_index(op.f('ix_restricted_areas_ingested_at'), table_name='restricted_areas')
    op.drop_index(op.f('ix_restricted_areas_source_record_id'), table_name='restricted_areas')
    op.drop_index(op.f('ix_restricted_areas_source'), table_name='restricted_areas')
    op.drop_index('idx_restricted_areas_geometry', table_name='restricted_areas')
    op.drop_table('restricted_areas')
    op.drop_index(op.f('ix_marine_warnings_ingested_at'), table_name='marine_warnings')
    op.drop_index(op.f('ix_marine_warnings_source_record_id'), table_name='marine_warnings')
    op.drop_index(op.f('ix_marine_warnings_source'), table_name='marine_warnings')
    op.drop_index('idx_marine_warnings_geometry', table_name='marine_warnings')
    op.drop_table('marine_warnings')
    op.drop_index(op.f('ix_pfz_zones_ingested_at'), table_name='pfz_zones')
    op.drop_index(op.f('ix_pfz_zones_generated_at'), table_name='pfz_zones')
    op.drop_index(op.f('ix_pfz_zones_source_record_id'), table_name='pfz_zones')
    op.drop_index(op.f('ix_pfz_zones_source'), table_name='pfz_zones')
    op.drop_index('idx_pfz_geometry', table_name='pfz_zones')
    op.drop_table('pfz_zones')
    op.drop_index(op.f('ix_tide_predictions_ingested_at'), table_name='tide_predictions')
    op.drop_index(op.f('ix_tide_predictions_event_time'), table_name='tide_predictions')
    op.drop_index(op.f('ix_tide_predictions_source_record_id'), table_name='tide_predictions')
    op.drop_index(op.f('ix_tide_predictions_source'), table_name='tide_predictions')
    op.drop_index('idx_tides_geom', table_name='tide_predictions')
    op.drop_table('tide_predictions')
    op.drop_index(op.f('ix_weather_forecasts_ingested_at'), table_name='weather_forecasts')
    op.drop_index(op.f('ix_weather_forecasts_valid_from'), table_name='weather_forecasts')
    op.drop_index(op.f('ix_weather_forecasts_issue_time'), table_name='weather_forecasts')
    op.drop_index(op.f('ix_weather_forecasts_source_record_id'), table_name='weather_forecasts')
    op.drop_index(op.f('ix_weather_forecasts_source'), table_name='weather_forecasts')
    op.drop_index('idx_weather_fc_geom', table_name='weather_forecasts')
    op.drop_table('weather_forecasts')
    op.drop_index(op.f('ix_weather_observations_ingested_at'), table_name='weather_observations')
    op.drop_index(op.f('ix_weather_observations_valid_time'), table_name='weather_observations')
    op.drop_index(op.f('ix_weather_observations_source_record_id'), table_name='weather_observations')
    op.drop_index(op.f('ix_weather_observations_source'), table_name='weather_observations')
    op.drop_index('idx_weather_obs_geom', table_name='weather_observations')
    op.drop_table('weather_observations')
    op.drop_index('idx_ocean_obs_time_loc', table_name='ocean_observations')
    op.drop_index(op.f('ix_ocean_observations_ingested_at'), table_name='ocean_observations')
    op.drop_index(op.f('ix_ocean_observations_observation_time'), table_name='ocean_observations')
    op.drop_index(op.f('ix_ocean_observations_source_record_id'), table_name='ocean_observations')
    op.drop_index(op.f('ix_ocean_observations_source'), table_name='ocean_observations')
    op.drop_index('idx_ocean_obs_geom', table_name='ocean_observations')
    op.drop_table('ocean_observations')
    op.drop_index(op.f('ix_source_capabilities_data_product'), table_name='source_capabilities')
    op.drop_index(op.f('ix_source_capabilities_source_id'), table_name='source_capabilities')
    op.drop_table('source_capabilities')
    op.drop_index(op.f('ix_sources_last_successful_fetch'), table_name='sources')
    op.drop_index(op.f('ix_sources_name'), table_name='sources')
    op.drop_table('sources')