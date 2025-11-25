"""
Property-based tests for onboarding session resumption.

Feature: discord-dm-onboarding, Property 4: Session resumption
Validates: Requirements 6.4
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
    project_goal=st.text(min_size=1, max_size=1000),
    checkin_frequency=st.sampled_from(["daily", "every_2_days", "every_3_days", "weekly"]),
    preferred_tone=st.sampled_from(["coach", "manager", "buddy", "drill_sergeant"])
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_session_resumption_preserves_data(
    discord_id, project_name, project_goal, checkin_frequency, preferred_tone,
    db_session, test_user
):
    """
    Property 4: Session resumption
    
    For any interrupted onboarding session, when the user returns,
    the system should resume from the last completed state with all
    previously collected data intact.
    
    Validates: Requirements 6.4
    """
    # Clean up any existing sessions
    from app.models.onboarding_session import OnboardingSession
    db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id
    ).delete()
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Start onboarding and collect some data
    session = await service.start_onboarding(test_user.id, discord_id)
    
    # Update session with partial data
    await service.update_session_data(
        test_user.id,
        project_name=project_name,
        project_goal=project_goal,
        checkin_frequency=checkin_frequency,
        preferred_tone=preferred_tone
    )
    
    # Transition through valid states: WELCOME -> COLLECT_PROJECT_NAME -> COLLECT_GOAL
    await service.process_message(
        test_user.id,
        "test message 1",
        next_state=OnboardingState.COLLECT_PROJECT_NAME
    )
    await service.process_message(
        test_user.id,
        "test message 2",
        next_state=OnboardingState.COLLECT_GOAL
    )
    
    # Store original data for comparison
    original_data = {
        "project_name": project_name,
        "project_goal": project_goal,
        "checkin_frequency": checkin_frequency,
        "preferred_tone": preferred_tone,
        "state": OnboardingState.COLLECT_GOAL
    }
    
    # Simulate interruption - clear session cache
    db_session.expire_all()
    
    # Resume session (get session again)
    resumed_session = await service.get_session(test_user.id)
    
    # Verify all data is intact
    assert resumed_session is not None
    assert resumed_session.project_name == original_data["project_name"]
    assert resumed_session.project_goal == original_data["project_goal"]
    assert resumed_session.checkin_frequency == original_data["checkin_frequency"]
    assert resumed_session.preferred_tone == original_data["preferred_tone"]
    assert resumed_session.current_state == original_data["state"]


@pytest.mark.asyncio
@given(
    discord_id=st.text(min_size=1, max_size=100),
    messages=st.lists(st.text(min_size=1, max_size=200), min_size=1, max_size=5)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_session_resumption_preserves_conversation_history(
    discord_id, messages, db_session, test_user
):
    """
    Property: Session resumption preserves conversation history
    
    For any interrupted onboarding session, when the user returns,
    the conversation history should be preserved.
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
    
    # Add messages to conversation history
    for message in messages:
        await service.process_message(test_user.id, message)
    
    # Store original conversation history length
    original_history_length = len(session.conversation_history)
    
    # Simulate interruption
    db_session.expire_all()
    
    # Resume session
    resumed_session = await service.get_session(test_user.id)
    
    # Verify conversation history is preserved
    assert resumed_session is not None
    assert len(resumed_session.conversation_history) >= original_history_length
    
    # Verify messages are in chronological order
    timestamps = [
        datetime.fromisoformat(msg["timestamp"])
        for msg in resumed_session.conversation_history
    ]
    assert timestamps == sorted(timestamps)


@pytest.mark.asyncio
@given(
    discord_id=st.text(min_size=1, max_size=100),
    project_name=st.text(min_size=1, max_size=200),
    inactivity_hours=st.integers(min_value=1, max_value=48)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_session_resumption_after_inactivity(
    discord_id, project_name, inactivity_hours, db_session, test_user
):
    """
    Property: Session resumption after inactivity
    
    For any onboarding session that has been inactive, the session
    should still be resumable with all data intact.
    """
    # Clean up any existing sessions
    from app.models.onboarding_session import OnboardingSession
    db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id
    ).delete()
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Start onboarding and collect some data
    session = await service.start_onboarding(test_user.id, discord_id)
    await service.update_session_data(test_user.id, project_name=project_name)
    
    # Simulate inactivity by manually updating last_activity_at
    past_time = datetime.utcnow() - timedelta(hours=inactivity_hours)
    session.last_activity_at = past_time
    db_session.commit()
    
    # Clear cache
    db_session.expire_all()
    
    # Resume session
    resumed_session = await service.get_session(test_user.id)
    
    # Verify session is still accessible and data is intact
    assert resumed_session is not None
    assert resumed_session.project_name == project_name
    
    # Verify last_activity_at reflects the inactivity
    time_since_activity = (datetime.utcnow() - resumed_session.last_activity_at).total_seconds()
    expected_inactivity = inactivity_hours * 3600
    # Allow 10 second tolerance
    assert abs(time_since_activity - expected_inactivity) < 10


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
async def test_session_resumption_preserves_deadline(
    discord_id, deadline_days_ahead, db_session, test_user
):
    """
    Property: Session resumption preserves deadline
    
    For any interrupted onboarding session with a deadline set,
    the deadline should be preserved when resuming.
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
    
    # Simulate interruption
    db_session.expire_all()
    
    # Resume session
    resumed_session = await service.get_session(test_user.id)
    
    # Verify deadline is preserved
    assert resumed_session is not None
    assert resumed_session.deadline is not None
    
    # Allow small time difference due to microseconds
    time_diff = abs((resumed_session.deadline - deadline).total_seconds())
    assert time_diff < 1
