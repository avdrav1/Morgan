"""
Property-based tests for change confirmation requirement.

Feature: discord-project-plan-management, Property 9: Change confirmation requirement
Validates: Requirements 3.4, 4.3
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import event

from app.core.database import Base
from app.models import User, Project, ProjectStatus
from app.models.project_plan_conversation import ProjectPlanConversation
from app.services.project_plan_conversation_manager import ProjectPlanConversationManager
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
def destructive_operation_data(draw):
    """Generate data for destructive operations that require confirmation."""
    operation_type = draw(st.sampled_from([
        "delete_milestone",
        "deadline_change",
        "delete_project",
        "clear_milestones"
    ]))
    
    # Generate operation-specific data
    if operation_type == "delete_milestone":
        data = {
            "milestone_id": str(draw(st.uuids())),
            "milestone_title": draw(st.text(min_size=1, max_size=100))
        }
    elif operation_type == "deadline_change":
        # Significant deadline change (shortening by more than 7 days)
        days_shortened = draw(st.integers(min_value=8, max_value=90))
        old_deadline = datetime.utcnow() + timedelta(days=30)
        new_deadline = datetime.utcnow() + timedelta(days=30 - days_shortened)
        data = {
            "old_deadline": old_deadline.isoformat(),
            "new_deadline": new_deadline.isoformat(),
            "affected_milestones": draw(st.integers(min_value=1, max_value=10))
        }
    elif operation_type == "delete_project":
        data = {
            "project_id": str(draw(st.uuids())),
            "project_title": draw(st.text(min_size=1, max_size=100))
        }
    else:  # clear_milestones
        data = {
            "milestone_count": draw(st.integers(min_value=1, max_value=20))
        }
    
    return {
        "type": operation_type,
        "data": data
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
    project=project_data(),
    operation=destructive_operation_data()
)
def test_destructive_operations_require_confirmation(user, project, operation):
    """
    Property 9: Change confirmation requirement
    
    For any destructive operation (delete milestone, shorten deadline significantly), 
    the system should require explicit user confirmation before applying the change.
    
    This test verifies that:
    1. Pending confirmations can be set for destructive operations
    2. Pending confirmations contain the operation type and data
    3. Pending confirmations can be retrieved
    4. Pending confirmations persist across multiple retrievals
    5. Pending confirmations can be cleared after user response
    
    Validates: Requirements 3.4, 4.3
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
        
        # Create conversation manager
        manager = ProjectPlanConversationManager(db_session)
        
        # Set pending confirmation for the destructive operation
        manager.set_pending_confirmation(
            user_id=db_user.id,
            project_id=db_project.id,
            confirmation_type=operation["type"],
            data=operation["data"]
        )
        
        # Property verification 1: Pending confirmation should be retrievable
        pending = manager.get_pending_confirmation(
            user_id=db_user.id,
            project_id=db_project.id
        )
        
        assert pending is not None, \
            "Pending confirmation should be set for destructive operations"
        
        # Property verification 2: Pending confirmation should contain operation type
        assert "type" in pending, \
            "Pending confirmation should contain 'type' field"
        assert pending["type"] == operation["type"], \
            f"Pending confirmation type should be '{operation['type']}', got '{pending['type']}'"
        
        # Property verification 3: Pending confirmation should contain operation data
        assert "data" in pending, \
            "Pending confirmation should contain 'data' field"
        assert pending["data"] == operation["data"], \
            "Pending confirmation data should match the operation data"
        
        # Property verification 4: Pending confirmation should have a timestamp
        assert "created_at" in pending, \
            "Pending confirmation should have a 'created_at' timestamp"
        
        # Verify timestamp is valid ISO format
        try:
            datetime.fromisoformat(pending["created_at"])
        except ValueError:
            pytest.fail(f"Pending confirmation timestamp should be valid ISO format, got '{pending['created_at']}'")
        
        # Property verification 5: Retrieving pending confirmation multiple times returns same data
        pending_again = manager.get_pending_confirmation(
            user_id=db_user.id,
            project_id=db_project.id
        )
        
        assert pending_again is not None, \
            "Pending confirmation should persist across retrievals"
        assert pending_again["type"] == pending["type"], \
            "Pending confirmation type should be consistent across retrievals"
        assert pending_again["data"] == pending["data"], \
            "Pending confirmation data should be consistent across retrievals"
        
        # Property verification 6: Clearing pending confirmation removes it
        manager.clear_pending_confirmation(
            user_id=db_user.id,
            project_id=db_project.id
        )
        
        pending_after_clear = manager.get_pending_confirmation(
            user_id=db_user.id,
            project_id=db_project.id
        )
        
        assert pending_after_clear is None, \
            "Pending confirmation should be None after clearing"
    
    finally:
        db_session.close()


@settings(max_examples=100, deadline=None)
@given(
    user=user_data(),
    project=project_data(),
    operation1=destructive_operation_data(),
    operation2=destructive_operation_data()
)
def test_pending_confirmation_replacement(user, project, operation1, operation2):
    """
    Property 9 (replacement): Only one pending confirmation at a time
    
    For any conversation, setting a new pending confirmation should replace 
    any existing pending confirmation.
    
    This ensures users are only asked to confirm one operation at a time.
    
    Validates: Requirements 3.4, 4.3
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
        
        # Create conversation manager
        manager = ProjectPlanConversationManager(db_session)
        
        # Set first pending confirmation
        manager.set_pending_confirmation(
            user_id=db_user.id,
            project_id=db_project.id,
            confirmation_type=operation1["type"],
            data=operation1["data"]
        )
        
        # Set second pending confirmation (should replace first)
        manager.set_pending_confirmation(
            user_id=db_user.id,
            project_id=db_project.id,
            confirmation_type=operation2["type"],
            data=operation2["data"]
        )
        
        # Retrieve pending confirmation
        pending = manager.get_pending_confirmation(
            user_id=db_user.id,
            project_id=db_project.id
        )
        
        # Property verification: Only the second confirmation should be present
        assert pending is not None, \
            "Pending confirmation should exist"
        assert pending["type"] == operation2["type"], \
            f"Pending confirmation should be the second operation ('{operation2['type']}'), " \
            f"not the first ('{operation1['type']}')"
        assert pending["data"] == operation2["data"], \
            "Pending confirmation data should match the second operation"
    
    finally:
        db_session.close()


@settings(max_examples=100, deadline=None)
@given(
    user=user_data(),
    project1=project_data(),
    project2=project_data(),
    operation1=destructive_operation_data(),
    operation2=destructive_operation_data()
)
def test_pending_confirmation_isolation_between_projects(user, project1, project2, operation1, operation2):
    """
    Property 9 (isolation): Pending confirmations are isolated between projects
    
    For any user with multiple projects, pending confirmations for one project 
    should not affect or appear in another project's conversation.
    
    Validates: Requirements 3.4, 4.3
    """
    # Create a fresh session for this test run
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(**user)
        db_session.add(db_user)
        db_session.commit()
        db_session.refresh(db_user)
        
        # Create two projects
        db_project1 = Project(user_id=db_user.id, **project1)
        db_project2 = Project(user_id=db_user.id, **project2)
        db_session.add(db_project1)
        db_session.add(db_project2)
        db_session.commit()
        db_session.refresh(db_project1)
        db_session.refresh(db_project2)
        
        # Create conversation manager
        manager = ProjectPlanConversationManager(db_session)
        
        # Set pending confirmation for project 1
        manager.set_pending_confirmation(
            user_id=db_user.id,
            project_id=db_project1.id,
            confirmation_type=operation1["type"],
            data=operation1["data"]
        )
        
        # Set pending confirmation for project 2
        manager.set_pending_confirmation(
            user_id=db_user.id,
            project_id=db_project2.id,
            confirmation_type=operation2["type"],
            data=operation2["data"]
        )
        
        # Retrieve pending confirmations for both projects
        pending1 = manager.get_pending_confirmation(
            user_id=db_user.id,
            project_id=db_project1.id
        )
        pending2 = manager.get_pending_confirmation(
            user_id=db_user.id,
            project_id=db_project2.id
        )
        
        # Property verification 1: Both projects should have their own pending confirmations
        assert pending1 is not None, \
            "Project 1 should have a pending confirmation"
        assert pending2 is not None, \
            "Project 2 should have a pending confirmation"
        
        # Property verification 2: Each project's confirmation should match what was set
        assert pending1["type"] == operation1["type"], \
            f"Project 1 confirmation type should be '{operation1['type']}', got '{pending1['type']}'"
        assert pending1["data"] == operation1["data"], \
            "Project 1 confirmation data should match operation1"
        
        assert pending2["type"] == operation2["type"], \
            f"Project 2 confirmation type should be '{operation2['type']}', got '{pending2['type']}'"
        assert pending2["data"] == operation2["data"], \
            "Project 2 confirmation data should match operation2"
        
        # Property verification 3: Clearing one project's confirmation doesn't affect the other
        manager.clear_pending_confirmation(
            user_id=db_user.id,
            project_id=db_project1.id
        )
        
        pending1_after_clear = manager.get_pending_confirmation(
            user_id=db_user.id,
            project_id=db_project1.id
        )
        pending2_after_clear = manager.get_pending_confirmation(
            user_id=db_user.id,
            project_id=db_project2.id
        )
        
        assert pending1_after_clear is None, \
            "Project 1 pending confirmation should be cleared"
        assert pending2_after_clear is not None, \
            "Project 2 pending confirmation should still exist"
        assert pending2_after_clear["type"] == operation2["type"], \
            "Project 2 confirmation should be unchanged"
    
    finally:
        db_session.close()
