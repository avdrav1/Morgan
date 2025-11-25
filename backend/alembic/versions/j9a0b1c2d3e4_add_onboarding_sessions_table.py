"""add onboarding sessions table

Revision ID: j9a0b1c2d3e4
Revises: i8a9b0c1d2e3
Create Date: 2024-11-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'j9a0b1c2d3e4'
down_revision = 'i8a9b0c1d2e3'
branch_labels = None
depends_on = None


def upgrade():
    """Create onboarding_sessions table.
    
    This migration is written to be idempotent so that it can run safely
    even if the table was already created manually.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    existing_tables = inspector.get_table_names()
    
    if "onboarding_sessions" not in existing_tables:
        op.create_table(
            'onboarding_sessions',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('discord_id', sa.String(), nullable=False),
            sa.Column('current_state', sa.Enum(
                'WELCOME', 'COLLECT_PROJECT_NAME', 'COLLECT_GOAL', 'COLLECT_DEADLINE',
                'CONFIRM_DEADLINE', 'COLLECT_CHECKIN_FREQUENCY', 'COLLECT_TONE',
                'CONFIRM_DETAILS', 'CREATING_PROJECT', 'COMPLETED', 'PAUSED', 'FAILED',
                name='onboardingstate'
            ), nullable=False),
            sa.Column('started_at', sa.DateTime(), nullable=False),
            sa.Column('last_activity_at', sa.DateTime(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('project_name', sa.String(), nullable=True),
            sa.Column('project_goal', sa.Text(), nullable=True),
            sa.Column('deadline', sa.DateTime(), nullable=True),
            sa.Column('checkin_frequency', sa.String(), nullable=True),
            sa.Column('preferred_tone', sa.String(), nullable=True),
            sa.Column('conversation_history', postgresql.JSON(astext_type=sa.Text()), nullable=False),
            sa.Column('retry_count', sa.Integer(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Create indexes for efficient lookups
        op.create_index('ix_onboarding_sessions_user_id', 'onboarding_sessions', ['user_id'], unique=False)
        op.create_index('ix_onboarding_sessions_discord_id', 'onboarding_sessions', ['discord_id'], unique=False)


def downgrade():
    """Drop onboarding_sessions table.
    
    This is also written defensively so it won't fail if the table
    was already removed.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    existing_tables = inspector.get_table_names()
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("onboarding_sessions")} if "onboarding_sessions" in existing_tables else set()
    
    # Drop indexes first
    if "ix_onboarding_sessions_discord_id" in existing_indexes:
        op.drop_index('ix_onboarding_sessions_discord_id', table_name='onboarding_sessions')
    if "ix_onboarding_sessions_user_id" in existing_indexes:
        op.drop_index('ix_onboarding_sessions_user_id', table_name='onboarding_sessions')
    
    # Drop table
    if "onboarding_sessions" in existing_tables:
        op.drop_table('onboarding_sessions')
    
    # Drop enum type
    op.execute("DROP TYPE IF EXISTS onboardingstate")
