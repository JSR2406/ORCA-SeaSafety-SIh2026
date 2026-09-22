"""dynamic restrictions (Phase 5)

Adds the first-class DYNAMIC RESTRICTION table: live, time-windowed official
restrictions (NAVAREA/NAVTEX advisories, naval/firing exercises, temporary
closures) with idempotent refresh (unique per source + source_record_id),
priority-expiry bookkeeping and a dedicated geometry index.

Revision ID: c5a7e9f1b2d3
Revises: 1a2b3c4d5e6f
Create Date: 2026-08-30 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5a7e9f1b2d3'
down_revision: Union[str, None] = '1a2b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == 'postgresql'


def upgrade() -> None:
    if _is_postgresql():
        geometry_type = geoalchemy2.types.Geometry(
            geometry_type='GEOMETRY', srid=4326, dimension=2, spatial_index=False)
    else:
        geometry_type = sa.Text()

    op.create_table('dynamic_restrictions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('source_record_id', sa.String(length=200), nullable=False),
        sa.Column('restriction_id', sa.String(length=200), nullable=False),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('restriction_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=30), nullable=False),
        sa.Column('geometry', geometry_type, nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('official', sa.Boolean(), nullable=False),
        sa.Column('data_class', sa.String(length=30), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('refreshed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expired', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'source_record_id',
                            name='uq_dynamic_restrictions_source_record',
                            postgresql_nulls_not_distinct=True)
    )
    op.create_index(op.f('ix_dynamic_restrictions_source'), 'dynamic_restrictions', ['source'], unique=False)
    op.create_index(op.f('ix_dynamic_restrictions_source_record_id'), 'dynamic_restrictions', ['source_record_id'], unique=False)
    op.create_index(op.f('ix_dynamic_restrictions_ingested_at'), 'dynamic_restrictions', ['ingested_at'], unique=False)
    op.create_index(op.f('ix_dynamic_restrictions_expired'), 'dynamic_restrictions', ['expired'], unique=False)
    if _is_postgresql():
        op.create_index('idx_dynamic_restrictions_geometry', 'dynamic_restrictions',
                        ['geometry'], unique=False, postgresql_using='gist')


def downgrade() -> None:
    if _is_postgresql():
        op.drop_index('idx_dynamic_restrictions_geometry', table_name='dynamic_restrictions')
    op.drop_index(op.f('ix_dynamic_restrictions_expired'), table_name='dynamic_restrictions')
    op.drop_index(op.f('ix_dynamic_restrictions_ingested_at'), table_name='dynamic_restrictions')
    op.drop_index(op.f('ix_dynamic_restrictions_source_record_id'), table_name='dynamic_restrictions')
    op.drop_index(op.f('ix_dynamic_restrictions_source'), table_name='dynamic_restrictions')
    op.drop_table('dynamic_restrictions')