"""add messaging_paused field

Revision ID: f5a6b7c8d9e0
Revises: e3f4a5b6c7d8
Create Date: 2025-11-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f5a6b7c8d9e0'
down_revision = 'e3f4a5b6c7d8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add messaging_paused field to users table
    op.add_column('users', sa.Column('messaging_paused', sa.Boolean(), nullable=True, server_default='false'))


def downgrade() -> None:
    # Remove messaging_paused field from users table
    op.drop_column('users', 'messaging_paused')
