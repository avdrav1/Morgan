"""
Property-based tests for onboarding session creation.

Feature: discord-dm-onboarding, Property 1: Onboarding session creation
Validates: Requirements 1.4
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from uuid import UUID
from datetime import datetime

from app.models.onboarding_session import OnboardingState
from app.services.onboarding_service import OnboardingService


@pytest.mark.asyncio
@given(
    user_id=st.uuids(),
    discord_id=st.text(min_size=1, max_size=100)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_onboarding_session_creation(user_id, discord_id, db_session, test_user):
    """
    Property 1: Onboarding session creation
    
    For any new user completing OAuth, starting the onboarding flow should create
    exactly one onboarding session in the database with state WELCOME.
    
    Validates: Requirements 1.4
    """
    # Clean up any existing sessions for this user from previous examples
    from app.models.onboarding_session import OnboardingSession
    db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id
    ).delete()
    db_session.commit()
    
    # Use the test user's ID instead of random UUID to ensure user exists
    service = OnboardingService(db_session)
    
    # Start onboarding
    session = await service.start_onboarding(test_user.id, discord_id)
    
    # Verify session was created with correct initial state
    assert session is not None
    assert session.current_state == OnboardingState.WELCOME
    assert session.user_id == test_user.id
    assert session.discord_id == discord_id
    assert session.started_at is not None
    assert isinstance(session.started_at, datetime)
    assert session.last_activity_at is not None
    assert session.conversation_history == []
    assert session.completed_at is None
    
    # Verify session is persisted in database
    retrieved_session = await service.get_session(test_user.id)
    assert retrieved_session is not None
    assert retrieved_session.id == session.id
    assert retrieved_session.current_state == OnboardingState.WELCOME


@pytest.mark.asyncio
@given(
    discord_id=st.text(min_size=1, max_size=100)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_onboarding_session_creation_idempotency(discord_id, db_session, test_user):
    """
    Property: Session creation idempotency
    
    For any user, calling start_onboarding multiple times should return the same
    session without creating duplicates.
    """
    # Clean up any existing sessions for this user from previous examples
    from app.models.onboarding_session import OnboardingSession
    db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id
    ).delete()
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Start onboarding first time
    session1 = await service.start_onboarding(test_user.id, discord_id)
    
    # Start onboarding second time
    session2 = await service.start_onboarding(test_user.id, discord_id)
    
    # Should return the same session
    assert session1.id == session2.id
    assert session1.current_state == session2.current_state
