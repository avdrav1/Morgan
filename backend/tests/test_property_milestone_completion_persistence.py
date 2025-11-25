"""
Property-based tests for milestone completion state persistence.

Feature: discord-project-plan-management, Property 5: Milestone completion state persistence
Validates: Requirements 5.2
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import event

from app.core.database import Base
from app.models import User, Project, ProjectStatus, Milestone, MilestoneStatus
from tests.conftest import SQLiteUUID, SQLiteJSONB
from sqlalchemy.dialects.postgresql import UUID, JSONB


@st.composite
def user_data(draw):
    """Generate valid user data."""
    return {
        "email": draw(st.emails()),
        "hashed_password": draw(st.text(min_size=10, max_size=100)),
        "full_name": draw(st.text(min_size=1, max_size=100)),
    }


@st.composite
def project_data(draw):
    """Generate valid project data."""
    return {
        "title": draw(st.text(min_size=1, max_size=100)),
        "description": draw(st.text(min_size=1, max_size=500)),
        "goal": draw(st.text(min_size=1, max_size=500)),
        "status": ProjectStatus.ACTIVE,
    }


@st.composite
def milestone_data(draw):
    """Generate valid milestone data."""
    # Generate a target date between 1 and 90 days from now
    days_ahead = draw(st.integers(min_value=1, max_value=90))
    target_date = datetime.utcnow() + timedelta(days=days_ahead)
    
    return {
        "title": draw(st.text(min_size=1, max_size=200)),
        "description": draw(st.text(min_size=0, max_size=500)),
        "target_date": target_date,
        "status": MilestoneStatus.PENDING,
        "order": draw(st.integers(min_value=0, max_value=100)),
    }


def create_test_session():
    """Create a fresh test database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Replace UUID and JSONB columns with SQLite-compatible types
    @event.listens_for(Base.metadata, "before_create")
    def receive_before_create(target, connection, **kw):
        """Replace PostgreSQL-specific types with SQLite-compatible types."""
        for table in target.tables.values():
            for column in table.columns:
                if isinstance(column.type, UUID):
                    column.type = SQLiteUUID()
                elif isinstance(column.type, JSONB):
                    column.type = SQLiteJSONB()
    
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return TestingSessionLocal()


@settings(max_examples=100)
@given(
    user=user_data(),
    project=project_data(),
    milestones=st.lists(milestone_data(), min_size=1, max_size=10)
)
def test_milestone_completion_state_persistence(user, project, milestones):
    """
    Property 5: Milestone completion state persistence
    
    For any milestone marked as complete, subsequent retrievals of that milestone 
    should show it as completed with a completion timestamp.
    
    This test verifies that:
    1. A milestone can be marked as complete
    2. The completion status persists across database operations
    3. The completion timestamp is recorded and persists
    4. Multiple retrievals return consistent completion state
    
    Validates: Requirements 5.2
    """
    # Create a fresh session for this test run
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(**user)
        db_session.add(db_user)
        db_session.commit()
        db_session.refresh(db_user)
        
        # Create project
        db_project = Project(user_id=db_user.id, **project)
        db_session.add(db_project)
        db_session.commit()
        db_session.refresh(db_project)
        
        # Create milestones
        created_milestones = []
        for milestone_dict in milestones:
            milestone = Milestone(
                project_id=db_project.id,
                **milestone_dict
            )
            db_session.add(milestone)
            created_milestones.append(milestone)
        
        db_session.commit()
        
        # Refresh all milestones to get their IDs
        for milestone in created_milestones:
            db_session.refresh(milestone)
        
        # Mark each milestone as complete and verify persistence
        for milestone in created_milestones:
            milestone_id = milestone.id
            
            # Record the completion time
            completion_time = datetime.utcnow()
            
            # Mark milestone as complete
            milestone.status = MilestoneStatus.COMPLETED
            milestone.completed_at = completion_time
            db_session.commit()
            
            # Property verification 1: Immediate retrieval shows completion
            retrieved_milestone = db_session.query(Milestone).filter(
                Milestone.id == milestone_id
            ).first()
            
            assert retrieved_milestone is not None, \
                f"Milestone {milestone_id} should exist in database"
            
            assert retrieved_milestone.status == MilestoneStatus.COMPLETED, \
                f"Milestone {milestone_id} should be marked as COMPLETED, but status is {retrieved_milestone.status}"
            
            assert retrieved_milestone.completed_at is not None, \
                f"Milestone {milestone_id} should have a completion timestamp"
            
            # Verify the completion timestamp is close to what we set
            # (allowing for small differences due to database precision)
            time_diff = abs((retrieved_milestone.completed_at - completion_time).total_seconds())
            assert time_diff < 2, \
                f"Completion timestamp differs by {time_diff} seconds, expected < 2 seconds"
            
            # Property verification 2: Subsequent retrieval still shows completion
            # Clear the session to force a fresh database query
            db_session.expire_all()
            
            retrieved_again = db_session.query(Milestone).filter(
                Milestone.id == milestone_id
            ).first()
            
            assert retrieved_again.status == MilestoneStatus.COMPLETED, \
                f"Milestone {milestone_id} completion status should persist across queries"
            
            assert retrieved_again.completed_at is not None, \
                f"Milestone {milestone_id} completion timestamp should persist across queries"
            
            # Verify the timestamp is still the same
            assert retrieved_again.completed_at == retrieved_milestone.completed_at, \
                f"Completion timestamp should remain consistent across retrievals"
        
        # Property verification 3: All milestones remain completed after all operations
        all_milestones = db_session.query(Milestone).filter(
            Milestone.project_id == db_project.id
        ).all()
        
        assert len(all_milestones) == len(milestones), \
            f"Expected {len(milestones)} milestones, but found {len(all_milestones)}"
        
        for milestone in all_milestones:
            assert milestone.status == MilestoneStatus.COMPLETED, \
                f"All milestones should remain COMPLETED"
            assert milestone.completed_at is not None, \
                f"All milestones should have completion timestamps"
    
    finally:
        db_session.close()
