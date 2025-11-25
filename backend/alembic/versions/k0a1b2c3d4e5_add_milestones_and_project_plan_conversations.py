"""Add milestones and project_plan_conversations tables

Revision ID: k0a1b2c3d4e5
Revises: 5061233dccf1
Create Date: 2025-11-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'k0a1b2c3d4e5'
down_revision = '5061233dccf1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create milestones table
    op.create_table(
        'milestones',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('target_date', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'IN_PROGRESS', 'COMPLETED', name='milestonestatus'), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for milestones
    op.create_index(op.f('ix_milestones_project_id'), 'milestones', ['project_id'], unique=False)
    op.create_index('ix_milestones_target_date', 'milestones', ['target_date'], unique=False)
    op.create_index('ix_milestones_status', 'milestones', ['status'], unique=False)
    
    # Create project_plan_conversations table
    op.create_table(
        'project_plan_conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('last_intent', sa.String(), nullable=True),
        sa.Column('pending_confirmation', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('conversation_history', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for project_plan_conversations
    op.create_index(op.f('ix_project_plan_conversations_user_id'), 'project_plan_conversations', ['user_id'], unique=False)
    op.create_index(op.f('ix_project_plan_conversations_project_id'), 'project_plan_conversations', ['project_id'], unique=False)


def downgrade() -> None:
    # Drop project_plan_conversations table and indexes
    op.drop_index(op.f('ix_project_plan_conversations_project_id'), table_name='project_plan_conversations')
    op.drop_index(op.f('ix_project_plan_conversations_user_id'), table_name='project_plan_conversations')
    op.drop_table('project_plan_conversations')
    
    # Drop milestones table and indexes
    op.drop_index('ix_milestones_status', table_name='milestones')
    op.drop_index('ix_milestones_target_date', table_name='milestones')
    op.drop_index(op.f('ix_milestones_project_id'), table_name='milestones')
    op.drop_table('milestones')
    
    # Drop enum types
    op.execute('DROP TYPE milestonestatus')
