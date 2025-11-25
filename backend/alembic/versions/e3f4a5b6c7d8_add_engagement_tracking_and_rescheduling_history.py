"""add engagement tracking and rescheduling history

Revision ID: e3f4a5b6c7d8
Revises: d20a51080f23
Create Date: 2025-11-21 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e3f4a5b6c7d8'
down_revision = 'd20a51080f23'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add engagement tracking fields to users table
    op.add_column('users', sa.Column('total_check_ins_sent', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('users', sa.Column('total_check_ins_responded', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('users', sa.Column('consecutive_missed_check_ins', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('users', sa.Column('last_active_at', sa.DateTime(), nullable=True))
    
    # Add ghosting tracking to projects table
    op.add_column('projects', sa.Column('ghosting_stage', sa.Integer(), nullable=True, server_default='0'))
    
    # Add blocker_diagnosed_at to tasks table
    op.add_column('tasks', sa.Column('blocker_diagnosed_at', sa.DateTime(), nullable=True))
    
    # Add response tracking fields to check_ins table
    op.add_column('check_ins', sa.Column('blocker_detected', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('check_ins', sa.Column('reschedule_initiated', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('check_ins', sa.Column('response_time_minutes', sa.Integer(), nullable=True))
    op.add_column('check_ins', sa.Column('sentiment', sa.String(), nullable=True))
    
    # Create rescheduling_history table
    op.create_table('rescheduling_history',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('task_id', sa.UUID(), nullable=False),
        sa.Column('old_due_date', sa.DateTime(), nullable=False),
        sa.Column('new_due_date', sa.DateTime(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('blocker_type', sa.String(), nullable=True),
        sa.Column('initiated_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Drop rescheduling_history table
    op.drop_table('rescheduling_history')
    
    # Remove fields from check_ins table
    op.drop_column('check_ins', 'sentiment')
    op.drop_column('check_ins', 'response_time_minutes')
    op.drop_column('check_ins', 'reschedule_initiated')
    op.drop_column('check_ins', 'blocker_detected')
    
    # Remove blocker_diagnosed_at from tasks table
    op.drop_column('tasks', 'blocker_diagnosed_at')
    
    # Remove ghosting_stage from projects table
    op.drop_column('projects', 'ghosting_stage')
    
    # Remove engagement tracking fields from users table
    op.drop_column('users', 'last_active_at')
    op.drop_column('users', 'consecutive_missed_check_ins')
    op.drop_column('users', 'total_check_ins_responded')
    op.drop_column('users', 'total_check_ins_sent')
