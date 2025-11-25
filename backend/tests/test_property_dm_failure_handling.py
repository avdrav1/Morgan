"""
Property-based tests for DM failure handling.

Feature: discord-dm-onboarding, Property 6: DM failure handling
Validates: Requirements 7.1, 7.2
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from uuid import UUID

from app.services.onboarding_service import OnboardingService


@pytest.mark.asyncio
@given(
    discord_id=st.text(min_size=1, max_size=100)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_dm_failure_prevents_session_creation(discord_id, db_session, test_user):
    """
    Property 6: DM failure handling
    
    For any user where Discord DM delivery fails, the system should detect
    the failure and not create an onboarding session.
    
    Validates: Requirements 7.1, 7.2
    """
    # Clean up any existing sessions for this user from previous examples
    from app.models.onboarding_session import OnboardingSession
    db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id
    ).delete()
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Simulate DM failure by passing dm_enabled=False
    session = await service.start_onboarding(
        user_id=test_user.id,
        discord_id=discord_id,
        dm_enabled=False
    )
    
    # Session should not be created when DM fails
    assert session is None
    
    # Verify no session exists in database
    retrieved_session = await service.get_session(test_user.id)
    assert retrieved_session is None


@pytest.mark.asyncio
@given(
    discord_id=st.text(min_size=1, max_size=100)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_dm_success_creates_session(discord_id, db_session, test_user):
    """
    Property: DM success creates session
    
    For any user where Discord DM delivery succeeds, the system should
    create an onboarding session.
    
    This is the inverse of the DM failure property - ensuring that when
    DMs work, sessions are created properly.
    """
    # Clean up any existing sessions for this user from previous examples
    from app.models.onboarding_session import OnboardingSession, OnboardingState
    db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id
    ).delete()
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Simulate DM success by passing dm_enabled=True (default)
    session = await service.start_onboarding(
        user_id=test_user.id,
        discord_id=discord_id,
        dm_enabled=True
    )
    
    # Session should be created when DM succeeds
    assert session is not None
    assert session.current_state == OnboardingState.WELCOME
    assert session.user_id == test_user.id
    assert session.discord_id == discord_id
    
    # Verify session exists in database
    retrieved_session = await service.get_session(test_user.id)
    assert retrieved_session is not None
    assert retrieved_session.id == session.id


@pytest.mark.asyncio
@given(
    discord_id=st.text(min_size=1, max_size=100)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_dm_failure_logged(discord_id, db_session, test_user, caplog):
    """
    Property: DM failure is logged
    
    For any user where Discord DM delivery fails, the system should
    log the failure with appropriate context.
    
    Validates: Requirements 7.2
    """
    # Clean up any existing sessions for this user from previous examples
    from app.models.onboarding_session import OnboardingSession
    db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id
    ).delete()
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Clear any previous log records
    caplog.clear()
    
    # Simulate DM failure
    session = await service.start_onboarding(
        user_id=test_user.id,
        discord_id=discord_id,
        dm_enabled=False
    )
    
    # Verify failure was logged
    assert session is None
    
    # Check that a warning was logged about DM failure
    warning_logs = [record for record in caplog.records if record.levelname == "WARNING"]
    assert len(warning_logs) > 0
    
    # Verify the log contains relevant information
    log_messages = " ".join([record.message for record in warning_logs])
    assert "DM delivery failed" in log_messages or "dm_enabled=False" in log_messages
