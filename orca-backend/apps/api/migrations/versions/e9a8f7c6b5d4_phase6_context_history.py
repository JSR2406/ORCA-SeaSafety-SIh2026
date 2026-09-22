"""phase 6 - persistent conversation history

Adds the `history` JSON column to conversation_contexts so multi-turn context
(language, resolved location, resolved time, last intent AND the message
history the assistant needs to resolve follow-ups like "20 km south.") can
survive process restarts.  The column is JSON: history is a bounded, ordered
list of {request_id, intent, message, language, ...} turn records.

Revision ID: e9a8f7c6b5d4
Revises: c5a7e9f1b2d3
Create Date: 2026-08-31 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9a8f7c6b5d4'
down_revision: Union[str, None] = 'c5a7e9f1b2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'conversation_contexts',
        sa.Column('history', sa.JSON(), nullable=True))


def downgrade() -> None:
    try:
        op.drop_column('conversation_contexts', 'history')
    except Exception:
        # SQLite < 3.35 cannot drop columns; the column is nullable so leaving
        # it behind is harmless for downgrade-on-sqlite.
        pass