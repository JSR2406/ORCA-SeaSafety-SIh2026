"""phase9 restriction lifecycle + change detection (Phase 9)

Extends the dynamic restrictions table for the operational lifecycle:
- `cancelled` boolean so a source can authoritatively cancel/withdraw an
  advisory (a revoked notice must never remain active or bind a route).
- `updated_at` timestamp recording when the record last changed (for change
  detection / audit and observability).

Revision ID: f3d2c1b0a9e8
Revises: e9a8f7c6b5d4
Create Date: 2026-08-31 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3d2c1b0a9e8'
down_revision: Union[str, None] = 'e9a8f7c6b5d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('dynamic_restrictions', sa.Column(
        'cancelled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('dynamic_restrictions', sa.Column(
        'updated_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_dynamic_restrictions_cancelled'),
                    'dynamic_restrictions', ['cancelled'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_dynamic_restrictions_cancelled'),
                  table_name='dynamic_restrictions')
    op.drop_column('dynamic_restrictions', 'updated_at')
    op.drop_column('dynamic_restrictions', 'cancelled')
