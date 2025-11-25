"""add deletion_scheduled_at field

Revision ID: g6a7b8c9d0e1
Revises: f5a6b7c8d9e0
Create Date: 2025-11-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'g6a7b8c9d0e1'
down_revision = 'f5a6b7c8d9e0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add deletion_scheduled_at field to users table
    op.add_column('users', sa.Column('deletion_scheduled_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove deletion_scheduled_at field from users table
    op.drop_column('users', 'deletion_scheduled_at')
