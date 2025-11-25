"""Add suggestion_tracking table

Revision ID: l1a2b3c4d5e6
Revises: k0a1b2c3d4e5
Create Date: 2025-11-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'l1a2b3c4d5e6'
down_revision = 'k0a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create suggestion_tracking table
    op.create_table(
        'suggestion_tracking',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('suggestion_type', sa.String(), nullable=False),
        sa.Column('suggestion_hash', sa.String(), nullable=False),
        sa.Column('message', sa.String(), nullable=False),
        sa.Column('reasoning', sa.String(), nullable=False),
        sa.Column('shown_at', sa.DateTime(), nullable=False),
        sa.Column('user_response', sa.String(), nullable=True),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for suggestion_tracking
    op.create_index(op.f('ix_suggestion_tracking_project_id'), 'suggestion_tracking', ['project_id'], unique=False)
    op.create_index(op.f('ix_suggestion_tracking_user_id'), 'suggestion_tracking', ['user_id'], unique=False)
    op.create_index(op.f('ix_suggestion_tracking_suggestion_hash'), 'suggestion_tracking', ['suggestion_hash'], unique=False)


def downgrade() -> None:
    # Drop suggestion_tracking table and indexes
    op.drop_index(op.f('ix_suggestion_tracking_suggestion_hash'), table_name='suggestion_tracking')
    op.drop_index(op.f('ix_suggestion_tracking_user_id'), table_name='suggestion_tracking')
    op.drop_index(op.f('ix_suggestion_tracking_project_id'), table_name='suggestion_tracking')
    op.drop_table('suggestion_tracking')
