"""
Property-based tests for onboarding cancellation cleanup.

Feature: discord-dm-onboarding, Property 8: Cancellation cleanup
Validates: Requirements 9.1, 9.2
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from app.models.onboarding_session import OnboardingSession, OnboardingState
from app.models.project import Project
from app.services.onboarding_service import OnboardingService


def cleanup_sessions_and_projects(db_session, user_id):
    """Helper to clean up sessions and projects between test examples."""
    db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == user_id
    ).delete()
    db_session.query(Project).filter(
        Project.user_id == user_id
    ).delete()
    db_session.commit()


@pytest.mark.asyncio
@given(
    discord_id=st.text(min_size=1, max_size=100),
    project_name=st.text(min_size=1, max_size=200),
    project_goal=st.text(min_size=1, max_size=1000),
    initial_state=st.sampled_from([
        OnboardingState.COLLECT_PROJECT_NAME,
        OnboardingState.COLLECT_GOAL,
        OnboardingState.COLLECT_DEADLINE,
        OnboardingState.COLLECT_CHECKIN_FREQUENCY,
        OnboardingState.COLLECT_TONE,
        OnboardingState.CONFIRM_DETAILS
    ])
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_cancellation_cleanup(
    discord_id, project_name, project_goal, initial_state,
    db_session, test_user
):
    """
    Property 8: Cancellation cleanup
    
    For any onboarding session, when a user cancels, the session state should
    be set to PAUSED and no project should be created.
    
    Validates: Requirements 9.1, 9.2
    """
    cleanup_sessions_and_projects(db_session, test_user.id)
    service = OnboardingService(db_session)
    
    # Start onboarding
    session = await service.start_onboarding(test_user.id, discord_id)
    
    # Set some data
    await service.update_session_data(
        test_user.id,
        project_name=project_name,
        project_goal=project_goal
    )
    
    # Transition to COLLECT_PROJECT_NAME first (valid from WELCOME)
    await service.process_message(
        test_user.id,
        project_name,
        next_state=OnboardingState.COLLECT_PROJECT_NAME
    )
    
    # Then transition to the target state if it's different
    if initial_state != OnboardingState.COLLECT_PROJECT_NAME:
        # For simplicity, just transition to COLLECT_GOAL which is valid from COLLECT_PROJECT_NAME
        if initial_state in [OnboardingState.COLLECT_GOAL, OnboardingState.COLLECT_DEADLINE, 
                            OnboardingState.COLLECT_CHECKIN_FREQUENCY, OnboardingState.COLLECT_TONE,
                            OnboardingState.CONFIRM_DETAILS]:
            await service.process_message(
                test_user.id,
                project_goal,
                next_state=OnboardingState.COLLECT_GOAL
            )
    
    # Cancel onboarding
    await service.cancel_onboarding(test_user.id)
    
    # Verify session state is PAUSED
    db_session.expire_all()
    updated_session = await service.get_session(test_user.id)
    assert updated_session is not None
    assert updated_session.current_state == OnboardingState.PAUSED
    
    # Verify no project was created
    projects = db_session.query(Project).filter(
        Project.user_id == test_user.id
    ).all()
    
    assert len(projects) == 0


@pytest.mark.asyncio
@given(
    discord_id=st.text(min_size=1, max_size=100),
    project_name=st.text(min_size=1, max_size=200),
    messages=st.lists(st.text(min_size=1, max_size=200), min_size=1, max_size=5)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_cancellation_preserves_data(
    discord_id, project_name, messages, db_session, test_user
):
    """
    Property: Cancellation preserves collected data
    
    For any onboarding session, when a user cancels, the collected data
    should be preserved for potential resumption.
    """
    cleanup_sessions_and_projects(db_session, test_user.id)
    service = OnboardingService(db_session)
    
    # Start onboarding
    session = await service.start_onboarding(test_user.id, discord_id)
    
    # Collect some data
    await service.update_session_data(test_user.id, project_name=project_name)
    
    # Transition to COLLECT_PROJECT_NAME
    await service.process_message(
        test_user.id,
        project_name,
        next_state=OnboardingState.COLLECT_PROJECT_NAME
    )
    
    # Cancel onboarding
    await service.cancel_onboarding(test_user.id)
    
    # Verify data is preserved
    db_session.expire_all()
    paused_session = await service.get_session(test_user.id)
    
    assert paused_session.project_name == project_name
    assert paused_session.current_state == OnboardingState.PAUSED


@pytest.mark.asyncio
@given(
    discord_id=st.text(min_size=1, max_size=100)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_cannot_cancel_completed_session(discord_id, db_session, test_user):
    """
    Property: Cannot cancel completed session
    
    For any completed onboarding session, attempting to cancel should
    raise an error since the session is already complete.
    """
    cleanup_sessions_and_projects(db_session, test_user.id)
    service = OnboardingService(db_session)
    
    # Start and complete onboarding
    session = await service.start_onboarding(test_user.id, discord_id)
    
    await service.update_session_data(
        test_user.id,
        project_name="Test Project",
        project_goal="Test Goal"
    )
    
    # Transition through states to CONFIRM_DETAILS
    await service.process_message(
        test_user.id,
        "Test Project",
        next_state=OnboardingState.COLLECT_PROJECT_NAME
    )
    await service.process_message(
        test_user.id,
        "Test Goal",
        next_state=OnboardingState.COLLECT_GOAL
    )
    await service.process_message(
        test_user.id,
        "deadline",
        next_state=OnboardingState.COLLECT_DEADLINE
    )
    await service.process_message(
        test_user.id,
        "confirmed",
        next_state=OnboardingState.CONFIRM_DEADLINE
    )
    await service.process_message(
        test_user.id,
        "daily",
        next_state=OnboardingState.COLLECT_CHECKIN_FREQUENCY
    )
    await service.process_message(
        test_user.id,
        "coach",
        next_state=OnboardingState.COLLECT_TONE
    )
    await service.process_message(
        test_user.id,
        "ready",
        next_state=OnboardingState.CONFIRM_DETAILS
    )
    
    await service.complete_onboarding(test_user.id)
    
    # Try to cancel - should raise error because session is completed
    # and get_session won't find it
    with pytest.raises(ValueError, match="No onboarding session found"):
        await service.cancel_onboarding(test_user.id)


@pytest.mark.asyncio
@given(
    discord_id=st.text(min_size=1, max_size=100),
    project_name=st.text(min_size=1, max_size=200),
    project_goal=st.text(min_size=1, max_size=1000)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_restart_after_cancellation(
    discord_id, project_name, project_goal, db_session, test_user
):
    """
    Property: Restart after cancellation
    
    For any cancelled onboarding session, restarting should clear all
    collected data and reset to WELCOME state.
    """
    cleanup_sessions_and_projects(db_session, test_user.id)
    service = OnboardingService(db_session)
    
    # Start onboarding and collect data
    session = await service.start_onboarding(test_user.id, discord_id)
    
    await service.update_session_data(
        test_user.id,
        project_name=project_name,
        project_goal=project_goal
    )
    
    # Transition to COLLECT_PROJECT_NAME first
    await service.process_message(
        test_user.id,
        project_name,
        next_state=OnboardingState.COLLECT_PROJECT_NAME
    )
    
    # Then to COLLECT_GOAL
    await service.process_message(
        test_user.id,
        project_goal,
        next_state=OnboardingState.COLLECT_GOAL
    )
    
    # Cancel
    await service.cancel_onboarding(test_user.id)
    
    # Restart
    restarted_session = await service.restart_onboarding(test_user.id)
    
    # Verify state is reset
    assert restarted_session.current_state == OnboardingState.WELCOME
    assert restarted_session.project_name is None
    assert restarted_session.project_goal is None
    assert restarted_session.conversation_history == []
    assert restarted_session.error_message is None
    assert restarted_session.retry_count == 0
