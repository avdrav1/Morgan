"""
Tests for onboarding command handling (help, cancel, stop, restart).

Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5
"""

import pytest
from uuid import uuid4
from datetime import datetime

from app.services.onboarding_service import OnboardingService
from app.models.onboarding_session import OnboardingSession, OnboardingState
from app.models.user import User


@pytest.mark.asyncio
async def test_is_command_recognizes_commands(db_session):
    """Test that is_command correctly identifies command messages."""
    service = OnboardingService(db_session)
    
    # Test valid commands
    assert service.is_command("help") is True
    assert service.is_command("HELP") is True
    assert service.is_command("  help  ") is True
    assert service.is_command("cancel") is True
    assert service.is_command("stop") is True
    assert service.is_command("restart") is True
    
    # Test non-commands
    assert service.is_command("hello") is False
    assert service.is_command("help me with this") is False
    assert service.is_command("I want to cancel my subscription") is False


@pytest.mark.asyncio
async def test_help_command_provides_contextual_help(db_session):
    """Test that help command provides contextual help based on current state."""
    # Create user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Create session in COLLECT_PROJECT_NAME state
    session = await service.start_onboarding(user.id, user.discord_user_id)
    await service.process_message(user.id, "test", OnboardingState.COLLECT_PROJECT_NAME)
    
    # Get help
    response = await service.handle_command(user.id, "help")
    
    # Should contain base commands
    assert "help" in response.lower()
    assert "cancel" in response.lower() or "stop" in response.lower()
    assert "restart" in response.lower()
    
    # Should contain contextual help for current state
    assert "project name" in response.lower()


@pytest.mark.asyncio
async def test_cancel_command_pauses_onboarding(db_session):
    """Test that cancel/stop command pauses onboarding session."""
    # Create user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Create session and progress to COLLECT_PROJECT_NAME
    session = await service.start_onboarding(user.id, user.discord_user_id)
    await service.process_message(user.id, "My Project", OnboardingState.COLLECT_PROJECT_NAME)
    
    # Cancel onboarding
    response = await service.handle_command(user.id, "cancel")
    
    # Check response
    assert "paused" in response.lower()
    assert "resume" in response.lower()
    
    # Verify session is paused
    updated_session = await service.get_session(user.id)
    assert updated_session.current_state == OnboardingState.PAUSED


@pytest.mark.asyncio
async def test_stop_command_pauses_onboarding(db_session):
    """Test that stop command also pauses onboarding session."""
    # Create user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Create session
    session = await service.start_onboarding(user.id, user.discord_user_id)
    
    # Stop onboarding
    response = await service.handle_command(user.id, "stop")
    
    # Check response
    assert "paused" in response.lower()
    
    # Verify session is paused
    updated_session = await service.get_session(user.id)
    assert updated_session.current_state == OnboardingState.PAUSED


@pytest.mark.asyncio
async def test_restart_command_clears_data(db_session):
    """Test that restart command clears collected data and resets to WELCOME."""
    # Create user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Create session and add some data
    session = await service.start_onboarding(user.id, user.discord_user_id)
    await service.process_message(user.id, "My Project", OnboardingState.COLLECT_PROJECT_NAME)
    await service.update_session_data(user.id, project_name="My Project")
    
    # Restart onboarding
    response = await service.handle_command(user.id, "restart")
    
    # Check response
    assert "start" in response.lower() or "fresh" in response.lower()
    assert "project" in response.lower()
    
    # Verify session is reset
    updated_session = await service.get_session(user.id)
    assert updated_session.current_state == OnboardingState.WELCOME
    assert updated_session.project_name is None


@pytest.mark.asyncio
async def test_commands_case_insensitive(db_session):
    """Test that commands work regardless of case."""
    # Create user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Create session
    session = await service.start_onboarding(user.id, user.discord_user_id)
    
    # Test different cases
    response_lower = await service.handle_command(user.id, "help")
    response_upper = await service.handle_command(user.id, "HELP")
    response_mixed = await service.handle_command(user.id, "HeLp")
    
    # All should work and contain help information
    assert "help" in response_lower.lower()
    assert "help" in response_upper.lower()
    assert "help" in response_mixed.lower()


@pytest.mark.asyncio
async def test_help_command_different_states(db_session):
    """Test that help command provides different contextual help for different states."""
    # Create user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Test help in WELCOME state
    session = await service.start_onboarding(user.id, user.discord_user_id)
    help_welcome = await service.handle_command(user.id, "help")
    assert "getting started" in help_welcome.lower() or "project" in help_welcome.lower()
    
    # Move to COLLECT_GOAL state
    await service.process_message(user.id, "My Project", OnboardingState.COLLECT_PROJECT_NAME)
    await service.update_session_data(user.id, project_name="My Project")
    await service.process_message(user.id, "test", OnboardingState.COLLECT_GOAL)
    
    help_goal = await service.handle_command(user.id, "help")
    assert "goal" in help_goal.lower()
    
    # Help messages should be different
    assert help_welcome != help_goal


@pytest.mark.asyncio
async def test_unknown_command_returns_helpful_message(db_session):
    """Test that unknown commands return a helpful message."""
    # Create user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Create session
    session = await service.start_onboarding(user.id, user.discord_user_id)
    
    # Try an unknown command (this won't be detected by is_command, but test the handler)
    # We need to manually call handle_command with an invalid command
    response = await service.handle_command(user.id, "invalid_command")
    
    # Should provide helpful message about available commands
    assert "help" in response.lower()
    assert "cancel" in response.lower() or "stop" in response.lower()
    assert "restart" in response.lower()


@pytest.mark.asyncio
async def test_cancel_preserves_data_for_resume(db_session):
    """Test that cancelling preserves collected data for later resumption."""
    # Create user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    # Create session and add data
    session = await service.start_onboarding(user.id, user.discord_user_id)
    await service.process_message(user.id, "My Project", OnboardingState.COLLECT_PROJECT_NAME)
    await service.update_session_data(user.id, project_name="My Project")
    await service.process_message(user.id, "Build something great", OnboardingState.COLLECT_GOAL)
    await service.update_session_data(user.id, project_goal="Build something great")
    
    # Cancel
    await service.handle_command(user.id, "cancel")
    
    # Verify data is preserved
    updated_session = await service.get_session(user.id)
    assert updated_session.project_name == "My Project"
    assert updated_session.project_goal == "Build something great"
    assert updated_session.current_state == OnboardingState.PAUSED
