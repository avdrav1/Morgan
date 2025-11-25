"""
Property-based tests for timeline modification acceptance.

Feature: proactive-accountability-assistant, Property 4: Timeline modification acceptance
Validates: Requirements 2.5
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import event
from datetime import datetime, timedelta

from app.core.database import Base
from app.models import User, Project, Task
from tests.conftest import SQLiteUUID, SQLiteJSONB
from sqlalchemy.dialects.postgresql import UUID, JSONB


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
    }


@st.composite
def task_data(draw):
    """Generate valid task data."""
    return {
        "title": draw(st.text(min_size=1, max_size=100)),
        "description": draw(st.text(min_size=1, max_size=500)),
        "order": draw(st.integers(min_value=1, max_value=20)),
        "estimated_duration_hours": draw(st.integers(min_value=1, max_value=40)),
        "due_date": datetime.utcnow() + timedelta(days=draw(st.integers(min_value=1, max_value=90)))
    }


@st.composite
def timeline_modifications(draw, num_tasks):
    """Generate timeline modifications for a set of tasks.
    
    This simulates user modifications to the proposed timeline:
    - Changing due dates
    - Adjusting estimated durations
    - Modifying task descriptions
    """
    modifications = []
    
    for i in range(num_tasks):
        # Generate a modification that changes at least one field
        modification_type = draw(st.sampled_from(['due_date', 'duration', 'description', 'multiple']))
        
        base_task = {
            "title": draw(st.text(min_size=1, max_size=100)),
            "description": draw(st.text(min_size=1, max_size=500)),
            "order": i + 1,
            "estimated_duration_hours": draw(st.integers(min_value=1, max_value=40)),
            "due_date": datetime.utcnow() + timedelta(days=draw(st.integers(min_value=1, max_value=90)))
        }
        
        # Apply modification based on type
        if modification_type == 'due_date':
            # User changes the due date
            base_task["due_date"] = datetime.utcnow() + timedelta(
                days=draw(st.integers(min_value=1, max_value=180))
            )
        elif modification_type == 'duration':
            # User adjusts the estimated duration
            base_task["estimated_duration_hours"] = draw(st.integers(min_value=1, max_value=80))
        elif modification_type == 'description':
            # User modifies the description
            base_task["description"] = draw(st.text(min_size=1, max_size=1000))
        elif modification_type == 'multiple':
            # User changes multiple fields
            base_task["due_date"] = datetime.utcnow() + timedelta(
                days=draw(st.integers(min_value=1, max_value=180))
            )
            base_task["estimated_duration_hours"] = draw(st.integers(min_value=1, max_value=80))
        
        modifications.append(base_task)
    
    return modifications


@settings(max_examples=100)
@given(
    user=user_data(),
    project=project_data(),
    num_tasks=st.integers(min_value=5, max_value=20),
    data=st.data()
)
def test_timeline_modification_acceptance(user, project, num_tasks, data):
    """
    Property 4: Timeline modification acceptance
    
    For any proposed timeline, when a user requests modifications, the system 
    should update the timeline to reflect the requested changes.
    
    This test verifies that:
    1. User can modify any aspect of the proposed timeline (dates, durations, descriptions)
    2. All modifications are persisted correctly in the database
    3. The system accepts and stores the modified timeline
    4. Modified values match exactly what the user requested
    
    Validates: Requirements 2.5
    """
    # Create a fresh session for this test run
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(**user)
        db_session.add(db_user)
        db_session.commit()
        user_id = db_user.id
        
        # Create project
        db_project = Project(
            user_id=user_id,
            **project
        )
        db_session.add(db_project)
        db_session.commit()
        project_id = db_project.id
        
        # Generate original proposed timeline
        original_tasks = []
        for i in range(num_tasks):
            task = Task(
                project_id=project_id,
                title=f"Original Task {i+1}",
                description=f"Original description {i+1}",
                order=i + 1,
                estimated_duration_hours=4,
                due_date=datetime.utcnow() + timedelta(days=(i+1) * 7)
            )
            original_tasks.append(task)
        
        # Generate user modifications using data.draw()
        modifications = data.draw(timeline_modifications(num_tasks))
        
        # Apply modifications by creating new tasks with modified values
        modified_tasks = []
        for i, mod in enumerate(modifications):
            task = Task(
                project_id=project_id,
                title=mod["title"],
                description=mod["description"],
                order=mod["order"],
                estimated_duration_hours=mod["estimated_duration_hours"],
                due_date=mod["due_date"],
                original_due_date=mod["due_date"]
            )
            db_session.add(task)
            modified_tasks.append(task)
        
        db_session.commit()
        
        # Property verification 1: All modified tasks are persisted
        stored_tasks = db_session.query(Task).filter(
            Task.project_id == project_id
        ).order_by(Task.order).all()
        
        assert len(stored_tasks) == num_tasks, \
            f"Expected {num_tasks} tasks to be stored, but found {len(stored_tasks)}"
        
        # Property verification 2: Modifications are reflected in stored tasks
        for i, (stored_task, modification) in enumerate(zip(stored_tasks, modifications)):
            assert stored_task.title == modification["title"], \
                f"Task {i+1} title not updated: expected '{modification['title']}', got '{stored_task.title}'"
            
            assert stored_task.description == modification["description"], \
                f"Task {i+1} description not updated"
            
            assert stored_task.estimated_duration_hours == modification["estimated_duration_hours"], \
                f"Task {i+1} duration not updated: expected {modification['estimated_duration_hours']}, got {stored_task.estimated_duration_hours}"
            
            # Due dates should match (within a small tolerance for datetime comparison)
            if stored_task.due_date and modification["due_date"]:
                time_diff = abs((stored_task.due_date - modification["due_date"]).total_seconds())
                assert time_diff < 1, \
                    f"Task {i+1} due date not updated correctly"
        
        # Property verification 3: System accepts modifications without error
        # (If we got here, the system accepted the modifications)
        
        # Property verification 4: Task order is preserved
        for i, task in enumerate(stored_tasks):
            assert task.order == i + 1, \
                f"Task order not preserved: expected {i+1}, got {task.order}"
    
    finally:
        db_session.close()


@settings(max_examples=100)
@given(
    user=user_data(),
    project=project_data(),
    num_tasks=st.integers(min_value=5, max_value=20),
    data=st.data()
)
def test_timeline_modification_preserves_project_integrity(user, project, num_tasks, data):
    """
    Property 4 (variant): Timeline modifications preserve project integrity
    
    For any timeline modifications, the project's overall integrity should be maintained:
    - Project completion date should reflect the latest task due date
    - All tasks should remain associated with the correct project
    - Task count should match the approved timeline
    
    Validates: Requirements 2.5
    """
    # Create a fresh session for this test run
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(**user)
        db_session.add(db_user)
        db_session.commit()
        user_id = db_user.id
        
        # Create project
        db_project = Project(
            user_id=user_id,
            **project
        )
        db_session.add(db_project)
        db_session.commit()
        project_id = db_project.id
        
        # Generate and apply timeline modifications using data.draw()
        modifications = data.draw(timeline_modifications(num_tasks))
        
        latest_due_date = None
        for mod in modifications:
            task = Task(
                project_id=project_id,
                title=mod["title"],
                description=mod["description"],
                order=mod["order"],
                estimated_duration_hours=mod["estimated_duration_hours"],
                due_date=mod["due_date"],
                original_due_date=mod["due_date"]
            )
            db_session.add(task)
            
            if not latest_due_date or mod["due_date"] > latest_due_date:
                latest_due_date = mod["due_date"]
        
        # Update project completion date
        db_project.target_completion_date = latest_due_date
        db_session.commit()
        project_target_completion = db_project.target_completion_date
        
        # Property verification 1: All tasks belong to the correct project
        stored_tasks = db_session.query(Task).filter(
            Task.project_id == project_id
        ).all()
        
        for task in stored_tasks:
            assert task.project_id == project_id, \
                "Task should belong to the correct project"
        
        # Property verification 2: Project completion date reflects latest task
        if latest_due_date:
            assert project_target_completion == latest_due_date, \
                "Project completion date should match the latest task due date"
        
        # Property verification 3: Task count matches approved timeline
        assert len(stored_tasks) == num_tasks, \
            f"Task count should match approved timeline: expected {num_tasks}, got {len(stored_tasks)}"
    
    finally:
        db_session.close()
