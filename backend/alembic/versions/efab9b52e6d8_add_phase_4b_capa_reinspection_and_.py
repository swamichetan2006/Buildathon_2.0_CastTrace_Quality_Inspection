"""add_phase_4b_capa_reinspection_and_recurrence_fields

Revision ID: efab9b52e6d8
Revises: 1e5e96baabb8
Create Date: 2026-10-22 15:12:21.400675

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = 'efab9b52e6d8'
down_revision: Union[str, Sequence[str], None] = '1e5e96baabb8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('corrective_actions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('root_cause', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('preventive_action', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('completion_evidence_image_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('verified_by', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('verification_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('verification_status', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('rejection_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('verification_history', sqlite.JSON(), nullable=True))
        batch_op.create_foreign_key('fk_corrective_actions_completion_evidence', 'images', ['completion_evidence_image_id'], ['id'])
        batch_op.create_foreign_key('fk_corrective_actions_verified_by', 'users', ['verified_by'], ['id'])

    with op.batch_alter_table('defects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('prior_corrective_action_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_defects_prior_corrective_action_id'), ['prior_corrective_action_id'], unique=False)
        batch_op.create_foreign_key('fk_defects_prior_corrective_action_id', 'corrective_actions', ['prior_corrective_action_id'], ['id'])

    with op.batch_alter_table('reinspections', schema=None) as batch_op:
        batch_op.add_column(sa.Column('evidence_image_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key('fk_reinspections_evidence_image_id', 'images', ['evidence_image_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('reinspections', schema=None) as batch_op:
        batch_op.drop_constraint('fk_reinspections_evidence_image_id', type_='foreignkey')
        batch_op.drop_column('evidence_image_id')

    with op.batch_alter_table('defects', schema=None) as batch_op:
        batch_op.drop_constraint('fk_defects_prior_corrective_action_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_defects_prior_corrective_action_id'))
        batch_op.drop_column('prior_corrective_action_id')

    with op.batch_alter_table('corrective_actions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_corrective_actions_verified_by', type_='foreignkey')
        batch_op.drop_constraint('fk_corrective_actions_completion_evidence', type_='foreignkey')
        batch_op.drop_column('verification_history')
        batch_op.drop_column('rejection_reason')
        batch_op.drop_column('verification_status')
        batch_op.drop_column('verification_notes')
        batch_op.drop_column('verified_at')
        batch_op.drop_column('verified_by')
        batch_op.drop_column('completion_evidence_image_id')
        batch_op.drop_column('preventive_action')
        batch_op.drop_column('root_cause')
