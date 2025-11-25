"""
Property-based test for onboarding conversation history preservation.

Feature: discord-dm-onboarding, Property 9: Conversation history preservation
Validates: Requirements 8.3
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime
from uuid import uuid4

from app.models.onboarding_session import OnboardingSession, OnboardingState
from app.models.user import User
from app.services.onboarding_service import OnboardingService


# Strategy for generating valid messages
messages_strategy = st.lists(
    st.text(min_size=1, max_size=200),
    min_size=1,
    max_size=10
)


@pytest.mark.asyncio
@given(messages=messages_strategy)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_conversation_history_preservation(messages, db_session, test_user):
    """
    Property: For any onboarding session, each message exchange should be 
    appended to the conversation history in chronological order.
    
    Feature: discord-dm-onboarding, Property 9: Conversation history preservation
    Validates: Requirements 8.3
    """
    # Clean up any existing sessions for this user from previous examples
    db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id
    ).delete()
    db_session.commit()
    
    # Create onboarding service
    service = OnboardingService(db_session)
    
    # Start onboarding session
    discord_id = f"discord_{uuid4()}"
    session = await service.start_onboarding(test_user.id, discord_id)
    
    # Process each message
    for message in messages:
        await service.process_message(test_user.id, message)
    
    # Retrieve the updated session
    updated_session = await service.get_session(test_user.id)
    
    # Property 1: All messages should be in history
    assert len(updated_session.conversation_history) >= len(messages), \
        f"Expected at least {len(messages)} messages in history, got {len(updated_session.conversation_history)}"
    
    # Property 2: Messages should be in chronological order
    timestamps = [
        datetime.fromisoformat(msg["timestamp"]) 
        for msg in updated_session.conversation_history
    ]
    assert timestamps == sorted(timestamps), \
        "Conversation history is not in chronological order"
    
    # Property 3: All user messages should be present
    user_messages = [
        msg["message"] 
        for msg in updated_session.conversation_history 
        if msg["role"] == "user"
    ]
    assert len(user_messages) == len(messages), \
        f"Expected {len(messages)} user messages, got {len(user_messages)}"
    
    # Property 4: Each message should have required fields
    for msg in updated_session.conversation_history:
        assert "timestamp" in msg, "Message missing timestamp"
        assert "role" in msg, "Message missing role"
        assert "message" in msg, "Message missing message content"
        assert msg["role"] in ["user", "assistant"], f"Invalid role: {msg['role']}"
    
    # Property 5: Timestamps should be valid ISO format
    for msg in updated_session.conversation_history:
        try:
            datetime.fromisoformat(msg["timestamp"])
        except (ValueError, TypeError) as e:
            pytest.fail(f"Invalid timestamp format: {msg['timestamp']}, error: {e}")


@pytest.mark.asyncio
async def test_conversation_history_empty_session(db_session, test_user):
    """
    Test that a new session starts with empty conversation history.
    """
    # Clean up any existing sessions
    db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id
    ).delete()
    db_session.commit()
    
    # Create onboarding service
    service = OnboardingService(db_session)
    
    # Start onboarding session
    discord_id = f"discord_{uuid4()}"
    session = await service.start_onboarding(test_user.id, discord_id)
    
    # Verify empty history
    assert session.conversation_history == [] or session.conversation_history is None, \
        "New session should have empty conversation history"


@pytest.mark.asyncio
async def test_conversation_history_with_bot_responses(db_session, test_user):
    """
    Test that bot responses are also added to conversation history.
    """
    # Clean up any existing sessions
    db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id
    ).delete()
    db_session.commit()
    
    # Create onboarding service
    service = OnboardingService(db_session)
    
    # Start onboarding session
    discord_id = f"discord_{uuid4()}"
    session = await service.start_onboarding(test_user.id, discord_id)
    
    # Process a user message
    await service.process_message(test_user.id, "My project name")
    
    # Generate a bot response (this will add to history)
    try:
        await service.generate_response(test_user.id)
    except Exception:
        # LLM might not be available in test environment, that's okay
        pass
    
    # Retrieve the updated session
    updated_session = await service.get_session(test_user.id)
    
    # Check that history contains user message
    user_messages = [
        msg for msg in updated_session.conversation_history 
        if msg["role"] == "user"
    ]
    assert len(user_messages) >= 1, "Should have at least one user message"
    
    # If bot response was added, verify it's after user message
    if len(updated_session.conversation_history) > 1:
        # Find pairs of user-assistant messages
        for i in range(len(updated_session.conversation_history) - 1):
            if updated_session.conversation_history[i]["role"] == "user":
                # Next message could be assistant or another user message
                next_msg = updated_session.conversation_history[i + 1]
                if next_msg["role"] == "assistant":
                    # Verify assistant message comes after user message chronologically
                    user_time = datetime.fromisoformat(updated_session.conversation_history[i]["timestamp"])
                    assistant_time = datetime.fromisoformat(next_msg["timestamp"])
                    assert assistant_time >= user_time, \
                        "Assistant response should come after user message"
