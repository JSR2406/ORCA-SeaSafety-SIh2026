"""knowledge ingress + agentic orchestration persistence

Extends the Phase 3 knowledge foundation with the production ingestion
metadata (authority, document type, effective/expiry windows, versioning,
checksums) and per-chunk embedding bookkeeping, then adds the minimal
structured storage for agentic orchestration: conversation context, execution
runs, tasks and trace events.

Revision ID: 1a2b3c4d5e6f
Revises: 0f7e1a2b3c4d
Create Date: 2026-08-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a2b3c4d5e6f'
down_revision: Union[str, None] = '0f7e1a2b3c4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------- knowledge docs
    op.add_column('knowledge_documents', sa.Column('authority', sa.String(length=200), nullable=True))
    op.add_column('knowledge_documents', sa.Column('document_type', sa.String(length=50), nullable=False, server_default='other'))
    op.add_column('knowledge_documents', sa.Column('publication_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('knowledge_documents', sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('knowledge_documents', sa.Column('expiry_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('knowledge_documents', sa.Column('active', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('knowledge_documents', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('knowledge_documents', sa.Column('source_reference', sa.String(length=500), nullable=True))
    op.create_index('ix_knowledge_documents_active', 'knowledge_documents', ['active'], unique=False)

    # --------------------------------------------------------- knowledge chunks
    op.add_column('knowledge_chunks', sa.Column('section', sa.String(length=300), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('page', sa.Integer(), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('heading', sa.String(length=300), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('chunk_hash', sa.String(length=64), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('embedding_model', sa.String(length=100), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('embedding_version', sa.String(length=50), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('embedding_dimensions', sa.Integer(), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('embedded_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_knowledge_chunks_chunk_hash', 'knowledge_chunks', ['chunk_hash'], unique=False)

    # -------------------------------------------------- conversation context
    op.create_table('conversation_contexts',
        sa.Column('conversation_id', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.String(length=100), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('resolved_location', sa.JSON(), nullable=True),
        sa.Column('resolved_time', sa.JSON(), nullable=True),
        sa.Column('last_intent', sa.JSON(), nullable=True),
        sa.Column('preferences', sa.JSON(), nullable=True),
        sa.Column('active_scenario', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('conversation_id')
    )
    op.create_index('ix_conversation_contexts_session', 'conversation_contexts', ['session_id'], unique=False)

    # --------------------------------------------------------- execution runs
    op.create_table('execution_runs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('request_id', sa.String(length=64), nullable=False),
        sa.Column('conversation_id', sa.String(length=64), nullable=True),
        sa.Column('intent', sa.JSON(), nullable=True),
        sa.Column('plan', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_execution_runs_request_id', 'execution_runs', ['request_id'], unique=False)
    op.create_index('ix_execution_runs_conversation_id', 'execution_runs', ['conversation_id'], unique=False)

    # ---------------------------------------------------------- execution tasks
    op.create_table('execution_tasks',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.BigInteger(), nullable=False),
        sa.Column('task_id', sa.String(length=64), nullable=False),
        sa.Column('agent', sa.String(length=100), nullable=False),
        sa.Column('tool', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('dependencies', sa.JSON(), nullable=False),
        sa.Column('input_json', sa.JSON(), nullable=True),
        sa.Column('result_json', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['execution_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_execution_tasks_run_id', 'execution_tasks', ['run_id'], unique=False)

    # --------------------------------------------------------- execution events
    op.create_table('execution_events',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.BigInteger(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['execution_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_execution_events_run_id', 'execution_events', ['run_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_execution_events_run_id', table_name='execution_events')
    op.drop_table('execution_events')
    op.drop_index('ix_execution_tasks_run_id', table_name='execution_tasks')
    op.drop_table('execution_tasks')
    op.drop_index('ix_execution_runs_conversation_id', table_name='execution_runs')
    op.drop_index('ix_execution_runs_request_id', table_name='execution_runs')
    op.drop_table('execution_runs')
    op.drop_index('ix_conversation_contexts_session', table_name='conversation_contexts')
    op.drop_table('conversation_contexts')

    op.drop_index('ix_knowledge_chunks_chunk_hash', table_name='knowledge_chunks')
    op.drop_column('knowledge_chunks', 'embedded_at')
    op.drop_column('knowledge_chunks', 'embedding_dimensions')
    op.drop_column('knowledge_chunks', 'embedding_version')
    op.drop_column('knowledge_chunks', 'embedding_model')
    op.drop_column('knowledge_chunks', 'chunk_hash')
    op.drop_column('knowledge_chunks', 'heading')
    op.drop_column('knowledge_chunks', 'page')
    op.drop_column('knowledge_chunks', 'section')

    op.drop_index('ix_knowledge_documents_active', table_name='knowledge_documents')
    op.drop_column('knowledge_documents', 'source_reference')
    op.drop_column('knowledge_documents', 'version')
    op.drop_column('knowledge_documents', 'active')
    op.drop_column('knowledge_documents', 'expiry_date')
    op.drop_column('knowledge_documents', 'effective_date')
    op.drop_column('knowledge_documents', 'publication_date')
    op.drop_column('knowledge_documents', 'document_type')
    op.drop_column('knowledge_documents', 'authority')