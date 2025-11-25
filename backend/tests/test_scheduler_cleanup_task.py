"""
Tests for the scheduler cleanup task.

Tests the Celery task that runs the cleanup operations.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import patch, MagicMock

from app.models.onboarding_session import OnboardingSession, OnboardingState
from app.models.user import User
from app.tasks.scheduler import cleanup_abandoned_onboarding_sessions


def test_cleanup_abandoned_onboarding_sessions_task(db_session):
    """Test the Celery task for cleaning up abandoned sessions."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        timezone="UTC"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create sessions at different stages
    # Session to be abandoned (8 days old)
    abandoned_session = OnboardingSession(
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.COLLECT_PROJECT_NAME,
        started_at=datetime.utcnow() - timedelta(days=8),
        last_activity_at=datetime.utcnow() - timedelta(days=8)
    )
    db_session.add(abandoned_session)
    
    # Session to be archived (35 days old, completed)
    archived_session = OnboardingSession(
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.COMPLETED,
        started_at=datetime.utcnow() - timedelta(days=36),
        last_activity_at=datetime.utcnow() - timedelta(days=35),
        completed_at=datetime.utcnow() - timedelta(days=35),
        updated_at=datetime.utcnow() - timedelta(days=35)
    )
    db_session.add(archived_session)
    
    # Recent session (should not be affected)
    recent_session = OnboardingSession(
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.COLLECT_GOAL,
        started_at=datetime.utcnow() - timedelta(days=2),
        last_activity_at=datetime.utcnow() - timedelta(days=2)
    )
    db_session.add(recent_session)
    
    db_session.commit()
    
    # Store IDs for later retrieval
    abandoned_id = abandoned_session.id
    archived_id = archived_session.id
    recent_id = recent_session.id
    
    # Mock SessionLocal to return our test session
    with patch('app.tasks.scheduler.SessionLocal') as mock_session_local:
        mock_session_local.return_value = db_session
        
        # Run the task
        cleanup_abandoned_onboarding_sessions()
    
    # Re-query sessions from database
    abandoned_session = db_session.query(OnboardingSession).filter_by(id=abandoned_id).first()
    archived_session = db_session.query(OnboardingSession).filter_by(id=archived_id).first()
    recent_session = db_session.query(OnboardingSession).filter_by(id=recent_id).first()
    
    # Verify abandoned session is marked as failed
    assert abandoned_session.current_state == OnboardingState.FAILED
    assert "abandoned" in abandoned_session.error_message.lower()
    
    # Verify archived session has archive marker
    assert "Archived" in archived_session.error_message
    
    # Verify recent session is unchanged
    assert recent_session.current_state == OnboardingState.COLLECT_GOAL
    assert recent_session.error_message is None


def test_cleanup_task_handles_errors_gracefully(db_session):
    """Test that the cleanup task handles errors without crashing."""
    # Mock SessionLocal to return our test session
    with patch('app.tasks.scheduler.SessionLocal') as mock_session_local:
        mock_session_local.return_value = db_session
        
        # Mock the service methods to raise an exception
        with patch('app.services.onboarding_service.OnboardingService.mark_abandoned_sessions') as mock_mark:
            mock_mark.side_effect = Exception("Test error")
            
            # Run the task - should not raise exception
            try:
                cleanup_abandoned_onboarding_sessions()
                # Task should complete without raising
                assert True
            except Exception as e:
                pytest.fail(f"Task should handle errors gracefully, but raised: {e}")


def test_cleanup_task_logs_results(db_session):
    """Test that the cleanup task logs the results of cleanup operations."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        timezone="UTC"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create a session to be abandoned
    session = OnboardingSession(
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.COLLECT_PROJECT_NAME,
        started_at=datetime.utcnow() - timedelta(days=8),
        last_activity_at=datetime.utcnow() - timedelta(days=8)
    )
    db_session.add(session)
    db_session.commit()
    
    # Mock SessionLocal and logger
    with patch('app.tasks.scheduler.SessionLocal') as mock_session_local:
        mock_session_local.return_value = db_session
        
        with patch('app.tasks.scheduler.logger') as mock_logger:
            # Run the task
            cleanup_abandoned_onboarding_sessions()
            
            # Verify logging occurred
            # Should log info about abandoned sessions
            info_calls = [call for call in mock_logger.info.call_args_list]
            assert len(info_calls) >= 1
            
            # Check that at least one log mentions abandoned sessions
            log_messages = [str(call) for call in info_calls]
            assert any('abandoned' in msg.lower() for msg in log_messages)
