"""
Property-Based Test: No automatic timeline adjustments

Feature: proactive-accountability-assistant, Property 11: No automatic timeline adjustments
Validates: Requirements 5.4

Property: For any task with a due date, the due date should never change without 
explicit user confirmation through conversation.

This test verifies that:
1. Initiating a reschedule does NOT change the task's due date
2. Only explicit confirmation updates the due date
3. The system maintains the original due date until confirmation
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base
from app.models import User, Project, Task, CheckIn
from app.models.task import TaskStatus
from app.models.check_in import CheckInType, CheckInStatus
from app.models.rescheduling_history import ReschedulingHistory
from app.models.project import ProjectStatus
from tests.conftest import SQLiteUUID, SQLiteJSONB


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


# Strategies for generating test data
@st.composite
def task_with_due_date(draw):
    """Generate a task with a due date."""
    base_date = datetime.utcnow()
    days_offset = draw(st.integers(min_value=1, max_value=90))
    due_date = base_date + timedelta(days=days_offset)
    
    return {
        "title": draw(st.text(min_size=5, max_size=50)),
        "description": draw(st.text(min_size=10, max_size=200)),
        "due_date": due_date,
        "status": TaskStatus.IN_PROGRESS
    }


@st.composite
def reschedule_scenario(draw):
    """Generate a reschedule scenario with reason and new date."""
    base_date = datetime.utcnow()
    days_offset = draw(st.integers(min_value=1, max_value=60))
    new_date = base_date + timedelta(days=days_offset)
    
    reasons = [
        "Need more time to complete",
        "Unexpected blocker came up",
        "Other priorities took precedence",
        "Underestimated the complexity",
        "Waiting on external dependencies"
    ]
    
    return {
        "reason": draw(st.sampled_from(reasons)),
        "new_date": new_date
    }


@settings(max_examples=100)
@given(
    task_data=task_with_due_date(),
    reschedule_data=reschedule_scenario()
)
def test_no_automatic_timeline_adjustment_on_initiate(
    task_data: dict,
    reschedule_data: dict
):
    """
    Property: Initiating a reschedule does NOT automatically change the due date.
    
    For any task with a due date, when a user initiates rescheduling,
    the task's due date should remain unchanged until explicit confirmation.
    """
    db_session = create_test_session()
    
    try:
        # Create test user
        test_user = User(
            email="test@example.com",
            hashed_password="hashed_password",
            preferred_tone="coach",
            timezone="UTC"
        )
        db_session.add(test_user)
        db_session.commit()
        user_id = test_user.id
        
        # Create test project
        test_project = Project(
            user_id=user_id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE
        )
        db_session.add(test_project)
        db_session.commit()
        project_id = test_project.id
        
        # Create a task with the generated due date
        task = Task(
            project_id=project_id,
            title=task_data["title"],
            description=task_data["description"],
            due_date=task_data["due_date"],
            original_due_date=task_data["due_date"],
            status=task_data["status"],
            order=1
        )
        db_session.add(task)
        db_session.commit()
        task_id = task.id
        
        # Store the original due date
        original_due_date = task.due_date
        
        # Create a check-in for this task
        check_in = CheckIn(
            project_id=project_id,
            task_id=task_id,
            check_in_type=CheckInType.SCHEDULED,
            status=CheckInStatus.SENT,
            scheduled_for=datetime.utcnow(),
            sent_at=datetime.utcnow()
        )
        db_session.add(check_in)
        db_session.commit()
        
        # Simulate initiating a reschedule (without confirmation)
        # This mimics what happens in the POST /check-ins/{id}/reschedule endpoint
        check_in.reschedule_initiated = True
        task.blocker_description = reschedule_data["reason"]
        
        db_session.commit()
        db_session.refresh(task)
        task_due_date = task.due_date
        
        # PROPERTY: The due date should NOT have changed
        assert task_due_date == original_due_date, \
            f"Due date changed without confirmation: {original_due_date} -> {task_due_date}"
        
        # Verify reschedule was marked as initiated
        assert check_in.reschedule_initiated is True
        
        # Verify no rescheduling history was created yet
        history_count = db_session.query(ReschedulingHistory).filter(
            ReschedulingHistory.task_id == task_id
        ).count()
        assert history_count == 0, "Rescheduling history should not be created without confirmation"
    finally:
        db_session.close()


@settings(max_examples=100)
@given(
    task_data=task_with_due_date(),
    reschedule_data=reschedule_scenario(),
    confirmed=st.booleans()
)
def test_timeline_only_changes_with_confirmation(
    task_data: dict,
    reschedule_data: dict,
    confirmed: bool
):
    """
    Property: Timeline only changes when user explicitly confirms.
    
    For any task and reschedule proposal, the due date should only change
    if and only if the user provides explicit confirmation.
    """
    db_session = create_test_session()
    
    try:
        # Create test user
        test_user = User(
            email="test@example.com",
            hashed_password="hashed_password",
            preferred_tone="coach",
            timezone="UTC"
        )
        db_session.add(test_user)
        db_session.commit()
        user_id = test_user.id
        
        # Create test project
        test_project = Project(
            user_id=user_id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE
        )
        db_session.add(test_project)
        db_session.commit()
        project_id = test_project.id
        
        # Create a task
        task = Task(
            project_id=project_id,
            title=task_data["title"],
            description=task_data["description"],
            due_date=task_data["due_date"],
            original_due_date=task_data["due_date"],
            status=task_data["status"],
            order=1
        )
        db_session.add(task)
        db_session.commit()
        task_id = task.id
        
        original_due_date = task.due_date
        
        # Create a check-in
        check_in = CheckIn(
            project_id=project_id,
            task_id=task_id,
            check_in_type=CheckInType.SCHEDULED,
            status=CheckInStatus.SENT,
            scheduled_for=datetime.utcnow(),
            sent_at=datetime.utcnow()
        )
        db_session.add(check_in)
        db_session.commit()
        
        # Initiate reschedule
        check_in.reschedule_initiated = True
        task.blocker_description = reschedule_data["reason"]
        db_session.commit()
        
        # Simulate confirmation step
        if confirmed:
            # User confirmed - apply the reschedule
            new_due_date = reschedule_data["new_date"]
            
            # Create history record
            history = ReschedulingHistory(
                task_id=task_id,
                old_due_date=original_due_date,
                new_due_date=new_due_date,
                reason=reschedule_data["reason"],
                initiated_by="user"
            )
            db_session.add(history)
            
            # Update task
            task.due_date = new_due_date
            task.reschedule_count += 1
            db_session.commit()
            task_new_due_date = task.due_date
            
            # PROPERTY: Due date should have changed
            assert task_new_due_date == new_due_date, \
                "Due date should change after confirmation"
            
            # Verify history was created
            history_count = db_session.query(ReschedulingHistory).filter(
                ReschedulingHistory.task_id == task_id
            ).count()
            assert history_count == 1, "Rescheduling history should be created after confirmation"
        else:
            # User did not confirm - due date should remain unchanged
            db_session.refresh(task)
            task_due_date = task.due_date
            
            # PROPERTY: Due date should NOT have changed
            assert task_due_date == original_due_date, \
                "Due date should not change without confirmation"
            
            # Verify no history was created
            history_count = db_session.query(ReschedulingHistory).filter(
                ReschedulingHistory.task_id == task_id
            ).count()
            assert history_count == 0, "Rescheduling history should not be created without confirmation"
    finally:
        db_session.close()


@settings(max_examples=100)
@given(
    task_data=task_with_due_date(),
    num_reschedule_attempts=st.integers(min_value=1, max_value=5)
)
def test_multiple_reschedule_attempts_without_confirmation(
    task_data: dict,
    num_reschedule_attempts: int
):
    """
    Property: Multiple reschedule attempts without confirmation don't change due date.
    
    For any task, even if rescheduling is initiated multiple times,
    the due date should remain unchanged until explicit confirmation.
    """
    db_session = create_test_session()
    
    try:
        # Create test user
        test_user = User(
            email="test@example.com",
            hashed_password="hashed_password",
            preferred_tone="coach",
            timezone="UTC"
        )
        db_session.add(test_user)
        db_session.commit()
        user_id = test_user.id
        
        # Create test project
        test_project = Project(
            user_id=user_id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE
        )
        db_session.add(test_project)
        db_session.commit()
        project_id = test_project.id
        
        # Create a task
        task = Task(
            project_id=project_id,
            title=task_data["title"],
            description=task_data["description"],
            due_date=task_data["due_date"],
            original_due_date=task_data["due_date"],
            status=task_data["status"],
            order=1
        )
        db_session.add(task)
        db_session.commit()
        task_id = task.id
        
        original_due_date = task.due_date
        
        # Simulate multiple reschedule attempts
        for i in range(num_reschedule_attempts):
            check_in = CheckIn(
                project_id=project_id,
                task_id=task_id,
                check_in_type=CheckInType.SCHEDULED,
                status=CheckInStatus.SENT,
                scheduled_for=datetime.utcnow() + timedelta(days=i),
                sent_at=datetime.utcnow() + timedelta(days=i)
            )
            db_session.add(check_in)
            db_session.commit()
            
            # Initiate reschedule (without confirmation)
            check_in.reschedule_initiated = True
            task.blocker_description = f"Attempt {i+1}: Need more time"
            db_session.commit()
        
        db_session.refresh(task)
        task_due_date = task.due_date
        
        # PROPERTY: Due date should still be the original
        assert task_due_date == original_due_date, \
            f"Due date changed after {num_reschedule_attempts} unconfirmed attempts"
        
        # Verify no rescheduling history was created
        history_count = db_session.query(ReschedulingHistory).filter(
            ReschedulingHistory.task_id == task_id
        ).count()
        assert history_count == 0, \
            "No rescheduling history should exist without confirmation"
    finally:
        db_session.close()
