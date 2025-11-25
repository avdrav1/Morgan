"""
Property-based tests for multi-project context isolation.

Feature: discord-project-plan-management, Property 6: Multi-project context isolation
Validates: Requirements 7.1, 7.2, 7.3
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
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


@settings(max_examples=100, deadline=None)
@given(
    user=user_data(),
    project1=project_data(),
    project2=project_data(),
    milestones1=st.lists(milestone_data(), min_size=1, max_size=5),
    milestones2=st.lists(milestone_data(), min_size=1, max_size=5)
)
def test_multi_project_context_isolation(user, project1, project2, milestones1, milestones2):
    """
    Property 6: Multi-project context isolation
    
    For any user with multiple projects, operations on one project should not 
    affect the data or state of other projects.
    
    This test verifies that:
    1. A user can have multiple projects
    2. Retrieving one project returns only that project's data
    3. Milestones are correctly associated with their respective projects
    4. Operations on one project don't affect other projects
    5. Each project maintains its own independent state
    
    Validates: Requirements 7.1, 7.2, 7.3
    """
    # Ensure projects have different titles to avoid confusion
    assume(project1['title'] != project2['title'])
    
    # Create a fresh session for this test run
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(**user)
        db_session.add(db_user)
        db_session.commit()
        db_session.refresh(db_user)
        
        # Create first project
        db_project1 = Project(user_id=db_user.id, **project1)
        db_session.add(db_project1)
        db_session.commit()
        db_session.refresh(db_project1)
        
        # Create second project
        db_project2 = Project(user_id=db_user.id, **project2)
        db_session.add(db_project2)
        db_session.commit()
        db_session.refresh(db_project2)
        
        # Create milestones for first project
        created_milestones1 = []
        for milestone_dict in milestones1:
            milestone = Milestone(
                project_id=db_project1.id,
                **milestone_dict
            )
            db_session.add(milestone)
            created_milestones1.append(milestone)
        
        # Create milestones for second project
        created_milestones2 = []
        for milestone_dict in milestones2:
            milestone = Milestone(
                project_id=db_project2.id,
                **milestone_dict
            )
            db_session.add(milestone)
            created_milestones2.append(milestone)
        
        db_session.commit()
        
        # Refresh all milestones
        for milestone in created_milestones1 + created_milestones2:
            db_session.refresh(milestone)
        
        # Create service
        service = ProjectPlanService(db_session)
        
        # Run async functions
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Retrieve first project
            result1 = loop.run_until_complete(
                service.get_project_plan(user_id=db_user.id, project_id=db_project1.id)
            )
            
            # Retrieve second project
            result2 = loop.run_until_complete(
                service.get_project_plan(user_id=db_user.id, project_id=db_project2.id)
            )
        finally:
            loop.close()
        
        # Property verification 1: Both projects should be retrievable
        assert result1 is not None, \
            "First project should be retrievable"
        assert result2 is not None, \
            "Second project should be retrievable"
        
        # Property verification 2: Each result should contain the correct project
        assert result1['project'].id == db_project1.id, \
            "First result should contain first project"
        assert result2['project'].id == db_project2.id, \
            "Second result should contain second project"
        
        # Property verification 3: Projects should have different IDs
        assert result1['project'].id != result2['project'].id, \
            "Projects should have different IDs"
        
        # Property verification 4: Each project should have its own milestones
        assert len(result1['milestones']) == len(milestones1), \
            f"First project should have {len(milestones1)} milestones, got {len(result1['milestones'])}"
        assert len(result2['milestones']) == len(milestones2), \
            f"Second project should have {len(milestones2)} milestones, got {len(result2['milestones'])}"
        
        # Property verification 5: Milestones should not overlap between projects
        milestone_ids1 = {m.id for m in result1['milestones']}
        milestone_ids2 = {m.id for m in result2['milestones']}
        
        assert len(milestone_ids1.intersection(milestone_ids2)) == 0, \
            "Projects should not share any milestones"
        
        # Property verification 6: All milestones should belong to correct project
        for milestone in result1['milestones']:
            assert milestone.project_id == db_project1.id, \
                f"Milestone {milestone.id} should belong to project 1"
        
        for milestone in result2['milestones']:
            assert milestone.project_id == db_project2.id, \
                f"Milestone {milestone.id} should belong to project 2"
        
        # Property verification 7: Modifying one project doesn't affect the other
        # Mark a milestone in project 1 as complete
        if created_milestones1:
            first_milestone = created_milestones1[0]
            first_milestone.status = MilestoneStatus.COMPLETED
            first_milestone.completed_at = datetime.utcnow()
            db_session.commit()
            
            # Retrieve both projects again
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result1_after = loop.run_until_complete(
                    service.get_project_plan(user_id=db_user.id, project_id=db_project1.id)
                )
                result2_after = loop.run_until_complete(
                    service.get_project_plan(user_id=db_user.id, project_id=db_project2.id)
                )
            finally:
                loop.close()
            
            # Verify project 1 has the change
            completed_in_project1 = [m for m in result1_after['milestones'] if m.status == MilestoneStatus.COMPLETED]
            assert len(completed_in_project1) >= 1, \
                "Project 1 should have at least one completed milestone"
            
            # Verify project 2 is unchanged
            assert len(result2_after['milestones']) == len(milestones2), \
                "Project 2 should still have the same number of milestones"
            
            # Verify project 2's milestone statuses match original by ID
            original_statuses = {m.id: m.status for m in created_milestones2}
            for milestone in result2_after['milestones']:
                original_status = original_statuses[milestone.id]
                assert milestone.status == original_status, \
                    f"Project 2 milestone {milestone.id} status should be unchanged (expected {original_status}, got {milestone.status})"
    
    finally:
        db_session.close()


@settings(max_examples=100)
@given(
    user=user_data(),
    projects=st.lists(project_data(), min_size=2, max_size=5)
)
def test_multi_project_retrieval_without_project_id(user, projects):
    """
    Property 6 (edge case): Multi-project retrieval without specifying project ID
    
    For any user with multiple projects, requesting a project plan without 
    specifying a project ID should return the most recently updated project.
    
    Validates: Requirements 7.1, 7.3
    """
    # Ensure all projects have unique titles
    titles = [p['title'] for p in projects]
    assume(len(titles) == len(set(titles)))
    
    # Create a fresh session for this test run
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(**user)
        db_session.add(db_user)
        db_session.commit()
        db_session.refresh(db_user)
        
        # Create projects with staggered update times
        created_projects = []
        for i, project_dict in enumerate(projects):
            db_project = Project(user_id=db_user.id, **project_dict)
            db_session.add(db_project)
            db_session.commit()
            db_session.refresh(db_project)
            
            # Update the updated_at timestamp to ensure ordering
            db_project.updated_at = datetime.utcnow() + timedelta(seconds=i)
            db_session.commit()
            db_session.refresh(db_project)
            
            created_projects.append(db_project)
        
        # The most recently updated project should be the last one
        most_recent_project = created_projects[-1]
        
        # Create service and retrieve project plan without specifying project_id
        service = ProjectPlanService(db_session)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                service.get_project_plan(user_id=db_user.id, project_id=None)
            )
        finally:
            loop.close()
        
        # Property verification: Should return the most recently updated project
        assert result is not None, \
            "Should return a project when user has multiple projects"
        assert result['project'].id == most_recent_project.id, \
            f"Should return the most recently updated project (expected {most_recent_project.id}, got {result['project'].id})"
        assert result['project'].title == most_recent_project.title, \
            "Returned project should have the correct title"
    
    finally:
        db_session.close()
