"""
Property-based tests for onboarding completion marking.

Feature: discord-dm-onboarding, Property 10: Onboarding completion marking
Validates: Requirements 5.4
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime, timedelta

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
    deadline_days_ahead=st.integers(min_value=1, max_value=365),
    preferred_tone=st.sampled_from(["coach", "manager", "buddy", "drill_sergeant"])
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_onboarding_completion_marking(
    discord_id, project_name, project_goal, deadline_days_ahead, preferred_tone,
    db_session, test_user
):
    """
    Property 10: Onboarding completion marking
    
    For any user who completes onboarding, the user's is_new flag should
    be set to false and the onboarding session should be marked as COMPLETED.
    
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
        deadline=deadline,
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
        preferred_tone,
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
    assert test_user.is_new is False, "User should be marked as not new after completing onboarding"
    
    # Verify session is marked as completed
    db_session.expire_all()
    completed_session = db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id,
        OnboardingSession.current_state == OnboardingState.COMPLETED
    ).first()
    
    assert completed_session is not None, "Onboarding session should exist"
    assert completed_session.current_state == OnboardingState.COMPLETED, "Session should be in COMPLETED state"
    assert completed_session.completed_at is not None, "Session should have a completion timestamp"
    
    # Verify the project was created
    assert project is not None, "Project should be created"
    assert project.title == project_name, "Project title should match"
    assert project.goal == project_goal, "Project goal should match"


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
async def test_completion_marking_without_deadline(
    discord_id, project_name, project_goal,
    db_session, test_user
):
    """
    Property 10: Onboarding completion marking (without deadline)
    
    For any user who completes onboarding without a deadline, the user's
    is_new flag should still be set to false and the session marked as COMPLETED.
    
    Validates: Requirements 5.4
    """
    cleanup_sessions_and_projects(db_session, test_user.id)
    service = OnboardingService(db_session)
    
    # Ensure user starts as new
    test_user.is_new = True
    db_session.commit()
    
    # Start onboarding and collect required data (no deadline)
    session = await service.start_onboarding(test_user.id, discord_id)
    
    await service.update_session_data(
        test_user.id,
        project_name=project_name,
        project_goal=project_goal
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
    assert test_user.is_new is False, "User should be marked as not new even without deadline"
    
    # Verify session is marked as completed
    db_session.expire_all()
    completed_session = db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id,
        OnboardingSession.current_state == OnboardingState.COMPLETED
    ).first()
    
    assert completed_session is not None, "Onboarding session should exist"
    assert completed_session.current_state == OnboardingState.COMPLETED, "Session should be in COMPLETED state"
    assert completed_session.completed_at is not None, "Session should have a completion timestamp"


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
async def test_completion_marking_persists_tone(
    discord_id, project_name, project_goal, preferred_tone,
    db_session, test_user
):
    """
    Property 10: Onboarding completion marking (tone persistence)
    
    For any user who completes onboarding with a preferred tone, the user's
    preferred_tone should be updated to match the onboarding selection.
    
    Validates: Requirements 5.4
    """
    cleanup_sessions_and_projects(db_session, test_user.id)
    service = OnboardingService(db_session)
    
    # Ensure user starts as new with default tone
    test_user.is_new = True
    test_user.preferred_tone = "coach"  # Default
    db_session.commit()
    
    # Start onboarding and collect required data
    session = await service.start_onboarding(test_user.id, discord_id)
    
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
        "ready",
        next_state=OnboardingState.CONFIRM_DETAILS
    )
    
    # Complete onboarding
    project = await service.complete_onboarding(test_user.id)
    
    # Verify user's preferred tone was updated
    db_session.refresh(test_user)
    assert test_user.preferred_tone == preferred_tone, "User's preferred tone should be updated from onboarding"
    assert test_user.is_new is False, "User should be marked as not new"
    
    # Verify session is marked as completed
    db_session.expire_all()
    completed_session = db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user.id,
        OnboardingSession.current_state == OnboardingState.COMPLETED
    ).first()
    
    assert completed_session is not None, "Onboarding session should exist"
    assert completed_session.current_state == OnboardingState.COMPLETED, "Session should be in COMPLETED state"
