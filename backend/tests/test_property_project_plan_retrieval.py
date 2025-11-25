"""
Property-based tests for project plan retrieval completeness.

Feature: discord-project-plan-management, Property 1: Project plan retrieval completeness
Validates: Requirements 1.1, 1.2, 1.3
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import event
import asyncio

from app.core.database import Base
from app.models import User, Project, ProjectStatus, Milestone, MilestoneStatus
from app.services.project_plan_service import ProjectPlanService
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
        "target_completion_date": datetime.utcnow() + timedelta(days=draw(st.integers(min_value=7, max_value=365))),
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
        "status": draw(st.sampled_from([MilestoneStatus.PENDING, MilestoneStatus.IN_PROGRESS, MilestoneStatus.COMPLETED])),
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
def test_project_plan_retrieval_completeness(user, project, milestones):
    """
    Property 1: Project plan retrieval completeness
    
    For any user with at least one project, requesting to view their project plan 
    should return a response containing the project name, goal, deadline, and all 
    associated milestones.
    
    This test verifies that:
    1. The project plan can be retrieved for a user
    2. The returned data includes the project object with all required fields
    3. All milestones associated with the project are included
    4. Milestones are ordered chronologically by target date
    
    Validates: Requirements 1.1, 1.2, 1.3
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
        
        # Create service and retrieve project plan
        service = ProjectPlanService(db_session)
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                service.get_project_plan(user_id=db_user.id, project_id=db_project.id)
            )
        finally:
            loop.close()
        
        # Property verification 1: Result should not be None
        assert result is not None, \
            "Project plan retrieval should return a result for a user with a project"
        
        # Property verification 2: Result should contain 'project' and 'milestones' keys
        assert 'project' in result, \
            "Project plan result should contain 'project' key"
        assert 'milestones' in result, \
            "Project plan result should contain 'milestones' key"
        
        # Property verification 3: Project should have all required fields
        returned_project = result['project']
        assert returned_project is not None, \
            "Returned project should not be None"
        assert returned_project.id == db_project.id, \
            "Returned project ID should match the created project"
        assert returned_project.title == project['title'], \
            f"Project title should be '{project['title']}', got '{returned_project.title}'"
        assert returned_project.goal == project['goal'], \
            f"Project goal should be present"
        assert returned_project.target_completion_date is not None, \
            "Project deadline (target_completion_date) should be present"
        
        # Property verification 4: All milestones should be included
        returned_milestones = result['milestones']
        assert len(returned_milestones) == len(milestones), \
            f"Expected {len(milestones)} milestones, but got {len(returned_milestones)}"
        
        # Property verification 5: Milestones should be ordered chronologically
        for i in range(len(returned_milestones) - 1):
            current_date = returned_milestones[i].target_date
            next_date = returned_milestones[i + 1].target_date
            assert current_date <= next_date, \
                f"Milestones should be ordered chronologically: milestone at index {i} " \
                f"has date {current_date} which is after milestone at index {i+1} with date {next_date}"
        
        # Property verification 6: Each milestone should have required fields
        for returned_milestone in returned_milestones:
            assert returned_milestone.id is not None, \
                "Each milestone should have an ID"
            assert returned_milestone.title is not None and len(returned_milestone.title) > 0, \
                "Each milestone should have a non-empty title"
            assert returned_milestone.target_date is not None, \
                "Each milestone should have a target date"
            assert returned_milestone.status in [MilestoneStatus.PENDING, MilestoneStatus.IN_PROGRESS, MilestoneStatus.COMPLETED], \
                f"Each milestone should have a valid status, got {returned_milestone.status}"
        
        # Property verification 7: Milestone IDs should match created milestones
        returned_ids = {m.id for m in returned_milestones}
        created_ids = {m.id for m in created_milestones}
        assert returned_ids == created_ids, \
            "Returned milestone IDs should match the created milestone IDs"
    
    finally:
        db_session.close()


@settings(max_examples=100)
@given(
    user=user_data(),
    project=project_data()
)
def test_project_plan_retrieval_without_milestones(user, project):
    """
    Property 1 (edge case): Project plan retrieval with no milestones
    
    For any user with a project but no milestones, requesting to view their 
    project plan should return the project with an empty milestones list.
    
    Validates: Requirements 1.1, 1.2
    """
    # Create a fresh session for this test run
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(**user)
        db_session.add(db_user)
        db_session.commit()
        db_session.refresh(db_user)
        
        # Create project (no milestones)
        db_project = Project(user_id=db_user.id, **project)
        db_session.add(db_project)
        db_session.commit()
        db_session.refresh(db_project)
        
        # Create service and retrieve project plan
        service = ProjectPlanService(db_session)
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                service.get_project_plan(user_id=db_user.id, project_id=db_project.id)
            )
        finally:
            loop.close()
        
        # Property verification: Result should contain project with empty milestones
        assert result is not None, \
            "Project plan retrieval should return a result even with no milestones"
        assert 'project' in result, \
            "Result should contain 'project' key"
        assert 'milestones' in result, \
            "Result should contain 'milestones' key"
        assert result['project'].id == db_project.id, \
            "Returned project should match the created project"
        assert len(result['milestones']) == 0, \
            "Milestones list should be empty when no milestones exist"
    
    finally:
        db_session.close()
