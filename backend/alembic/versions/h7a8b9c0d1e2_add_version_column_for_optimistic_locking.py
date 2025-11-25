"""add_version_column_for_optimistic_locking

Revision ID: h7a8b9c0d1e2
Revises: g6a7b8c9d0e1
Create Date: 2024-11-22 10:08:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h7a8b9c0d1e2'
down_revision = 'g6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    # Add version column to tasks table for optimistic locking
    # Requirements: 5.4 - Concurrent rescheduling protection
    op.add_column('tasks', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))


def downgrade():
    op.drop_column('tasks', 'version')
