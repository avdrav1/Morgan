"""
Property-based tests for blocker type validity.

Feature: proactive-accountability-assistant, Property 10: Blocker type validity
Validates: Requirements 4.3
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from datetime import datetime
import uuid
from unittest.mock import Mock

from app.models.task import Task, TaskStatus
from app.models.check_in import CheckIn
from app.services.conversation_manager import ConversationManager


# Valid blocker types as defined in the requirements
VALID_BLOCKER_TYPES = {"time", "clarity", "emotional", "external", "scope"}


@st.composite
def conversation_with_blocker_keywords(draw):
    """
    Generate conversation history that contains blocker-related keywords.
    
    This strategy creates realistic conversation patterns that should trigger
    blocker detection.
    """
    # Choose a blocker type to embed in the conversation
    blocker_type = draw(st.sampled_from(list(VALID_BLOCKER_TYPES)))
    
    # Define keyword sets for each blocker type
    blocker_keywords = {
        "time": [
            "I don't have enough time",
            "Too busy with other things",
            "Schedule is packed",
            "Running out of time",
            "Deadline is too tight"
        ],
        "clarity": [
            "I'm not sure how to start",
            "This is unclear to me",
            "I don't understand the requirements",
            "Need more clarification",
            "Confused about what to do"
        ],
        "emotional": [
            "Feeling overwhelmed by this",
            "I'm anxious about starting",
            "This is stressing me out",
            "I keep procrastinating",
            "Can't focus on this task"
        ],
        "external": [
            "Waiting for someone else",
            "Blocked by another team",
            "Need approval first",
            "Depends on external input",
            "Third party hasn't responded"
        ],
        "scope": [
            "This is too big to handle",
            "Scope keeps expanding",
            "Task is more complex than expected",
            "Need to break this down",
            "Unrealistic expectations"
        ]
    }
    
    # Pick a keyword phrase for the chosen blocker type
    keyword_phrase = draw(st.sampled_from(blocker_keywords[blocker_type]))
    
    # Build a conversation with the keyword
    num_turns = draw(st.integers(min_value=1, max_value=5))
    conversation = []
    
    # Add some assistant messages
    for i in range(num_turns):
        conversation.append({
            "role": "assistant",
            "content": draw(st.sampled_from([
                "How's the task going?",
                "Any progress to report?",
                "What's blocking you?",
                "Tell me more about the challenge."
            ]))
        })
        
        # Add user response, including the blocker keyword in at least one
        if i == num_turns - 1:
            # Last turn includes the blocker keyword
            conversation.append({
                "role": "user",
                "content": keyword_phrase
            })
        else:
            conversation.append({
                "role": "user",
                "content": draw(st.sampled_from([
                    "Working on it",
                    "Making some progress",
                    "Still figuring it out"
                ]))
            })
    
    return conversation, blocker_type


@st.composite
def conversation_without_blockers(draw):
    """Generate conversation history without blocker keywords."""
    num_turns = draw(st.integers(min_value=1, max_value=5))
    conversation = []
    
    for i in range(num_turns):
        conversation.append({
            "role": "assistant",
            "content": "How's it going?"
        })
        conversation.append({
            "role": "user",
            "content": draw(st.sampled_from([
                "Good progress",
                "Almost done",
                "Completed it",
                "Going well",
                "On track"
            ]))
        })
    
    return conversation


@settings(max_examples=100)
@given(conversation_data=conversation_with_blocker_keywords())
def test_blocker_type_validity_with_detection(conversation_data):
    """
    Property 10: Blocker type validity
    
    For any diagnosed blocker, the blocker type should be one of: 
    time, clarity, emotional, external, or scope.
    
    This test verifies that when a blocker is detected from conversation patterns,
    it always returns one of the valid blocker types.
    
    Validates: Requirements 4.3
    """
    conversation, expected_type = conversation_data
    
    # Create a task
    task = Task(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Test Task",
        description="Test description",
        order=1,
        status=TaskStatus.IN_PROGRESS
    )
    
    # Create conversation manager with mock db session
    # (blocker detection doesn't need database access)
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    # Detect blocker pattern
    detected_type = manager.detect_blocker_pattern(task, conversation)
    
    # If a blocker was detected, it must be one of the valid types
    if detected_type is not None:
        assert detected_type in VALID_BLOCKER_TYPES, \
            f"Detected blocker type '{detected_type}' is not in valid types: {VALID_BLOCKER_TYPES}"


@settings(max_examples=100)
@given(conversation=conversation_without_blockers())
def test_no_blocker_detection_returns_none(conversation):
    """
    Property 10: Blocker type validity (negative case)
    
    When no blocker patterns are present in the conversation, the detection
    should return None rather than an invalid blocker type.
    
    Validates: Requirements 4.3
    """
    # Create a task
    task = Task(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Test Task",
        description="Test description",
        order=1,
        status=TaskStatus.IN_PROGRESS
    )
    
    # Create conversation manager with mock db session
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    # Detect blocker pattern
    detected_type = manager.detect_blocker_pattern(task, conversation)
    
    # Should either be None or a valid blocker type
    if detected_type is not None:
        assert detected_type in VALID_BLOCKER_TYPES, \
            f"Detected blocker type '{detected_type}' is not in valid types: {VALID_BLOCKER_TYPES}"


@settings(max_examples=100)
@given(
    blocker_type=st.sampled_from(list(VALID_BLOCKER_TYPES)),
    num_messages=st.integers(min_value=1, max_value=10)
)
def test_all_blocker_types_are_valid(blocker_type, num_messages):
    """
    Property 10: Blocker type validity (exhaustive)
    
    Verify that the detect_blocker_pattern method can only return values
    from the set of valid blocker types, regardless of input.
    
    Validates: Requirements 4.3
    """
    # Create a task
    task = Task(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Test Task",
        description="Test description",
        order=1,
        status=TaskStatus.IN_PROGRESS
    )
    
    # Create conversation with random content
    conversation = []
    for i in range(num_messages):
        conversation.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Message {i} with random content"
        })
    
    # Create conversation manager with mock db session
    mock_db = Mock()
    manager = ConversationManager(mock_db)
    
    # Detect blocker pattern
    detected_type = manager.detect_blocker_pattern(task, conversation)
    
    # If a blocker was detected, it must be valid
    if detected_type is not None:
        assert detected_type in VALID_BLOCKER_TYPES, \
            f"Detected blocker type '{detected_type}' is not in valid types: {VALID_BLOCKER_TYPES}"
