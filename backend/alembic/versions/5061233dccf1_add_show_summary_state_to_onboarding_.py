"""add show_summary state to onboarding enum

Revision ID: 5061233dccf1
Revises: j9a0b1c2d3e4
Create Date: 2025-11-24 14:58:37.373517

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5061233dccf1'
down_revision = 'j9a0b1c2d3e4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add SHOW_SUMMARY to the onboardingstate enum
    # Note: ALTER TYPE ADD VALUE cannot run inside a transaction block
    from alembic import context
    connection = context.get_bind()
    
    # Check if the value already exists
    result = connection.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid "
        "WHERE t.typname = 'onboardingstate' AND e.enumlabel = 'SHOW_SUMMARY')"
    ).scalar()
    
    if not result:
        # We need to execute this outside of a transaction
        connection.execute("COMMIT")
        connection.execute("ALTER TYPE onboardingstate ADD VALUE 'SHOW_SUMMARY'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values directly
    # You would need to recreate the enum type to remove a value
    pass
