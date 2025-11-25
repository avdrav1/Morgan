"""
Property-based tests for onboarding data persistence.

Feature: discord-dm-onboarding, Property 3: Data persistence
Validates: Requirements 6.2
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from datetime import datetime, timedelta

from app.models.onboarding_session import OnboardingState
from app.services.onboarding_service import OnboardingService


@pytest.mark.asyncio
@given(
    discord_id=st.text(min_size=1, max_size=100),
    project_name=st.text(min_size=1, max_size=200),
    message=st.text(min_size=1, max_size=500)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_data_persistence_after_message(
    discord_id, project_name, message, db_session, test_user
):
    """
    Property 3: Data persistence
    
    For any onboarding session, after each user response is processed,
    the collected data should be persisted to the database before sending
    the next question.
    
    Validates: Requirements 6.2
    """
    # Clean up any existing sessions
    from app.models.onboarding_session import OnboardingSession
    db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id
    ).delete()
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Start onboarding
    session = await service.start_onboarding(test_user.id, discord_id)
    initial_session_id = session.id
    
    # Process a message and update session data
    await service.update_session_data(test_user.id, project_name=project_name)
    await service.process_message(
        test_user.id,
        message,
        next_state=OnboardingState.COLLECT_PROJECT_NAME
    )
    
    # Fetch session from database (fresh query)
    db_session.expire_all()  # Clear session cache
    updated_session = await service.get_session(test_user.id)
    
    # Verify data was persisted
    assert updated_session is not None
    assert updated_session.id == initial_session_id
    assert updated_session.project_name == project_name
    assert updated_session.current_state == OnboardingState.COLLECT_PROJECT_NAME
    
    # Verify last_activity_at was updated
    assert updated_session.last_activity_at is not None


@pytest.mark.asyncio
@given(
    discord_id=st.text(min_size=1, max_size=100),
    project_name=st.text(min_size=1, max_size=200),
    project_goal=st.text(min_size=1, max_size=1000),
    checkin_frequency=st.sampled_from(["daily", "every_2_days", "every_3_days", "weekly"]),
    preferred_tone=st.sampled_from(["coach", "manager", "buddy", "drill_sergeant"])
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_multiple_field_persistence(
    discord_id, project_name, project_goal, checkin_frequency, preferred_tone,
    db_session, test_user
):
    """
    Property: Multiple field persistence
    
    For any onboarding session, updating multiple fields should persist
    all changes to the database.
    """
    # Clean up any existing sessions
    from app.models.onboarding_session import OnboardingSession
    db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id
    ).delete()
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Start onboarding
    session = await service.start_onboarding(test_user.id, discord_id)
    
    # Update multiple fields
    await service.update_session_data(
        test_user.id,
        project_name=project_name,
        project_goal=project_goal,
        checkin_frequency=checkin_frequency,
        preferred_tone=preferred_tone
    )
    
    # Fetch session from database (fresh query)
    db_session.expire_all()
    updated_session = await service.get_session(test_user.id)
    
    # Verify all fields were persisted
    assert updated_session.project_name == project_name
    assert updated_session.project_goal == project_goal
    assert updated_session.checkin_frequency == checkin_frequency
    assert updated_session.preferred_tone == preferred_tone


@pytest.mark.asyncio
@given(
    discord_id=st.text(min_size=1, max_size=100),
    deadline_days_ahead=st.integers(min_value=1, max_value=365)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_deadline_persistence(
    discord_id, deadline_days_ahead, db_session, test_user
):
    """
    Property: Deadline persistence
    
    For any onboarding session, setting a deadline should persist
    the datetime value correctly.
    """
    # Clean up any existing sessions
    from app.models.onboarding_session import OnboardingSession
    db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id
    ).delete()
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Start onboarding
    session = await service.start_onboarding(test_user.id, discord_id)
    
    # Set deadline
    deadline = datetime.utcnow() + timedelta(days=deadline_days_ahead)
    await service.update_session_data(test_user.id, deadline=deadline)
    
    # Fetch session from database (fresh query)
    db_session.expire_all()
    updated_session = await service.get_session(test_user.id)
    
    # Verify deadline was persisted (allow small time difference due to microseconds)
    assert updated_session.deadline is not None
    time_diff = abs((updated_session.deadline - deadline).total_seconds())
    assert time_diff < 1  # Less than 1 second difference
