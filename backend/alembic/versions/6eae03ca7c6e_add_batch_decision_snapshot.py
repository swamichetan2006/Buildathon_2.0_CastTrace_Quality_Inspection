"""add_batch_decision_snapshot

Revision ID: 6eae03ca7c6e
Revises: efab9b52e6d8
Create Date: 2026-10-22 15:54:36.609702

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6eae03ca7c6e'
down_revision: Union[str, Sequence[str], None] = 'efab9b52e6d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('batch_decisions', sa.Column('snapshot', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('batch_decisions') as batch_op:
        batch_op.drop_column('snapshot')
