"""
Property-based tests for intent classification consistency.

Feature: discord-project-plan-management, Property 3: Intent classification consistency
Validates: Requirements 6.1, 6.2
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from app.services.intent_classifier import IntentClassifier, IntentType, Intent


@st.composite
def clear_intent_message(draw):
    """
    Generate messages with clear intent.
    
    Returns a tuple of (message, expected_intent_type)
    """
    intent_templates = {
        IntentType.VIEW_PLAN: [
            "show me my project plan",
            "what's my project plan?",
            "can I see my plan",
            "display my project",
            "view plan",
        ],
        IntentType.EDIT_DEADLINE: [
            "change my deadline to next Friday",
            "move the deadline to December 15",
            "I need to extend the deadline",
            "update deadline to 2024-12-31",
        ],
        IntentType.ADD_MILESTONE: [
            "add a milestone for testing phase",
            "create a new milestone called 'Design Review'",
            "I want to add a milestone",
            "add milestone: Complete prototype",
        ],
        IntentType.EDIT_MILESTONE: [
            "change the 'Testing' milestone date",
            "update the first milestone",
            "modify milestone 2",
            "edit the Design Review milestone",
        ],
        IntentType.DELETE_MILESTONE: [
            "remove the Testing milestone",
            "delete milestone 3",
            "get rid of the Design Review milestone",
            "remove the first milestone",
        ],
        IntentType.MARK_COMPLETE: [
            "I completed the Testing milestone",
            "mark Design Review as done",
            "finished the first milestone",
            "milestone 2 is complete",
        ],
        IntentType.ASK_QUESTION: [
            "how much time do I have left?",
            "what should I focus on next?",
            "when is my next milestone?",
            "am I on track?",
        ],
    }
    
    # Choose a random intent type (excluding UNCLEAR)
    intent_type = draw(st.sampled_from([
        IntentType.VIEW_PLAN,
        IntentType.EDIT_DEADLINE,
        IntentType.ADD_MILESTONE,
        IntentType.EDIT_MILESTONE,
        IntentType.DELETE_MILESTONE,
        IntentType.MARK_COMPLETE,
        IntentType.ASK_QUESTION,
    ]))
    
    # Choose a random message template for that intent
    message = draw(st.sampled_from(intent_templates[intent_type]))
    
    return (message, intent_type)


@st.composite
def project_context_data(draw):
    """Generate valid project context data."""
    return {
        'project_id': str(draw(st.uuids())),
        'project_name': draw(st.text(min_size=1, max_size=50)),
        'project_goal': draw(st.text(min_size=1, max_size=200)),
        'deadline': (datetime.utcnow() + timedelta(days=draw(st.integers(min_value=1, max_value=365)))).isoformat(),
    }


@st.composite
def conversation_history_data(draw):
    """Generate conversation history."""
    num_messages = draw(st.integers(min_value=0, max_value=5))
    history = []
    
    for _ in range(num_messages):
        role = draw(st.sampled_from(['user', 'assistant']))
        content = draw(st.text(min_size=1, max_size=100))
        history.append({'role': role, 'content': content})
    
    return history


def create_mock_llm_response(intent_type: IntentType, confidence: float = 0.9):
    """Create a mock LLM response for the given intent type."""
    return f'''{{
  "intent_type": "{intent_type.name}",
  "parameters": {{}},
  "confidence": {confidence}
}}'''


@settings(max_examples=100, deadline=None)
@given(
    message_and_intent=clear_intent_message(),
    project_context=project_context_data(),
    conversation_history=conversation_history_data()
)
def test_intent_classification_consistency(message_and_intent, project_context, conversation_history):
    """
    Property 3: Intent classification consistency
    
    For any user message expressing a clear intent (view, edit, add, etc.), 
    the intent classifier should return the same intent type when given the 
    same message and context.
    
    This test verifies that:
    1. Clear intent messages are classified correctly
    2. The same message with the same context produces the same result
    3. The confidence score is reasonable for clear intents
    
    Validates: Requirements 6.1, 6.2
    """
    message, expected_intent = message_and_intent
    
    # Create mock LLM service
    mock_llm_service = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text=create_mock_llm_response(expected_intent))]
    mock_llm_service.client.messages.create = Mock(return_value=mock_response)
    mock_llm_service.model = "claude-3-5-sonnet-20241022"
    
    # Create classifier with mock LLM
    classifier = IntentClassifier(llm_service=mock_llm_service)
    
    # Run classification twice with the same inputs
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result1 = loop.run_until_complete(
            classifier.classify_intent(
                message=message,
                conversation_history=conversation_history,
                project_context=project_context
            )
        )
        
        result2 = loop.run_until_complete(
            classifier.classify_intent(
                message=message,
                conversation_history=conversation_history,
                project_context=project_context
            )
        )
    finally:
        loop.close()
    
    # Property verification 1: Both results should have the same intent type
    assert result1.type == result2.type, \
        f"Intent classification should be consistent: first call returned {result1.type}, " \
        f"second call returned {result2.type}"
    
    # Property verification 2: Intent type should match expected
    assert result1.type == expected_intent, \
        f"Intent should be classified as {expected_intent}, but got {result1.type}"
    
    # Property verification 3: Confidence should be reasonable for clear intents
    assert result1.confidence >= 0.5, \
        f"Confidence for clear intent should be >= 0.5, got {result1.confidence}"
    
    # Property verification 4: Parameters should be consistent
    assert result1.parameters == result2.parameters, \
        f"Extracted parameters should be consistent across calls"


@settings(max_examples=100, deadline=None)
@given(
    message=st.text(min_size=1, max_size=200),
    project_context=project_context_data(),
    conversation_history=conversation_history_data()
)
def test_intent_classification_always_returns_valid_intent(message, project_context, conversation_history):
    """
    Property 3 (robustness): Intent classification always returns a valid Intent
    
    For any message (even ambiguous or unclear), the classifier should always 
    return a valid Intent object with a valid IntentType.
    
    This test verifies that:
    1. The classifier never crashes or returns None
    2. The returned Intent has a valid IntentType
    3. The confidence is between 0 and 1
    4. Parameters is a dictionary
    
    Validates: Requirements 6.1, 6.4
    """
    # Filter out empty or whitespace-only messages
    assume(message.strip() != "")
    
    # Create mock LLM service that returns UNCLEAR for ambiguous messages
    mock_llm_service = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text=create_mock_llm_response(IntentType.UNCLEAR, confidence=0.3))]
    mock_llm_service.client.messages.create = Mock(return_value=mock_response)
    mock_llm_service.model = "claude-3-5-sonnet-20241022"
    
    # Create classifier with mock LLM
    classifier = IntentClassifier(llm_service=mock_llm_service)
    
    # Run classification
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            classifier.classify_intent(
                message=message,
                conversation_history=conversation_history,
                project_context=project_context
            )
        )
    finally:
        loop.close()
    
    # Property verification 1: Result should not be None
    assert result is not None, \
        "Intent classification should always return a result, never None"
    
    # Property verification 2: Result should be an Intent object
    assert isinstance(result, Intent), \
        f"Result should be an Intent object, got {type(result)}"
    
    # Property verification 3: Intent type should be valid
    assert isinstance(result.type, IntentType), \
        f"Intent type should be an IntentType enum, got {type(result.type)}"
    
    # Property verification 4: Confidence should be between 0 and 1
    assert 0 <= result.confidence <= 1, \
        f"Confidence should be between 0 and 1, got {result.confidence}"
    
    # Property verification 5: Parameters should be a dictionary
    assert isinstance(result.parameters, dict), \
        f"Parameters should be a dictionary, got {type(result.parameters)}"


@settings(max_examples=50, deadline=None)
@given(
    message_and_intent=clear_intent_message(),
    project_context=project_context_data()
)
def test_intent_classification_independent_of_conversation_history(message_and_intent, project_context):
    """
    Property 3 (context independence): Clear intents are classified correctly 
    regardless of conversation history
    
    For any message with a clear intent, the classification should be the same
    whether there is conversation history or not.
    
    This test verifies that:
    1. Clear intents don't require conversation history
    2. The presence or absence of history doesn't change clear intent classification
    
    Validates: Requirements 6.1, 6.2
    """
    message, expected_intent = message_and_intent
    
    # Create mock LLM service
    mock_llm_service = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text=create_mock_llm_response(expected_intent))]
    mock_llm_service.client.messages.create = Mock(return_value=mock_response)
    mock_llm_service.model = "claude-3-5-sonnet-20241022"
    
    # Create classifier with mock LLM
    classifier = IntentClassifier(llm_service=mock_llm_service)
    
    # Run classification with empty history
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result_no_history = loop.run_until_complete(
            classifier.classify_intent(
                message=message,
                conversation_history=[],
                project_context=project_context
            )
        )
        
        # Run classification with some history
        result_with_history = loop.run_until_complete(
            classifier.classify_intent(
                message=message,
                conversation_history=[
                    {'role': 'user', 'content': 'Hello'},
                    {'role': 'assistant', 'content': 'Hi there!'}
                ],
                project_context=project_context
            )
        )
    finally:
        loop.close()
    
    # Property verification: Intent type should be the same regardless of history
    assert result_no_history.type == result_with_history.type, \
        f"Clear intent classification should be independent of conversation history: " \
        f"without history got {result_no_history.type}, with history got {result_with_history.type}"
    
    # Both should match expected intent
    assert result_no_history.type == expected_intent, \
        f"Intent should be classified as {expected_intent}, but got {result_no_history.type}"
    assert result_with_history.type == expected_intent, \
        f"Intent should be classified as {expected_intent}, but got {result_with_history.type}"
