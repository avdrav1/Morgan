"""
Property-based tests for conversation history preservation.

Feature: discord-project-plan-management, Property 10: Conversation history preservation
Validates: Requirements 2.2, 6.1
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
def message_data(draw):
    """Generate valid message data."""
    return {
        "role": draw(st.sampled_from(["user", "assistant"])),
        "content": draw(st.text(min_size=1, max_size=500)),
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
    messages=st.lists(message_data(), min_size=1, max_size=20)
)
def test_conversation_history_preservation(user, project, messages):
    """
    Property 10: Conversation history preservation
    
    For any conversation about a project plan, the conversation history should be 
    maintained and available for context in subsequent messages within the same session.
    
    This test verifies that:
    1. Messages added to conversation history are preserved
    2. History can be retrieved for the same user and project
    3. Messages are returned in chronological order
    4. History is limited to the last 10 messages (MAX_HISTORY_LENGTH)
    5. Each message contains role, content, and timestamp
    
    Validates: Requirements 2.2, 6.1
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
        
        # Add all messages to the conversation
        for message in messages:
            manager.add_message(
                user_id=db_user.id,
                project_id=db_project.id,
                role=message["role"],
                content=message["content"]
            )
        
        # Retrieve conversation history
        history = manager.get_conversation_history(
            user_id=db_user.id,
            project_id=db_project.id
        )
        
        # Property verification 1: History should not be empty
        assert len(history) > 0, \
            "Conversation history should not be empty after adding messages"
        
        # Property verification 2: History should contain at most MAX_HISTORY_LENGTH messages
        max_length = ProjectPlanConversationManager.MAX_HISTORY_LENGTH
        assert len(history) <= max_length, \
            f"Conversation history should contain at most {max_length} messages, got {len(history)}"
        
        # Property verification 3: If more than MAX_HISTORY_LENGTH messages were added,
        # history should contain exactly the last MAX_HISTORY_LENGTH messages
        expected_count = min(len(messages), max_length)
        assert len(history) == expected_count, \
            f"Expected {expected_count} messages in history, got {len(history)}"
        
        # Property verification 4: Messages should be in chronological order
        for i in range(len(history) - 1):
            current_timestamp = datetime.fromisoformat(history[i]["timestamp"])
            next_timestamp = datetime.fromisoformat(history[i + 1]["timestamp"])
            assert current_timestamp <= next_timestamp, \
                f"Messages should be in chronological order: message at index {i} " \
                f"has timestamp {current_timestamp} which is after message at index {i+1} " \
                f"with timestamp {next_timestamp}"
        
        # Property verification 5: Each message should have required fields
        for msg in history:
            assert "role" in msg, \
                "Each message should have a 'role' field"
            assert "content" in msg, \
                "Each message should have a 'content' field"
            assert "timestamp" in msg, \
                "Each message should have a 'timestamp' field"
            assert msg["role"] in ["user", "assistant"], \
                f"Message role should be 'user' or 'assistant', got '{msg['role']}'"
            assert len(msg["content"]) > 0, \
                "Message content should not be empty"
        
        # Property verification 6: The last messages in history should match
        # the last messages that were added (accounting for MAX_HISTORY_LENGTH limit)
        expected_messages = messages[-expected_count:]
        for i, expected_msg in enumerate(expected_messages):
            actual_msg = history[i]
            assert actual_msg["role"] == expected_msg["role"], \
                f"Message {i} role should be '{expected_msg['role']}', got '{actual_msg['role']}'"
            assert actual_msg["content"] == expected_msg["content"], \
                f"Message {i} content should match the added message"
        
        # Property verification 7: Retrieving history again should return the same data
        history_again = manager.get_conversation_history(
            user_id=db_user.id,
            project_id=db_project.id
        )
        assert len(history_again) == len(history), \
            "Retrieving history multiple times should return the same number of messages"
        for i in range(len(history)):
            assert history_again[i]["role"] == history[i]["role"], \
                "Message roles should be consistent across retrievals"
            assert history_again[i]["content"] == history[i]["content"], \
                "Message content should be consistent across retrievals"
    
    finally:
        db_session.close()


@settings(max_examples=100, deadline=None)
@given(
    user=user_data(),
    project=project_data(),
    message=message_data()
)
def test_conversation_history_single_message(user, project, message):
    """
    Property 10 (edge case): Single message preservation
    
    For any conversation with a single message, that message should be 
    preserved and retrievable.
    
    Validates: Requirements 2.2, 6.1
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
        
        # Add single message
        manager.add_message(
            user_id=db_user.id,
            project_id=db_project.id,
            role=message["role"],
            content=message["content"]
        )
        
        # Retrieve conversation history
        history = manager.get_conversation_history(
            user_id=db_user.id,
            project_id=db_project.id
        )
        
        # Property verification: Single message should be preserved
        assert len(history) == 1, \
            f"History should contain exactly 1 message, got {len(history)}"
        assert history[0]["role"] == message["role"], \
            f"Message role should be '{message['role']}', got '{history[0]['role']}'"
        assert history[0]["content"] == message["content"], \
            "Message content should match the added message"
        assert "timestamp" in history[0], \
            "Message should have a timestamp"
    
    finally:
        db_session.close()


@settings(max_examples=100, deadline=None)
@given(
    user=user_data(),
    project1=project_data(),
    project2=project_data(),
    messages1=st.lists(message_data(), min_size=1, max_size=10),
    messages2=st.lists(message_data(), min_size=1, max_size=10)
)
def test_conversation_history_isolation_between_projects(user, project1, project2, messages1, messages2):
    """
    Property 10 (isolation): Conversation history isolation between projects
    
    For any user with multiple projects, conversation history for one project 
    should not affect or appear in the history of another project.
    
    Validates: Requirements 2.2, 6.1
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
        
        # Add messages to project 1
        for message in messages1:
            manager.add_message(
                user_id=db_user.id,
                project_id=db_project1.id,
                role=message["role"],
                content=message["content"]
            )
        
        # Add messages to project 2
        for message in messages2:
            manager.add_message(
                user_id=db_user.id,
                project_id=db_project2.id,
                role=message["role"],
                content=message["content"]
            )
        
        # Retrieve conversation history for both projects
        history1 = manager.get_conversation_history(
            user_id=db_user.id,
            project_id=db_project1.id
        )
        history2 = manager.get_conversation_history(
            user_id=db_user.id,
            project_id=db_project2.id
        )
        
        # Property verification 1: Each project should have its own history
        max_length = ProjectPlanConversationManager.MAX_HISTORY_LENGTH
        expected_count1 = min(len(messages1), max_length)
        expected_count2 = min(len(messages2), max_length)
        
        assert len(history1) == expected_count1, \
            f"Project 1 should have {expected_count1} messages, got {len(history1)}"
        assert len(history2) == expected_count2, \
            f"Project 2 should have {expected_count2} messages, got {len(history2)}"
        
        # Property verification 2: Messages from project 1 should not appear in project 2
        contents1 = {msg["content"] for msg in history1}
        contents2 = {msg["content"] for msg in history2}
        
        # Check that the last messages match what was added to each project
        expected_messages1 = messages1[-expected_count1:]
        expected_messages2 = messages2[-expected_count2:]
        
        for i, expected_msg in enumerate(expected_messages1):
            assert history1[i]["content"] == expected_msg["content"], \
                f"Project 1 message {i} should match the added message"
        
        for i, expected_msg in enumerate(expected_messages2):
            assert history2[i]["content"] == expected_msg["content"], \
                f"Project 2 message {i} should match the added message"
    
    finally:
        db_session.close()
