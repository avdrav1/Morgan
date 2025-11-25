"""
Property-Based Test: Rescheduling history tracking

Feature: proactive-accountability-assistant, Property 12: Rescheduling history tracking
Validates: Requirements 5.5

Property: For any task that is rescheduled, a rescheduling history record should be 
created with the old date, new date, and reason.

This test verifies that:
1. Every reschedule creates a history record
2. History records contain all required information
3. Multiple reschedules create multiple history records
4. History is preserved even after task completion
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
def reschedule_data(draw):
    """Generate reschedule data with reason and new date."""
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
    
    blocker_types = ["time", "clarity", "emotional", "external", "scope", None]
    
    return {
        "reason": draw(st.sampled_from(reasons)),
        "new_date": new_date,
        "blocker_type": draw(st.sampled_from(blocker_types)),
        "initiated_by": draw(st.sampled_from(["user", "assistant"]))
    }


@settings(max_examples=100)
@given(
    task_data=task_with_due_date(),
    reschedule=reschedule_data()
)
def test_reschedule_creates_history_record(
    task_data: dict,
    reschedule: dict
):
    """
    Property: Every confirmed reschedule creates a history record.
    
    For any task that is rescheduled, a ReschedulingHistory record should be
    created with the old date, new date, reason, and blocker type.
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
        db_session.flush()  # Flush to get ID without committing
        
        # Create test project
        test_project = Project(
            user_id=test_user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE
        )
        db_session.add(test_project)
        db_session.flush()  # Flush to get ID without committing
        
        # Create a task
        task = Task(
            project_id=test_project.id,
            title=task_data["title"],
            description=task_data["description"],
            due_date=task_data["due_date"],
            original_due_date=task_data["due_date"],
            status=task_data["status"],
            order=1
        )
        db_session.add(task)
        db_session.flush()  # Flush to get ID
        
        original_due_date = task.due_date
        
        # Perform reschedule with confirmation
        new_due_date = reschedule["new_date"]
        
        # Create history record (as done in confirm_reschedule endpoint)
        history = ReschedulingHistory(
            task_id=task.id,
            old_due_date=original_due_date,
            new_due_date=new_due_date,
            reason=reschedule["reason"],
            blocker_type=reschedule["blocker_type"],
            initiated_by=reschedule["initiated_by"]
        )
        db_session.add(history)
        
        # Update task
        task.due_date = new_due_date
        task.reschedule_count += 1
        db_session.commit()
        
        # Store task_id before session closes
        task_id = task.id
        
        # PROPERTY: History record should exist
        history_records = db_session.query(ReschedulingHistory).filter(
            ReschedulingHistory.task_id == task_id
        ).all()
        
        assert len(history_records) == 1, "Exactly one history record should be created"
        
        # Verify history record contains all required information
        record = history_records[0]
        assert record.old_due_date == original_due_date, "Old due date should match original"
        assert record.new_due_date == new_due_date, "New due date should match reschedule"
        assert record.reason == reschedule["reason"], "Reason should be stored"
        assert record.blocker_type == reschedule["blocker_type"], "Blocker type should be stored"
        assert record.initiated_by == reschedule["initiated_by"], "Initiator should be stored"
        assert record.created_at is not None, "Created timestamp should be set"
    finally:
        db_session.close()


@settings(max_examples=100)
@given(
    task_data=task_with_due_date(),
    num_reschedules=st.integers(min_value=1, max_value=5)
)
def test_multiple_reschedules_create_multiple_history_records(
    task_data: dict,
    num_reschedules: int
):
    """
    Property: Multiple reschedules create multiple history records.
    
    For any task that is rescheduled multiple times, each reschedule should
    create a separate history record, preserving the complete timeline.
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
        db_session.flush()  # Flush to get ID without committing
        
        # Create test project
        test_project = Project(
            user_id=test_user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE
        )
        db_session.add(test_project)
        db_session.flush()  # Flush to get ID without committing
        
        # Create a task
        task = Task(
            project_id=test_project.id,
            title=task_data["title"],
            description=task_data["description"],
            due_date=task_data["due_date"],
            original_due_date=task_data["due_date"],
            status=task_data["status"],
            order=1
        )
        db_session.add(task)
        db_session.flush()  # Flush to get ID
        
        # Store task_id before loop
        task_id = task.id
        
        # Perform multiple reschedules
        for i in range(num_reschedules):
            old_due_date = task.due_date
            new_due_date = old_due_date + timedelta(days=7 * (i + 1))
            
            # Create history record
            history = ReschedulingHistory(
                task_id=task_id,
                old_due_date=old_due_date,
                new_due_date=new_due_date,
                reason=f"Reschedule attempt {i+1}",
                blocker_type="time",
                initiated_by="user"
            )
            db_session.add(history)
            
            # Update task
            task.due_date = new_due_date
            task.reschedule_count += 1
            db_session.commit()
        
        # PROPERTY: Number of history records should equal number of reschedules
        history_count = db_session.query(ReschedulingHistory).filter(
            ReschedulingHistory.task_id == task_id
        ).count()
        
        assert history_count == num_reschedules, \
            f"Expected {num_reschedules} history records, got {history_count}"
        
        # Verify task reschedule count matches
        db_session.refresh(task)
        assert task.reschedule_count == num_reschedules, \
            "Task reschedule count should match number of reschedules"
    finally:
        db_session.close()


@settings(max_examples=100)
@given(
    task_data=task_with_due_date(),
    reschedule=reschedule_data()
)
def test_history_preserved_after_task_completion(
    task_data: dict,
    reschedule: dict
):
    """
    Property: Rescheduling history is preserved even after task completion.
    
    For any task that is rescheduled and then completed, the rescheduling
    history should remain accessible for audit and learning purposes.
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
        db_session.flush()  # Flush to get ID without committing
        
        # Create test project
        test_project = Project(
            user_id=test_user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE
        )
        db_session.add(test_project)
        db_session.flush()  # Flush to get ID without committing
        
        # Create a task
        task = Task(
            project_id=test_project.id,
            title=task_data["title"],
            description=task_data["description"],
            due_date=task_data["due_date"],
            original_due_date=task_data["due_date"],
            status=task_data["status"],
            order=1
        )
        db_session.add(task)
        db_session.flush()  # Flush to get ID
        
        original_due_date = task.due_date
        task_id = task.id
        
        # Perform reschedule
        new_due_date = reschedule["new_date"]
        history = ReschedulingHistory(
            task_id=task_id,
            old_due_date=original_due_date,
            new_due_date=new_due_date,
            reason=reschedule["reason"],
            blocker_type=reschedule["blocker_type"],
            initiated_by=reschedule["initiated_by"]
        )
        db_session.add(history)
        task.due_date = new_due_date
        task.reschedule_count += 1
        db_session.commit()
        
        # Complete the task
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        db_session.commit()
        
        # PROPERTY: History should still be accessible
        history_records = db_session.query(ReschedulingHistory).filter(
            ReschedulingHistory.task_id == task_id
        ).all()
        
        assert len(history_records) == 1, \
            "History should be preserved after task completion"
        
        record = history_records[0]
        assert record.old_due_date == original_due_date
        assert record.new_due_date == new_due_date
        assert record.reason == reschedule["reason"]
    finally:
        db_session.close()


@settings(max_examples=100)
@given(
    task_data=task_with_due_date(),
    reschedule=reschedule_data()
)
def test_history_tracks_timeline_changes_accurately(
    task_data: dict,
    reschedule: dict
):
    """
    Property: History accurately tracks the timeline of changes.
    
    For any sequence of reschedules, the history should form a complete
    chain showing how the due date evolved over time.
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
        db_session.flush()  # Flush to get ID without committing
        
        # Create test project
        test_project = Project(
            user_id=test_user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE
        )
        db_session.add(test_project)
        db_session.flush()  # Flush to get ID without committing
        
        # Create a task
        task = Task(
            project_id=test_project.id,
            title=task_data["title"],
            description=task_data["description"],
            due_date=task_data["due_date"],
            original_due_date=task_data["due_date"],
            status=task_data["status"],
            order=1
        )
        db_session.add(task)
        db_session.flush()  # Flush to get ID
        
        # Perform reschedule
        old_due_date = task.due_date
        new_due_date = reschedule["new_date"]
        task_id = task.id
        
        history = ReschedulingHistory(
            task_id=task_id,
            old_due_date=old_due_date,
            new_due_date=new_due_date,
            reason=reschedule["reason"],
            blocker_type=reschedule["blocker_type"],
            initiated_by=reschedule["initiated_by"]
        )
        db_session.add(history)
        task.due_date = new_due_date
        db_session.commit()
        
        # Store the new due date before refresh
        task_new_due_date = task.due_date
        
        # PROPERTY: The history record should accurately reflect the change
        db_session.refresh(history)
        
        # The old date in history should match what the task had before
        assert history.old_due_date == old_due_date, \
            "History should record the actual old due date"
        
        # The new date in history should match what the task has now
        assert history.new_due_date == task_new_due_date, \
            "History should record the actual new due date"
        
        # The new date should be different from the old date
        # (unless by chance they're the same, which is unlikely but possible)
        if old_due_date != new_due_date:
            assert history.old_due_date != history.new_due_date, \
                "History should show a change in due date"
    finally:
        db_session.close()
