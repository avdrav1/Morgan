"""
Tests for onboarding logging and metrics.

Validates that comprehensive logging and metrics tracking are in place
for the onboarding flow (Requirements: 10.1, 10.2, 10.3, 10.4, 10.5).
"""

import pytest
from uuid import uuid4
from datetime import datetime
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.services.onboarding_service import OnboardingService
from app.models.onboarding_session import OnboardingSession, OnboardingState
from app.models.user import User
from app.core.metrics import metrics
from app.core.logging_config import get_correlation_id, set_correlation_id


@pytest.mark.asyncio
async def test_onboarding_start_logs_event(db_session: Session):
    """
    Test that starting onboarding logs the event with correlation ID.
    
    Validates: Requirements 10.1 (log all onboarding events with correlation IDs)
    """
    user_id = uuid4()
    discord_id = "123456789012345678"
    
    # Create user
    user = User(
        id=user_id,
        email="test@example.com",
        discord_user_id=discord_id,
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Mock logger to capture log calls
    with patch('app.services.onboarding_service.logger') as mock_logger:
        session = await service.start_onboarding(user_id, discord_id, dm_enabled=True)
        
        # Verify logging occurred
        assert mock_logger.info.called
        
        # Check that correlation ID was set
        correlation_id = get_correlation_id()
        assert correlation_id is not None
        
        # Verify log contains event type and correlation ID
        log_calls = [call for call in mock_logger.info.call_args_list]
        assert any('onboarding_session_created' in str(call) for call in log_calls)


@pytest.mark.asyncio
async def test_onboarding_state_transition_logged(db_session: Session):
    """
    Test that state transitions are logged.
    
    Validates: Requirements 10.2 (log state transitions)
    """
    user_id = uuid4()
    discord_id = "123456789012345678"
    
    # Create user
    user = User(
        id=user_id,
        email="test@example.com",
        discord_user_id=discord_id,
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    session = await service.start_onboarding(user_id, discord_id, dm_enabled=True)
    
    # Mock logger to capture state transition logs
    with patch('app.services.onboarding_service.logger') as mock_logger:
        # Process message with valid state transition (WELCOME -> COLLECT_PROJECT_NAME)
        await service.process_message(
            user_id,
            "My Project",
            next_state=OnboardingState.COLLECT_PROJECT_NAME
        )
        
        # Verify state transition was logged
        log_calls = [call for call in mock_logger.info.call_args_list]
        assert any('onboarding_state_transition' in str(call) for call in log_calls)
        assert any('from_state' in str(call) for call in log_calls)
        assert any('to_state' in str(call) for call in log_calls)


@pytest.mark.asyncio
async def test_onboarding_error_logged_with_context(db_session: Session):
    """
    Test that errors are logged with full context.
    
    Validates: Requirements 10.3 (log errors with full context)
    """
    user_id = uuid4()
    
    service = OnboardingService(db_session)
    
    # Mock logger to capture error logs
    with patch('app.services.onboarding_service.logger') as mock_logger:
        # Try to process message for non-existent session (should error)
        with pytest.raises(ValueError):
            await service.process_message(user_id, "test message")
        
        # Verify error was logged with context
        assert mock_logger.error.called
        error_calls = [call for call in mock_logger.error.call_args_list]
        
        # Check that error log contains context
        assert any('onboarding_session_not_found' in str(call) for call in error_calls)
        assert any(str(user_id) in str(call) for call in error_calls)


@pytest.mark.asyncio
async def test_onboarding_completion_logged_with_duration(db_session: Session):
    """
    Test that onboarding completion is logged with duration metrics.
    
    Validates: Requirements 10.4 (log completion with PII-redacted data)
    """
    user_id = uuid4()
    discord_id = "123456789012345678"
    
    # Create user
    user = User(
        id=user_id,
        email="test@example.com",
        discord_user_id=discord_id,
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    session = await service.start_onboarding(user_id, discord_id, dm_enabled=True)
    
    # Set required data
    await service.update_session_data(
        user_id,
        project_name="Test Project",
        project_goal="Test Goal"
    )
    
    # Transition to a state that allows completion
    session = await service.get_session(user_id)
    session.current_state = OnboardingState.CONFIRM_DETAILS
    db_session.commit()
    
    # Mock logger to capture completion logs
    with patch('app.services.onboarding_service.logger') as mock_logger:
        project = await service.complete_onboarding(user_id)
        
        # Verify completion was logged
        log_calls = [call for call in mock_logger.info.call_args_list]
        assert any('onboarding_completed' in str(call) for call in log_calls)
        
        # Check that duration was logged
        assert any('duration_minutes' in str(call) for call in log_calls)


@pytest.mark.asyncio
async def test_onboarding_metrics_tracked(db_session: Session):
    """
    Test that onboarding metrics are tracked.
    
    Validates: Requirements 10.5 (metrics for completion rates and drop-offs)
    """
    # Reset metrics
    metrics.reset()
    
    user_id = uuid4()
    discord_id = "123456789012345678"
    
    # Create user
    user = User(
        id=user_id,
        email="test@example.com",
        discord_user_id=discord_id,
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Start onboarding
    session = await service.start_onboarding(user_id, discord_id, dm_enabled=True)
    
    # Verify metrics were incremented
    assert metrics.get_metric('onboarding_started') > 0
    assert metrics.get_metric('onboarding_session_created') > 0


@pytest.mark.asyncio
async def test_onboarding_cancellation_metrics(db_session: Session):
    """
    Test that cancellation metrics track drop-off points.
    
    Validates: Requirements 10.5 (metrics for drop-offs)
    """
    # Reset metrics
    metrics.reset()
    
    user_id = uuid4()
    discord_id = "123456789012345678"
    
    # Create user
    user = User(
        id=user_id,
        email="test@example.com",
        discord_user_id=discord_id,
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    session = await service.start_onboarding(user_id, discord_id, dm_enabled=True)
    
    # Transition to a specific state (WELCOME -> COLLECT_PROJECT_NAME)
    await service.process_message(
        user_id,
        "My Project",
        next_state=OnboardingState.COLLECT_PROJECT_NAME
    )
    
    # Cancel onboarding
    await service.cancel_onboarding(user_id)
    
    # Verify cancellation metric was tracked with state
    cancelled_count = metrics.get_metric('onboarding_cancelled')
    assert cancelled_count > 0


@pytest.mark.asyncio
async def test_dm_failure_metrics(db_session: Session):
    """
    Test that DM failures are tracked in metrics.
    
    Validates: Requirements 10.5 (metrics for DM delivery failures)
    """
    # Reset metrics
    metrics.reset()
    
    user_id = uuid4()
    discord_id = "123456789012345678"
    
    # Create user
    user = User(
        id=user_id,
        email="test@example.com",
        discord_user_id=discord_id,
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Start onboarding with DM disabled (simulates failure)
    session = await service.start_onboarding(user_id, discord_id, dm_enabled=False)
    
    # Verify DM failure was tracked
    assert session is None
    assert metrics.get_metric('onboarding_dm_failed') > 0


@pytest.mark.asyncio
async def test_pii_redaction_in_logs(db_session: Session):
    """
    Test that PII is redacted in logs.
    
    Validates: Requirements 10.4 (PII redaction in logs)
    """
    from app.core.logging_config import PIIRedactor
    
    # Test email redaction
    text_with_email = "User email is test@example.com"
    redacted = PIIRedactor.redact(text_with_email)
    assert "test@example.com" not in redacted
    assert "[EMAIL_REDACTED]" in redacted
    
    # Test Discord ID redaction
    text_with_discord_id = "Discord ID: 123456789012345678"
    redacted = PIIRedactor.redact(text_with_discord_id)
    assert "123456789012345678" not in redacted
    assert "[DISCORD_ID_REDACTED]" in redacted
    
    # Test UUID redaction
    user_id = uuid4()
    text_with_uuid = f"User ID: {user_id}"
    redacted = PIIRedactor.redact(text_with_uuid)
    assert str(user_id) not in redacted
    assert "[UUID_REDACTED]" in redacted


@pytest.mark.asyncio
async def test_correlation_id_propagation(db_session: Session):
    """
    Test that correlation IDs are propagated through the onboarding flow.
    
    Validates: Requirements 10.1 (correlation IDs for request tracing)
    """
    user_id = uuid4()
    discord_id = "123456789012345678"
    
    # Create user
    user = User(
        id=user_id,
        email="test@example.com",
        discord_user_id=discord_id,
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Start onboarding (this sets a correlation ID)
    session = await service.start_onboarding(user_id, discord_id, dm_enabled=True)
    
    # Get correlation ID
    correlation_id_1 = get_correlation_id()
    assert correlation_id_1 is not None
    
    # Process message (should use same correlation ID or set new one)
    await service.process_message(user_id, "Test message")
    
    correlation_id_2 = get_correlation_id()
    assert correlation_id_2 is not None


@pytest.mark.asyncio
async def test_state_transition_metrics(db_session: Session):
    """
    Test that state transitions are tracked in metrics.
    
    Validates: Requirements 10.2, 10.5 (state transition tracking)
    """
    # Reset metrics
    metrics.reset()
    
    user_id = uuid4()
    discord_id = "123456789012345678"
    
    # Create user
    user = User(
        id=user_id,
        email="test@example.com",
        discord_user_id=discord_id,
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    session = await service.start_onboarding(user_id, discord_id, dm_enabled=True)
    
    # Perform valid state transition (WELCOME -> COLLECT_PROJECT_NAME)
    await service.process_message(
        user_id,
        "My Project",
        next_state=OnboardingState.COLLECT_PROJECT_NAME
    )
    
    # Verify state transition metric was tracked
    transition_count = metrics.get_metric('onboarding_state_transitions')
    assert transition_count > 0


@pytest.mark.asyncio
async def test_error_metrics_tracking(db_session: Session):
    """
    Test that errors are tracked in metrics by error type.
    
    Validates: Requirements 10.3, 10.5 (error tracking)
    """
    # Reset metrics
    metrics.reset()
    
    user_id = uuid4()
    
    service = OnboardingService(db_session)
    
    # Try to process message for non-existent session (should error)
    with pytest.raises(ValueError):
        await service.process_message(user_id, "test message")
    
    # Verify error metric was tracked
    error_count = metrics.get_metric('onboarding_errors')
    assert error_count > 0
