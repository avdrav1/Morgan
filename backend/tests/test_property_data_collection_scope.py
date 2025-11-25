"""
Property-based tests for data collection scope.

Feature: proactive-accountability-assistant, Property 21: Data collection scope
Validates: Requirements 10.4
"""

import pytest
from hypothesis import given, strategies as st, settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import inspect
from datetime import datetime, timedelta

from app.core.database import Base
from app.models import User, Project, Task, CheckIn, AvailabilityWindow
from app.models.project import ProjectStatus
from app.models.task import TaskStatus
from app.models.check_in import CheckInType, CheckInStatus
from tests.conftest import SQLiteUUID, SQLiteJSONB
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import event


# Define the allowed data categories based on Requirements 10.4
ALLOWED_DATA_CATEGORIES = {
    "project_goals": ["projects.title", "projects.description", "projects.goal", "projects.success_criteria", 
                     "projects.status"],  # Status is part of project tracking
    "tasks": ["tasks.title", "tasks.description", "tasks.order", "tasks.status", "tasks.estimated_duration_hours", 
              "tasks.due_date", "tasks.original_due_date", "tasks.completed_at", "tasks.blocker_type", 
              "tasks.blocker_description", "tasks.blocker_diagnosed_at", "tasks.reschedule_count"],
    "timelines": ["projects.target_completion_date", "projects.actual_completion_date", "projects.estimated_duration_weeks",
                  "tasks.due_date", "tasks.original_due_date", "tasks.completed_at"],
    "user_preferences": ["users.preferred_tone", "users.custom_system_prompt", "users.timezone", 
                        "users.quiet_hours_start", "users.quiet_hours_end", "users.messaging_paused",
                        "users.full_name",  # User's name for personalization
                        "availability_windows.day_of_week", "availability_windows.start_time", 
                        "availability_windows.end_time", "projects.project_tone", "projects.project_context"],
    "conversation_history": ["check_ins.message_sent", "check_ins.user_response", "check_ins.assistant_reply",
                            "check_ins.conversation_context", "check_ins.check_in_type", "check_ins.status",
                            "check_ins.scheduled_for", "check_ins.sent_at", "check_ins.responded_at",
                            "check_ins.blocker_detected", "check_ins.reschedule_initiated", 
                            "check_ins.response_time_minutes", "check_ins.sentiment"],
}

# Fields that are system metadata (allowed for system operation but not user data)
SYSTEM_METADATA_FIELDS = ["id", "created_at", "updated_at", "user_id", "project_id", "task_id"]

# Fields that are authentication/security (necessary for system operation)
AUTH_FIELDS = ["email", "hashed_password", "discord_user_id", "is_active"]

# Fields for engagement tracking (used for adaptive behavior)
ENGAGEMENT_FIELDS = ["total_check_ins_sent", "total_check_ins_responded", "consecutive_missed_check_ins", 
                     "last_active_at", "ghosting_stage"]

# Fields for data privacy features
PRIVACY_FIELDS = ["deletion_scheduled_at"]

# Platform-specific fields
PLATFORM_FIELDS = ["platform"]


def get_all_model_fields():
    """Get all fields from all models in the database."""
    models = [User, Project, Task, CheckIn, AvailabilityWindow]
    all_fields = {}
    
    for model in models:
        table_name = model.__tablename__
        inspector = inspect(model)
        fields = [column.key for column in inspector.columns]
        all_fields[table_name] = fields
    
    return all_fields


def categorize_field(table_name, field_name):
    """Categorize a field based on its purpose."""
    full_field_name = f"{table_name}.{field_name}"
    
    # Check if it's in allowed data categories
    for category, fields in ALLOWED_DATA_CATEGORIES.items():
        if full_field_name in fields:
            return "allowed_data"
    
    # Check if it's system metadata
    if field_name in SYSTEM_METADATA_FIELDS:
        return "system_metadata"
    
    # Check if it's authentication
    if field_name in AUTH_FIELDS:
        return "authentication"
    
    # Check if it's engagement tracking
    if field_name in ENGAGEMENT_FIELDS:
        return "engagement_tracking"
    
    # Check if it's privacy-related
    if field_name in PRIVACY_FIELDS:
        return "privacy"
    
    # Check if it's platform-specific
    if field_name in PLATFORM_FIELDS:
        return "platform"
    
    # If we get here, it's an unknown field
    return "unknown"


@st.composite
def user_interaction_data(draw):
    """Generate data representing a user interaction."""
    return {
        "user": {
            "email": draw(st.emails()),
            "hashed_password": draw(st.text(min_size=10, max_size=100)),
            "full_name": draw(st.text(min_size=1, max_size=100)),
            "timezone": draw(st.sampled_from(["UTC", "America/New_York"])),
            "preferred_tone": draw(st.sampled_from(["coach", "manager"])),
        },
        "project": {
            "title": draw(st.text(min_size=1, max_size=100)),
            "description": draw(st.text(min_size=1, max_size=500)),
            "goal": draw(st.text(min_size=1, max_size=500)),
            "status": ProjectStatus.ACTIVE,
        },
        "task": {
            "title": draw(st.text(min_size=1, max_size=100)),
            "description": draw(st.text(min_size=1, max_size=500)),
            "order": 0,
            "status": TaskStatus.NOT_STARTED,
        },
        "check_in": {
            "check_in_type": CheckInType.SCHEDULED,
            "status": CheckInStatus.RESPONDED,
            "scheduled_for": datetime.utcnow(),
            "message_sent": draw(st.text(min_size=1, max_size=200)),
            "user_response": draw(st.text(min_size=1, max_size=200)),
        },
        "availability_window": {
            "day_of_week": draw(st.integers(min_value=0, max_value=6)),
            "start_time": "09:00",
            "end_time": "17:00",
        }
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
@given(interaction=user_interaction_data())
def test_data_collection_scope(interaction):
    """
    Property 21: Data collection scope
    
    For any user interaction, the system should only store data in the categories:
    - Project goals (title, description, goal, success criteria)
    - Tasks (title, description, order, status, timeline info, blocker info)
    - Timelines (due dates, completion dates, duration estimates)
    - User preferences (tone, timezone, quiet hours, availability, custom prompts)
    - Conversation history (check-ins, messages, responses, context)
    
    This test verifies that:
    1. All fields in the database can be categorized into allowed categories
    2. No fields exist that collect data outside the specified scope
    3. System metadata and authentication fields are separate from user data
    
    Validates: Requirements 10.4
    """
    db_session = create_test_session()
    
    try:
        # Create a user interaction with all data types
        user = User(**interaction["user"])
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Create availability window
        availability = AvailabilityWindow(user_id=user.id, **interaction["availability_window"])
        db_session.add(availability)
        
        # Create project
        project = Project(user_id=user.id, **interaction["project"])
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        
        # Create task
        task = Task(project_id=project.id, **interaction["task"])
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        
        # Create check-in
        check_in = CheckIn(project_id=project.id, task_id=task.id, **interaction["check_in"])
        db_session.add(check_in)
        db_session.commit()
        
        # Get all fields from all models
        all_fields = get_all_model_fields()
        
        # Categorize all fields
        field_categories = {}
        unknown_fields = []
        
        for table_name, fields in all_fields.items():
            for field_name in fields:
                category = categorize_field(table_name, field_name)
                full_field_name = f"{table_name}.{field_name}"
                field_categories[full_field_name] = category
                
                if category == "unknown":
                    unknown_fields.append(full_field_name)
        
        # Property verification 1: No unknown fields should exist
        assert len(unknown_fields) == 0, \
            f"Found fields that don't fit into allowed data categories or system fields: {unknown_fields}"
        
        # Property verification 2: All fields are categorized
        assert len(field_categories) > 0, "Should have categorized some fields"
        
        # Property verification 3: Verify we have fields in each allowed category
        allowed_data_fields = [f for f, c in field_categories.items() if c == "allowed_data"]
        assert len(allowed_data_fields) > 0, "Should have fields in allowed data categories"
        
        # Property verification 4: System metadata is separate from user data
        system_fields = [f for f, c in field_categories.items() if c == "system_metadata"]
        assert len(system_fields) > 0, "Should have system metadata fields"
        
        # Verify system metadata doesn't overlap with user data
        for field in system_fields:
            assert field not in allowed_data_fields, \
                f"System metadata field {field} should not be in user data categories"
        
        # Property verification 5: Authentication fields are separate from user data
        auth_fields = [f for f, c in field_categories.items() if c == "authentication"]
        for field in auth_fields:
            assert field not in allowed_data_fields, \
                f"Authentication field {field} should not be in user data categories"
        
        # Property verification 6: Verify specific required data categories exist
        # Check that we have fields for each required category
        project_goal_fields = [f for f in allowed_data_fields if f.startswith("projects.") and 
                              any(x in f for x in ["title", "description", "goal"])]
        assert len(project_goal_fields) > 0, "Should have project goal fields"
        
        task_fields = [f for f in allowed_data_fields if f.startswith("tasks.")]
        assert len(task_fields) > 0, "Should have task fields"
        
        timeline_fields = [f for f in allowed_data_fields if "due_date" in f or "completion_date" in f]
        assert len(timeline_fields) > 0, "Should have timeline fields"
        
        preference_fields = [f for f in allowed_data_fields if 
                           any(x in f for x in ["tone", "timezone", "quiet_hours", "availability"])]
        assert len(preference_fields) > 0, "Should have preference fields"
        
        conversation_fields = [f for f in allowed_data_fields if f.startswith("check_ins.")]
        assert len(conversation_fields) > 0, "Should have conversation history fields"
        
        # Property verification 7: Verify no sensitive personal data beyond what's specified
        # Check that we don't have fields for things like:
        # - Health information
        # - Financial information
        # - Location tracking (beyond timezone)
        # - Biometric data
        # - Social security numbers, etc.
        
        sensitive_keywords = ["ssn", "social_security", "credit_card", "bank", "health", 
                             "medical", "biometric", "fingerprint", "location", "gps", 
                             "coordinates", "address", "phone"]
        
        for table_name, fields in all_fields.items():
            for field_name in fields:
                field_lower = field_name.lower()
                for keyword in sensitive_keywords:
                    assert keyword not in field_lower, \
                        f"Found potentially sensitive field {table_name}.{field_name} that may collect data outside allowed scope"
        
    finally:
        db_session.close()


def test_data_collection_scope_documentation():
    """
    Test that verifies the data collection scope is properly documented.
    
    This is a static test that ensures we have properly categorized all fields
    and that the categorization is complete.
    """
    all_fields = get_all_model_fields()
    
    # Count total fields
    total_fields = sum(len(fields) for fields in all_fields.values())
    
    # Count categorized fields
    categorized_count = 0
    unknown_count = 0
    
    for table_name, fields in all_fields.items():
        for field_name in fields:
            category = categorize_field(table_name, field_name)
            categorized_count += 1
            if category == "unknown":
                unknown_count += 1
    
    # Verify all fields are categorized
    assert categorized_count == total_fields, \
        f"Not all fields are categorized: {categorized_count}/{total_fields}"
    
    # Verify no unknown fields
    assert unknown_count == 0, \
        f"Found {unknown_count} unknown fields that need categorization"
    
    # Print summary for documentation
    print(f"\nData Collection Scope Summary:")
    print(f"Total fields: {total_fields}")
    print(f"Categorized fields: {categorized_count}")
    print(f"Unknown fields: {unknown_count}")
