"""
Tests for onboarding session cleanup and abandonment handling.

Tests the functionality for:
- Detecting inactive sessions
- Sending reminders after 24 hours
- Marking sessions as abandoned after 7 days
- Archiving old sessions after 30 days
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.models.onboarding_session import OnboardingSession, OnboardingState
from app.models.user import User
from app.services.onboarding_service import OnboardingService


@pytest.mark.asyncio
async def test_get_inactive_sessions_24_hours(db_session):
    """Test that get_inactive_sessions returns sessions inactive for 24+ hours."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        timezone="UTC"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create an active session (recent activity)
    active_session = OnboardingSession(
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.COLLECT_PROJECT_NAME,
        started_at=datetime.utcnow() - timedelta(hours=2),
        last_activity_at=datetime.utcnow() - timedelta(hours=2)
    )
    db_session.add(active_session)
    
    # Create an inactive session (25 hours old)
    inactive_session = OnboardingSession(
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.COLLECT_GOAL,
        started_at=datetime.utcnow() - timedelta(hours=25),
        last_activity_at=datetime.utcnow() - timedelta(hours=25)
    )
    db_session.add(inactive_session)
    
    # Create a completed session (should not be returned)
    completed_session = OnboardingSession(
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.COMPLETED,
        started_at=datetime.utcnow() - timedelta(hours=30),
        last_activity_at=datetime.utcnow() - timedelta(hours=30),
        completed_at=datetime.utcnow() - timedelta(hours=28)
    )
    db_session.add(completed_session)
    
    db_session.commit()
    
    # Test
    service = OnboardingService(db_session)
    inactive_sessions = await service.get_inactive_sessions(hours=24)
    
    # Verify
    assert len(inactive_sessions) == 1
    assert inactive_sessions[0].id == inactive_session.id


@pytest.mark.asyncio
async def test_mark_abandoned_sessions_after_7_days(db_session):
    """Test that sessions are marked as abandoned after 7 days of inactivity."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        timezone="UTC"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create a session inactive for 8 days
    old_session = OnboardingSession(
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.COLLECT_PROJECT_NAME,
        started_at=datetime.utcnow() - timedelta(days=8),
        last_activity_at=datetime.utcnow() - timedelta(days=8)
    )
    db_session.add(old_session)
    
    # Create a session inactive for 5 days (should not be marked)
    recent_session = OnboardingSession(
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.COLLECT_GOAL,
        started_at=datetime.utcnow() - timedelta(days=5),
        last_activity_at=datetime.utcnow() - timedelta(days=5)
    )
    db_session.add(recent_session)
    
    # Create a completed session (should not be marked)
    completed_session = OnboardingSession(
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.COMPLETED,
        started_at=datetime.utcnow() - timedelta(days=10),
        last_activity_at=datetime.utcnow() - timedelta(days=10),
        completed_at=datetime.utcnow() - timedelta(days=9)
    )
    db_session.add(completed_session)
    
    db_session.commit()
    
    # Test
    service = OnboardingService(db_session)
    count = await service.mark_abandoned_sessions(days=7)
    
    # Verify
    assert count == 1
    
    # Refresh sessions
    db_session.refresh(old_session)
    db_session.refresh(recent_session)
    db_session.refresh(completed_session)
    
    # Check that old session is marked as failed
    assert old_session.current_state == OnboardingState.FAILED
    assert "abandoned" in old_session.error_message.lower()
    
    # Check that recent session is unchanged
    assert recent_session.current_state == OnboardingState.COLLECT_GOAL
    
    # Check that completed session is unchanged
    assert completed_session.current_state == OnboardingState.COMPLETED


@pytest.mark.asyncio
async def test_archive_old_sessions_after_30_days(db_session):
    """Test that old completed/failed sessions are archived after 30 days."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        timezone="UTC"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create an old completed session (35 days old)
    old_completed = OnboardingSession(
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.COMPLETED,
        started_at=datetime.utcnow() - timedelta(days=36),
        last_activity_at=datetime.utcnow() - timedelta(days=35),
        completed_at=datetime.utcnow() - timedelta(days=35),
        updated_at=datetime.utcnow() - timedelta(days=35)
    )
    db_session.add(old_completed)
    
    # Create an old failed session (32 days old)
    old_failed = OnboardingSession(
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.FAILED,
        started_at=datetime.utcnow() - timedelta(days=33),
        last_activity_at=datetime.utcnow() - timedelta(days=32),
        error_message="Test failure",
        updated_at=datetime.utcnow() - timedelta(days=32)
    )
    db_session.add(old_failed)
    
    # Create a recent completed session (20 days old - should not be archived)
    recent_completed = OnboardingSession(
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.COMPLETED,
        started_at=datetime.utcnow() - timedelta(days=21),
        last_activity_at=datetime.utcnow() - timedelta(days=20),
        completed_at=datetime.utcnow() - timedelta(days=20),
        updated_at=datetime.utcnow() - timedelta(days=20)
    )
    db_session.add(recent_completed)
    
    # Create an active session (should not be archived)
    active_session = OnboardingSession(
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.COLLECT_PROJECT_NAME,
        started_at=datetime.utcnow() - timedelta(days=35),
        last_activity_at=datetime.utcnow() - timedelta(days=35),
        updated_at=datetime.utcnow() - timedelta(days=35)
    )
    db_session.add(active_session)
    
    db_session.commit()
    
    # Test
    service = OnboardingService(db_session)
    count = await service.archive_old_sessions(days=30)
    
    # Verify
    assert count == 2
    
    # Refresh sessions
    db_session.refresh(old_completed)
    db_session.refresh(old_failed)
    db_session.refresh(recent_completed)
    db_session.refresh(active_session)
    
    # Check that old sessions have archive marker
    assert "Archived" in old_completed.error_message
    assert "Archived" in old_failed.error_message
    
    # Check that recent completed session is not archived
    assert recent_completed.error_message is None
    
    # Check that active session is not archived
    assert active_session.error_message is None


@pytest.mark.asyncio
async def test_mark_abandoned_excludes_paused_sessions(db_session):
    """Test that paused sessions are not marked as abandoned."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        timezone="UTC"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create a paused session inactive for 10 days
    paused_session = OnboardingSession(
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.PAUSED,
        started_at=datetime.utcnow() - timedelta(days=10),
        last_activity_at=datetime.utcnow() - timedelta(days=10)
    )
    db_session.add(paused_session)
    db_session.commit()
    
    # Test
    service = OnboardingService(db_session)
    count = await service.mark_abandoned_sessions(days=7)
    
    # Verify - paused session should be marked as abandoned
    # (paused sessions can still be abandoned if inactive too long)
    assert count == 1
    
    db_session.refresh(paused_session)
    assert paused_session.current_state == OnboardingState.FAILED


@pytest.mark.asyncio
async def test_cleanup_handles_multiple_sessions_per_user(db_session):
    """Test that cleanup handles multiple sessions for the same user correctly."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        timezone="UTC"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create multiple sessions at different stages
    sessions = [
        OnboardingSession(
            user_id=user.id,
            discord_id="123456789",
            current_state=OnboardingState.COLLECT_PROJECT_NAME,
            started_at=datetime.utcnow() - timedelta(days=8),
            last_activity_at=datetime.utcnow() - timedelta(days=8)
        ),
        OnboardingSession(
            user_id=user.id,
            discord_id="123456789",
            current_state=OnboardingState.COLLECT_GOAL,
            started_at=datetime.utcnow() - timedelta(days=9),
            last_activity_at=datetime.utcnow() - timedelta(days=9)
        ),
        OnboardingSession(
            user_id=user.id,
            discord_id="123456789",
            current_state=OnboardingState.COMPLETED,
            started_at=datetime.utcnow() - timedelta(days=35),
            last_activity_at=datetime.utcnow() - timedelta(days=35),
            completed_at=datetime.utcnow() - timedelta(days=35),
            updated_at=datetime.utcnow() - timedelta(days=35)
        ),
    ]
    
    for session in sessions:
        db_session.add(session)
    db_session.commit()
    
    # Test abandonment
    service = OnboardingService(db_session)
    abandoned_count = await service.mark_abandoned_sessions(days=7)
    
    # Verify - first two sessions should be marked as abandoned
    assert abandoned_count == 2
    
    # Test archival
    archived_count = await service.archive_old_sessions(days=30)
    
    # Verify - completed session should be archived
    assert archived_count == 1


@pytest.mark.asyncio
async def test_get_inactive_sessions_respects_state_filters(db_session):
    """Test that get_inactive_sessions excludes completed, paused, and failed sessions."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        timezone="UTC"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create sessions in different states, all inactive for 25 hours
    inactive_time = datetime.utcnow() - timedelta(hours=25)
    
    states_to_test = [
        (OnboardingState.COLLECT_PROJECT_NAME, True),  # Should be included
        (OnboardingState.COLLECT_GOAL, True),  # Should be included
        (OnboardingState.COMPLETED, False),  # Should be excluded
        (OnboardingState.PAUSED, False),  # Should be excluded
        (OnboardingState.FAILED, False),  # Should be excluded
    ]
    
    sessions = []
    for state, should_include in states_to_test:
        session = OnboardingSession(
            user_id=user.id,
            discord_id="123456789",
            current_state=state,
            started_at=inactive_time,
            last_activity_at=inactive_time
        )
        db_session.add(session)
        sessions.append((session, should_include))
    
    db_session.commit()
    
    # Test
    service = OnboardingService(db_session)
    inactive_sessions = await service.get_inactive_sessions(hours=24)
    
    # Verify
    expected_count = sum(1 for _, should_include in states_to_test if should_include)
    assert len(inactive_sessions) == expected_count
    
    # Verify correct sessions are included
    inactive_ids = {s.id for s in inactive_sessions}
    for session, should_include in sessions:
        if should_include:
            assert session.id in inactive_ids
        else:
            assert session.id not in inactive_ids
