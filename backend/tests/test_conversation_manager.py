"""
Unit tests for ConversationManager.
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock

from app.models.task import Task, TaskStatus
from app.models.check_in import CheckIn
from app.services.conversation_manager import ConversationManager


def test_get_conversation_context_from_stored_context():
    """Test retrieving conversation context from stored JSONB field."""
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    # Create a check-in with stored conversation context
    check_in = CheckIn(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        conversation_context=[
            {"role": "assistant", "content": "How's it going?"},
            {"role": "user", "content": "Good progress"},
            {"role": "assistant", "content": "Great to hear!"}
        ]
    )
    
    context = manager.get_conversation_context(check_in)
    
    assert len(context) == 3
    assert context[0]["role"] == "assistant"
    assert context[1]["role"] == "user"
    assert context[2]["role"] == "assistant"


def test_get_conversation_context_from_fields():
    """Test building conversation context from individual fields."""
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    # Create a check-in without stored context but with individual fields
    check_in = CheckIn(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        message_sent="How's the task going?",
        user_response="Making progress",
        assistant_reply="That's great!"
    )
    
    context = manager.get_conversation_context(check_in)
    
    assert len(context) == 3
    assert context[0]["content"] == "How's the task going?"
    assert context[1]["content"] == "Making progress"
    assert context[2]["content"] == "That's great!"


def test_get_conversation_context_max_history():
    """Test that max_history limits the returned context."""
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    # Create a check-in with many conversation turns
    check_in = CheckIn(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        conversation_context=[
            {"role": "assistant", "content": f"Message {i}"}
            for i in range(20)
        ]
    )
    
    context = manager.get_conversation_context(check_in, max_history=5)
    
    assert len(context) == 5
    # Should return the last 5 messages
    assert context[0]["content"] == "Message 15"
    assert context[4]["content"] == "Message 19"


def test_detect_blocker_pattern_time():
    """Test detecting time-related blockers."""
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    task = Task(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Test Task",
        order=1,
        status=TaskStatus.IN_PROGRESS
    )
    
    conversation = [
        {"role": "assistant", "content": "How's it going?"},
        {"role": "user", "content": "I don't have enough time to finish this"}
    ]
    
    blocker_type = manager.detect_blocker_pattern(task, conversation)
    
    assert blocker_type == "time"


def test_detect_blocker_pattern_clarity():
    """Test detecting clarity-related blockers."""
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    task = Task(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Test Task",
        order=1,
        status=TaskStatus.IN_PROGRESS
    )
    
    conversation = [
        {"role": "assistant", "content": "What's blocking you?"},
        {"role": "user", "content": "I'm not sure how to start this task"}
    ]
    
    blocker_type = manager.detect_blocker_pattern(task, conversation)
    
    assert blocker_type == "clarity"


def test_detect_blocker_pattern_emotional():
    """Test detecting emotional blockers."""
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    task = Task(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Test Task",
        order=1,
        status=TaskStatus.IN_PROGRESS
    )
    
    conversation = [
        {"role": "assistant", "content": "How are you feeling about this?"},
        {"role": "user", "content": "I'm feeling overwhelmed by this task"}
    ]
    
    blocker_type = manager.detect_blocker_pattern(task, conversation)
    
    assert blocker_type == "emotional"


def test_detect_blocker_pattern_external():
    """Test detecting external blockers."""
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    task = Task(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Test Task",
        order=1,
        status=TaskStatus.IN_PROGRESS
    )
    
    conversation = [
        {"role": "assistant", "content": "What's the status?"},
        {"role": "user", "content": "I'm waiting for approval from someone else"}
    ]
    
    blocker_type = manager.detect_blocker_pattern(task, conversation)
    
    assert blocker_type == "external"


def test_detect_blocker_pattern_scope():
    """Test detecting scope-related blockers."""
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    task = Task(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Test Task",
        order=1,
        status=TaskStatus.IN_PROGRESS
    )
    
    conversation = [
        {"role": "assistant", "content": "What's the challenge?"},
        {"role": "user", "content": "This task is too big to handle"}
    ]
    
    blocker_type = manager.detect_blocker_pattern(task, conversation)
    
    assert blocker_type == "scope"


def test_detect_blocker_pattern_no_blocker():
    """Test that no blocker is detected in positive conversation."""
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    task = Task(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Test Task",
        order=1,
        status=TaskStatus.IN_PROGRESS
    )
    
    conversation = [
        {"role": "assistant", "content": "How's it going?"},
        {"role": "user", "content": "Great! Making good progress"}
    ]
    
    blocker_type = manager.detect_blocker_pattern(task, conversation)
    
    assert blocker_type is None


def test_extract_reschedule_intent_direct():
    """Test detecting direct reschedule requests."""
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    assert manager.extract_reschedule_intent("Can we reschedule this?") is True
    assert manager.extract_reschedule_intent("I need to push this back") is True
    assert manager.extract_reschedule_intent("Can I postpone the deadline?") is True


def test_extract_reschedule_intent_indirect():
    """Test detecting indirect reschedule signals."""
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    assert manager.extract_reschedule_intent("I need more time") is True
    assert manager.extract_reschedule_intent("I can't make it by Friday") is True
    assert manager.extract_reschedule_intent("I'm behind schedule") is True


def test_extract_reschedule_intent_no_intent():
    """Test that no reschedule intent is detected in normal responses."""
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    assert manager.extract_reschedule_intent("Making good progress") is False
    assert manager.extract_reschedule_intent("Almost done") is False
    assert manager.extract_reschedule_intent("On track") is False


def test_extract_reschedule_intent_empty():
    """Test handling empty input."""
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    assert manager.extract_reschedule_intent("") is False
    assert manager.extract_reschedule_intent(None) is False
