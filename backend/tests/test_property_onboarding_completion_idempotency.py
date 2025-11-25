"""
Property-based tests for onboarding completion idempotency.

Feature: discord-dm-onboarding, Property 5: Completion idempotency
Validates: Requirements 5.1
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime, timedelta

from app.models.onboarding_session import OnboardingSession
from app.models.onboarding_session import OnboardingState
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
    preferred_tone=st.sampled_from(["coach", "manager", "buddy", "drill_sergeant"])
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_completion_idempotency(
    discord_id, project_name, project_goal, preferred_tone,
    db_session, test_user
):
    """
    Property 5: Completion idempotency
    
    For any onboarding session, completing onboarding multiple times should
    result in only one project being created.
    
    Validates: Requirements 5.1
    """
    cleanup_sessions_and_projects(db_session, test_user.id)
    service = OnboardingService(db_session)
    
    # Start onboarding and collect required data
    session = await service.start_onboarding(test_user.id, discord_id)
    
    # Set required data for completion
    await service.update_session_data(
        test_user.id,
        project_name=project_name,
        project_goal=project_goal,
        preferred_tone=preferred_tone
    )
    
    # Transition through states to reach CONFIRM_DETAILS
    await service.process_message(
        test_user.id,
        project_name,
        next_state=OnboardingState.COLLECT_PROJECT_NAME
    )
    await service.process_message(
        test_user.id,
        project_goal,
        next_state=OnboardingState.COLLECT_GOAL
    )
    await service.process_message(
        test_user.id,
        "no deadline",
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
        preferred_tone,
        next_state=OnboardingState.COLLECT_TONE
    )
    await service.process_message(
        test_user.id,
        "ready to complete",
        next_state=OnboardingState.CONFIRM_DETAILS
    )
    
    # Complete onboarding first time
    project1 = await service.complete_onboarding(test_user.id)
    
    # Attempt to complete again
    project2 = await service.complete_onboarding(test_user.id)
    
    # Should return same project, not create new one
    assert project1.id == project2.id
    assert project1.title == project2.title
    assert project1.goal == project2.goal
    
    # Verify only one project exists for this user with this name
    projects = db_session.query(Project).filter(
        Project.user_id == test_user.id,
        Project.title == project_name
    ).all()
    
    assert len(projects) == 1
    assert projects[0].id == project1.id


@pytest.mark.asyncio
@given(
    discord_id=st.text(min_size=1, max_size=100),
    project_name=st.text(min_size=1, max_size=200),
    project_goal=st.text(min_size=1, max_size=1000),
    deadline_days_ahead=st.integers(min_value=1, max_value=365)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_completion_marks_user_not_new(
    discord_id, project_name, project_goal, deadline_days_ahead,
    db_session, test_user
):
    """
    Property: Completion marks user as not new
    
    For any user who completes onboarding, the user's is_new flag should
    be set to false.
    
    Validates: Requirements 5.4
    """
    cleanup_sessions_and_projects(db_session, test_user.id)
    service = OnboardingService(db_session)
    
    # Ensure user starts as new
    test_user.is_new = True
    db_session.commit()
    
    # Start onboarding and collect required data
    session = await service.start_onboarding(test_user.id, discord_id)
    
    deadline = datetime.utcnow() + timedelta(days=deadline_days_ahead)
    await service.update_session_data(
        test_user.id,
        project_name=project_name,
        project_goal=project_goal,
        deadline=deadline
    )
    
    # Transition through states to reach CONFIRM_DETAILS
    await service.process_message(
        test_user.id,
        project_name,
        next_state=OnboardingState.COLLECT_PROJECT_NAME
    )
    await service.process_message(
        test_user.id,
        project_goal,
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
    
    # Complete onboarding
    project = await service.complete_onboarding(test_user.id)
    
    # Verify user is marked as not new
    db_session.refresh(test_user)
    assert test_user.is_new is False
    
    # Verify session is marked as completed
    db_session.expire_all()
    completed_session = await service.get_session(test_user.id)
    # get_session filters out completed sessions, so it should return None
    assert completed_session is None
    
    # Verify we can still find the completed session by querying directly
    from app.models.onboarding_session import OnboardingSession
    completed_session = db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id,
        OnboardingSession.current_state == OnboardingState.COMPLETED
    ).first()
    
    assert completed_session is not None
    assert completed_session.completed_at is not None


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
async def test_completion_requires_minimum_data(
    discord_id, project_name, project_goal, db_session, test_user
):
    """
    Property: Completion requires minimum data
    
    For any onboarding session, attempting to complete without required
    data (project_name, project_goal) should raise an error.
    """
    cleanup_sessions_and_projects(db_session, test_user.id)
    service = OnboardingService(db_session)
    
    # Start onboarding
    session = await service.start_onboarding(test_user.id, discord_id)
    
    # Try to complete without setting required data
    with pytest.raises(ValueError, match="Project name is required"):
        await service.complete_onboarding(test_user.id)
    
    # Set only project name
    await service.update_session_data(test_user.id, project_name=project_name)
    
    # Try to complete without goal
    with pytest.raises(ValueError, match="Project goal is required"):
        await service.complete_onboarding(test_user.id)
    
    # Set goal and transition to completable state
    await service.update_session_data(test_user.id, project_goal=project_goal)
    
    # Transition through states to reach CONFIRM_DETAILS
    await service.process_message(
        test_user.id,
        project_name,
        next_state=OnboardingState.COLLECT_PROJECT_NAME
    )
    await service.process_message(
        test_user.id,
        project_goal,
        next_state=OnboardingState.COLLECT_GOAL
    )
    await service.process_message(
        test_user.id,
        "no deadline",
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
    
    # Now completion should succeed
    project = await service.complete_onboarding(test_user.id)
    assert project is not None
    assert project.title == project_name
    assert project.goal == project_goal
