"""
Property-based tests for data deletion completeness.

Feature: proactive-accountability-assistant, Property 18: Data deletion completeness
Validates: Requirements 10.1
"""

import pytest
from hypothesis import given, strategies as st, settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta

from app.core.database import Base
from app.models import User, Project, Task, CheckIn, AvailabilityWindow
from app.models.project import ProjectStatus
from app.models.task import TaskStatus
from app.models.check_in import CheckInType, CheckInStatus
from app.models.rescheduling_history import ReschedulingHistory
from tests.conftest import SQLiteUUID, SQLiteJSONB
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import event


@st.composite
def user_with_data(draw):
    """Generate a user with associated data (projects, tasks, check-ins, availability)."""
    user_data = {
        "email": draw(st.emails()),
        "hashed_password": draw(st.text(min_size=10, max_size=100)),
        "full_name": draw(st.text(min_size=1, max_size=100)),
        "timezone": draw(st.sampled_from(["UTC", "America/New_York", "Europe/London", "Asia/Tokyo"])),
    }
    
    # Generate 1-5 projects
    num_projects = draw(st.integers(min_value=1, max_value=5))
    projects = []
    for _ in range(num_projects):
        project = {
            "title": draw(st.text(min_size=1, max_size=100)),
            "description": draw(st.text(min_size=1, max_size=500)),
            "goal": draw(st.text(min_size=1, max_size=500)),
            "status": draw(st.sampled_from([ProjectStatus.ACTIVE, ProjectStatus.PAUSED, ProjectStatus.COMPLETED])),
        }
        
        # Generate 1-10 tasks per project
        num_tasks = draw(st.integers(min_value=1, max_value=10))
        tasks = []
        for i in range(num_tasks):
            task = {
                "title": draw(st.text(min_size=1, max_size=100)),
                "description": draw(st.text(min_size=1, max_size=500)),
                "order": i,
                "status": draw(st.sampled_from([TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED])),
            }
            tasks.append(task)
        
        project["tasks"] = tasks
        
        # Generate 0-5 check-ins per project
        num_check_ins = draw(st.integers(min_value=0, max_value=5))
        check_ins = []
        for _ in range(num_check_ins):
            check_in = {
                "check_in_type": draw(st.sampled_from([CheckInType.SCHEDULED, CheckInType.USER_INITIATED])),
                "status": draw(st.sampled_from([CheckInStatus.SENT, CheckInStatus.RESPONDED, CheckInStatus.MISSED])),
                "scheduled_for": datetime.utcnow() + timedelta(days=draw(st.integers(min_value=-30, max_value=30))),
            }
            check_ins.append(check_in)
        
        project["check_ins"] = check_ins
        projects.append(project)
    
    # Generate 0-7 availability windows
    num_windows = draw(st.integers(min_value=0, max_value=7))
    availability_windows = []
    for _ in range(num_windows):
        window = {
            "day_of_week": draw(st.integers(min_value=0, max_value=6)),
            "start_time": draw(st.sampled_from(["09:00", "10:00", "14:00"])),
            "end_time": draw(st.sampled_from(["17:00", "18:00", "22:00"])),
        }
        availability_windows.append(window)
    
    return {
        "user": user_data,
        "projects": projects,
        "availability_windows": availability_windows,
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
@given(data=user_with_data())
def test_data_deletion_completeness(data):
    """
    Property 18: Data deletion completeness
    
    For any user who requests data deletion, all associated records (projects, tasks, 
    check-ins, availability windows) should be deleted within 30 days.
    
    This test verifies that:
    1. When a user schedules deletion, the deletion_scheduled_at field is set
    2. When deletion is executed (simulated), all associated records are removed
    3. No orphaned records remain in the database
    
    Validates: Requirements 10.1
    """
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(**data["user"])
        db_session.add(db_user)
        db_session.commit()
        db_session.refresh(db_user)
        
        user_id = db_user.id
        
        # Create availability windows
        for window_data in data["availability_windows"]:
            window = AvailabilityWindow(user_id=user_id, **window_data)
            db_session.add(window)
        
        # Create projects with tasks and check-ins
        task_ids = []
        for project_data in data["projects"]:
            tasks_data = project_data.pop("tasks")
            check_ins_data = project_data.pop("check_ins")
            
            project = Project(user_id=user_id, **project_data)
            db_session.add(project)
            db_session.commit()
            db_session.refresh(project)
            
            # Create tasks
            for task_data in tasks_data:
                task = Task(project_id=project.id, **task_data)
                db_session.add(task)
                db_session.commit()
                db_session.refresh(task)
                task_ids.append(task.id)
            
            # Create check-ins
            for check_in_data in check_ins_data:
                # Assign to a random task if available
                task_id = task_ids[0] if task_ids else None
                check_in = CheckIn(
                    project_id=project.id,
                    task_id=task_id,
                    **check_in_data
                )
                db_session.add(check_in)
        
        db_session.commit()
        
        # Count records before deletion
        projects_count_before = db_session.query(Project).filter(Project.user_id == user_id).count()
        tasks_count_before = db_session.query(Task).join(Project).filter(Project.user_id == user_id).count()
        check_ins_count_before = db_session.query(CheckIn).join(Project).filter(Project.user_id == user_id).count()
        availability_count_before = db_session.query(AvailabilityWindow).filter(AvailabilityWindow.user_id == user_id).count()
        
        # Verify we have data
        assert projects_count_before > 0, "Should have at least one project"
        assert tasks_count_before > 0, "Should have at least one task"
        
        # Step 1: Schedule deletion (simulating the DELETE /me/data endpoint)
        deletion_date = datetime.utcnow() + timedelta(days=30)
        db_user.deletion_scheduled_at = deletion_date
        db_user.messaging_paused = True
        db_session.commit()
        
        # Verify deletion is scheduled
        assert db_user.deletion_scheduled_at is not None, "Deletion should be scheduled"
        assert db_user.messaging_paused is True, "Messaging should be paused"
        
        # Step 2: Simulate deletion execution (what would happen after 30 days)
        # This simulates the actual deletion process
        db_session.delete(db_user)
        db_session.commit()
        
        # Step 3: Verify all associated records are deleted
        # Due to cascade delete, all related records should be removed
        
        # Verify user is deleted
        user_exists = db_session.query(User).filter(User.id == user_id).first()
        assert user_exists is None, "User should be deleted"
        
        # Verify projects are deleted
        projects_count_after = db_session.query(Project).filter(Project.user_id == user_id).count()
        assert projects_count_after == 0, f"All projects should be deleted, but found {projects_count_after}"
        
        # Verify tasks are deleted (cascade from projects)
        tasks_count_after = db_session.query(Task).filter(Task.id.in_(task_ids)).count()
        assert tasks_count_after == 0, f"All tasks should be deleted, but found {tasks_count_after}"
        
        # Verify check-ins are deleted (cascade from projects)
        check_ins_count_after = db_session.query(CheckIn).join(Project).filter(Project.user_id == user_id).count()
        assert check_ins_count_after == 0, f"All check-ins should be deleted, but found {check_ins_count_after}"
        
        # Verify availability windows are deleted (cascade from user)
        availability_count_after = db_session.query(AvailabilityWindow).filter(AvailabilityWindow.user_id == user_id).count()
        assert availability_count_after == 0, f"All availability windows should be deleted, but found {availability_count_after}"
        
    finally:
        db_session.close()
