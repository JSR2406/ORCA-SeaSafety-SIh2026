"""knowledge base + marine evidence + pgvector

Adds the hybrid-retrieval foundation:
  * knowledge_documents / knowledge_chunks  - curated marine knowledge (real
    documents only, never fabricated) with a pgvector embedding column and a
    PostgreSQL FTS expression index for hybrid search.
  * marine_evidence                          - durable evidence/provenance for
    every fact an agent asserts about live marine data (query_run, agent,
    tool, source, coordinates, payload).

Revision ID: 0f7e1a2b3c4d
Revises: 8f51d7a9c3b2
Create Date: 2026-08-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = '0f7e1a2b3c4d'
down_revision: Union[str, None] = '8f51d7a9c3b2'
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


def upgrade() -> None:
    # pgvector extension - only meaningful on PostgreSQL.
    if _is_postgresql():
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    array_str = _array_type(sa.String(length=100))
    point_type = _point_type()

    # ------------------------------------------------------------------ knowledge
    op.create_table('knowledge_documents',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('source_url', sa.String(length=500), nullable=True),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('tags', array_str, nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('document_hash', sa.String(length=64), nullable=False),
        sa.Column('ingestion_status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_hash', name='uq_knowledge_document_hash')
    )
    op.create_index(op.f('ix_knowledge_documents_source_type'), 'knowledge_documents', ['source_type'], unique=False)
    op.create_index(op.f('ix_knowledge_documents_ingestion_status'), 'knowledge_documents', ['ingestion_status'], unique=False)

    # embedding is created as Text so the migration runs on SQLite too; on
    # PostgreSQL it is converted to vector(1536) together with the HNSW index.
    op.create_table('knowledge_chunks',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.BigInteger(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['knowledge_documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', 'chunk_index', name='uq_knowledge_chunk_index')
    )
    op.create_index(op.f('ix_knowledge_chunks_document_id'), 'knowledge_chunks', ['document_id'], unique=False)

    if _is_postgresql():
        op.execute(
            "ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(1536) "
            "USING embedding::vector(1536)")
        op.execute(
            "CREATE INDEX idx_knowledge_chunks_embedding ON knowledge_chunks "
            "USING hnsw (embedding vector_cosine_ops)")
        op.execute(
            "CREATE INDEX idx_knowledge_chunks_fts ON knowledge_chunks "
            "USING gin (to_tsvector('english', coalesce(content, '')))")

    # ------------------------------------------------------------------ evidence
    op.create_table('marine_evidence',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('query_run_id', sa.String(length=64), nullable=False),
        sa.Column('agent_name', sa.String(length=100), nullable=False),
        sa.Column('tool_name', sa.String(length=100), nullable=False),
        sa.Column('evidence_type', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=True),
        sa.Column('source_record_id', sa.String(length=200), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('geom', point_type, nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_marine_evidence_query_run_id'), 'marine_evidence', ['query_run_id'], unique=False)
    op.create_index(op.f('ix_marine_evidence_agent_tool'), 'marine_evidence', ['agent_name', 'tool_name'], unique=False)
    op.create_index(op.f('ix_marine_evidence_source_record_id'), 'marine_evidence', ['source_record_id'], unique=False)
    if _is_postgresql():
        op.create_index('idx_marine_evidence_geom', 'marine_evidence', ['geom'], unique=False, postgresql_using='gist')
    else:
        op.create_index('idx_marine_evidence_geom', 'marine_evidence', ['geom'], unique=False)


def downgrade() -> None:
    if _is_postgresql():
        op.drop_index('idx_marine_evidence_geom', table_name='marine_evidence')
    else:
        op.drop_index('idx_marine_evidence_geom', table_name='marine_evidence')
    op.drop_index(op.f('ix_marine_evidence_source_record_id'), table_name='marine_evidence')
    op.drop_index(op.f('ix_marine_evidence_agent_tool'), table_name='marine_evidence')
    op.drop_index(op.f('ix_marine_evidence_query_run_id'), table_name='marine_evidence')
    op.drop_table('marine_evidence')

    if _is_postgresql():
        op.execute("DROP INDEX IF EXISTS idx_knowledge_chunks_fts")
        op.execute("DROP INDEX IF EXISTS idx_knowledge_chunks_embedding")
    op.drop_index(op.f('ix_knowledge_chunks_document_id'), table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')

    op.drop_index(op.f('ix_knowledge_documents_ingestion_status'), table_name='knowledge_documents')
    op.drop_index(op.f('ix_knowledge_documents_source_type'), table_name='knowledge_documents')
    op.drop_table('knowledge_documents')