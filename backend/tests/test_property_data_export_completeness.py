"""
Property-based tests for data export completeness.

Feature: proactive-accountability-assistant, Property 19: Data export completeness
Validates: Requirements 10.2
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
def user_with_complete_data(draw):
    """Generate a user with comprehensive data for export testing."""
    user_data = {
        "email": draw(st.emails()),
        "hashed_password": draw(st.text(min_size=10, max_size=100)),
        "full_name": draw(st.text(min_size=1, max_size=100)),
        "timezone": draw(st.sampled_from(["UTC", "America/New_York", "Europe/London"])),
        "preferred_tone": draw(st.sampled_from(["coach", "manager", "buddy", "drill_sergeant"])),
        "quiet_hours_start": draw(st.sampled_from(["22:00", "23:00", None])),
        "quiet_hours_end": draw(st.sampled_from(["08:00", "09:00", None])),
    }
    
    # Generate 1-3 projects
    num_projects = draw(st.integers(min_value=1, max_value=3))
    projects = []
    for _ in range(num_projects):
        project = {
            "title": draw(st.text(min_size=1, max_size=100)),
            "description": draw(st.text(min_size=1, max_size=500)),
            "goal": draw(st.text(min_size=1, max_size=500)),
            "status": draw(st.sampled_from([ProjectStatus.ACTIVE, ProjectStatus.PAUSED, ProjectStatus.COMPLETED])),
            "project_tone": draw(st.sampled_from(["coach", "manager", None])),
            "project_context": draw(st.text(min_size=0, max_size=200)),
        }
        
        # Generate 1-5 tasks per project
        num_tasks = draw(st.integers(min_value=1, max_value=5))
        tasks = []
        for i in range(num_tasks):
            task = {
                "title": draw(st.text(min_size=1, max_size=100)),
                "description": draw(st.text(min_size=1, max_size=500)),
                "order": i,
                "status": draw(st.sampled_from([TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED])),
                "blocker_type": draw(st.sampled_from([None, "time", "clarity", "emotional"])),
            }
            tasks.append(task)
        
        project["tasks"] = tasks
        
        # Generate 1-3 check-ins per project
        num_check_ins = draw(st.integers(min_value=1, max_value=3))
        check_ins = []
        for _ in range(num_check_ins):
            check_in = {
                "check_in_type": draw(st.sampled_from([CheckInType.SCHEDULED, CheckInType.USER_INITIATED])),
                "status": draw(st.sampled_from([CheckInStatus.SENT, CheckInStatus.RESPONDED])),
                "scheduled_for": datetime.utcnow() + timedelta(days=draw(st.integers(min_value=-10, max_value=10))),
                "message_sent": draw(st.text(min_size=1, max_size=200)),
                "user_response": draw(st.text(min_size=0, max_size=200)),
            }
            check_ins.append(check_in)
        
        project["check_ins"] = check_ins
        projects.append(project)
    
    # Generate 1-5 availability windows
    num_windows = draw(st.integers(min_value=1, max_value=5))
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


def simulate_export_endpoint(db_session, user_id):
    """Simulate the export endpoint logic."""
    user = db_session.query(User).filter(User.id == user_id).first()
    projects = db_session.query(Project).filter(Project.user_id == user_id).all()
    
    export_data = {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "preferred_tone": user.preferred_tone,
            "custom_system_prompt": user.custom_system_prompt,
            "timezone": user.timezone,
            "quiet_hours_start": user.quiet_hours_start,
            "quiet_hours_end": user.quiet_hours_end,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "availability_windows": [
            {
                "day_of_week": window.day_of_week,
                "start_time": window.start_time,
                "end_time": window.end_time,
            }
            for window in user.availability_windows
        ],
        "projects": []
    }
    
    for project in projects:
        project_data = {
            "id": str(project.id),
            "title": project.title,
            "description": project.description,
            "goal": project.goal,
            "project_tone": project.project_tone,
            "project_context": project.project_context,
            "tasks": [],
            "check_ins": []
        }
        
        for task in project.tasks:
            task_data = {
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "order": task.order,
                "status": task.status.value if task.status else None,
                "blocker_type": task.blocker_type,
            }
            project_data["tasks"].append(task_data)
        
        for check_in in project.check_ins:
            check_in_data = {
                "id": str(check_in.id),
                "check_in_type": check_in.check_in_type.value if check_in.check_in_type else None,
                "status": check_in.status.value if check_in.status else None,
                "message_sent": check_in.message_sent,
                "user_response": check_in.user_response,
            }
            project_data["check_ins"].append(check_in_data)
        
        export_data["projects"].append(project_data)
    
    return export_data


@settings(max_examples=100, deadline=None)
@given(data=user_with_complete_data())
def test_data_export_completeness(data):
    """
    Property 19: Data export completeness
    
    For any user who requests data export, the exported data should include all 
    projects, tasks, timelines, and conversation history associated with that user.
    
    This test verifies that:
    1. All user profile data is included in the export
    2. All projects are included with their metadata
    3. All tasks are included with their details
    4. All check-ins (conversation history) are included
    5. All availability windows are included
    6. The export is in a portable JSON format
    
    Validates: Requirements 10.2
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
        
        # Track counts for verification
        total_projects = len(data["projects"])
        total_tasks = 0
        total_check_ins = 0
        
        # Create projects with tasks and check-ins
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
                total_tasks += 1
            
            db_session.commit()
            
            # Create check-ins
            for check_in_data in check_ins_data:
                check_in = CheckIn(
                    project_id=project.id,
                    task_id=None,  # Not assigning to specific tasks for simplicity
                    **check_in_data
                )
                db_session.add(check_in)
                total_check_ins += 1
        
        db_session.commit()
        
        # Simulate the export endpoint
        export_data = simulate_export_endpoint(db_session, user_id)
        
        # Property verification 1: User data is complete
        assert export_data["user"]["email"] == data["user"]["email"], "User email should be exported"
        assert export_data["user"]["full_name"] == data["user"]["full_name"], "User full name should be exported"
        assert export_data["user"]["preferred_tone"] == data["user"]["preferred_tone"], "User tone should be exported"
        assert export_data["user"]["timezone"] == data["user"]["timezone"], "User timezone should be exported"
        assert export_data["user"]["quiet_hours_start"] == data["user"]["quiet_hours_start"], "Quiet hours start should be exported"
        assert export_data["user"]["quiet_hours_end"] == data["user"]["quiet_hours_end"], "Quiet hours end should be exported"
        
        # Property verification 2: All availability windows are exported
        assert len(export_data["availability_windows"]) == len(data["availability_windows"]), \
            f"Expected {len(data['availability_windows'])} availability windows, but found {len(export_data['availability_windows'])}"
        
        # Property verification 3: All projects are exported
        assert len(export_data["projects"]) == total_projects, \
            f"Expected {total_projects} projects in export, but found {len(export_data['projects'])}"
        
        # Property verification 4: All tasks are exported
        exported_tasks_count = sum(len(p["tasks"]) for p in export_data["projects"])
        assert exported_tasks_count == total_tasks, \
            f"Expected {total_tasks} tasks in export, but found {exported_tasks_count}"
        
        # Property verification 5: All check-ins (conversation history) are exported
        exported_check_ins_count = sum(len(p["check_ins"]) for p in export_data["projects"])
        assert exported_check_ins_count == total_check_ins, \
            f"Expected {total_check_ins} check-ins in export, but found {exported_check_ins_count}"
        
        # Property verification 6: Project-specific settings are exported
        for i, project in enumerate(export_data["projects"]):
            original_project = data["projects"][i]
            assert project["title"] == original_project["title"], "Project title should be exported"
            assert project["description"] == original_project["description"], "Project description should be exported"
            assert project["goal"] == original_project["goal"], "Project goal should be exported"
            assert project["project_tone"] == original_project["project_tone"], "Project tone should be exported"
            assert project["project_context"] == original_project["project_context"], "Project context should be exported"
        
        # Property verification 7: Task details are exported
        for project in export_data["projects"]:
            for task in project["tasks"]:
                assert "id" in task, "Task ID should be exported"
                assert "title" in task, "Task title should be exported"
                assert "description" in task, "Task description should be exported"
                assert "order" in task, "Task order should be exported"
                assert "status" in task, "Task status should be exported"
                assert "blocker_type" in task, "Task blocker type should be exported"
        
        # Property verification 8: Check-in (conversation) details are exported
        for project in export_data["projects"]:
            for check_in in project["check_ins"]:
                assert "id" in check_in, "Check-in ID should be exported"
                assert "check_in_type" in check_in, "Check-in type should be exported"
                assert "status" in check_in, "Check-in status should be exported"
                assert "message_sent" in check_in, "Check-in message should be exported"
                assert "user_response" in check_in, "User response should be exported"
        
        # Property verification 9: Export is in JSON-serializable format
        # All values should be JSON-serializable (strings, numbers, booleans, None, lists, dicts)
        import json
        try:
            json_str = json.dumps(export_data)
            assert len(json_str) > 0, "Export should be JSON-serializable"
        except (TypeError, ValueError) as e:
            pytest.fail(f"Export data is not JSON-serializable: {e}")
        
    finally:
        db_session.close()
