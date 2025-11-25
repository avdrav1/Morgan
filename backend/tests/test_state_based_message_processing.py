"""
Tests for state-based message processing in onboarding.

These tests verify that the enhanced webhook message processing correctly:
- Parses user input based on current onboarding state
- Extracts relevant data (project name, goal, deadline, tone, frequency)
- Validates extracted data using input validators
- Updates session with extracted data
- Determines next state based on current state and input
- Transitions to next state
- Generates LLM response for next question
- Handles validation errors with clarifying questions

Validates: Requirements 2.1, 3.1, 3.2, 8.1, 8.2
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from app.services.onboarding_service import OnboardingService
from app.models.onboarding_session import OnboardingSession, OnboardingState
from app.models.user import User


@pytest.fixture
def test_user_for_state_processing(db_session):
    """Create a test user for state-based processing tests."""
    user = User(
        email="state_test@example.com",
        hashed_password="hashed_password",
        discord_user_id="987654321098765432",
        discord_username="statetest",
        is_new=True,
        preferred_tone="supportive",
        timezone="UTC"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_collect_project_name_valid(db_session, test_user_for_state_processing):
    """Test that valid project name is extracted and state transitions correctly."""
    service = OnboardingService(db_session)
    
    # Create session in COLLECT_PROJECT_NAME state
    session = OnboardingSession(
        user_id=test_user_for_state_processing.id,
        discord_id=test_user_for_state_processing.discord_user_id,
        current_state=OnboardingState.COLLECT_PROJECT_NAME,
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
        conversation_history=[]
    )
    db_session.add(session)
    db_session.commit()
    
    # Process a valid project name
    result = await service.process_message_with_state_logic(
        user_id=test_user_for_state_processing.id,
        message="Website Redesign"
    )
    
    # Verify validation passed
    assert result['validation_passed'] is True
    
    # Verify state transitioned to COLLECT_GOAL
    assert result['current_state'] == OnboardingState.COLLECT_GOAL.value
    
    # Verify project name was extracted and saved
    updated_session = await service.get_session(test_user_for_state_processing.id)
    assert updated_session.project_name == "Website Redesign"
    assert updated_session.current_state == OnboardingState.COLLECT_GOAL


@pytest.mark.asyncio
async def test_collect_project_name_invalid(db_session, test_user_for_state_processing):
    """Test that invalid project name triggers validation error."""
    service = OnboardingService(db_session)
    
    # Create session in COLLECT_PROJECT_NAME state
    session = OnboardingSession(
        user_id=test_user_for_state_processing.id,
        discord_id=test_user_for_state_processing.discord_user_id,
        current_state=OnboardingState.COLLECT_PROJECT_NAME,
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
        conversation_history=[]
    )
    db_session.add(session)
    db_session.commit()
    
    # Process an invalid project name (too short)
    result = await service.process_message_with_state_logic(
        user_id=test_user_for_state_processing.id,
        message="A"
    )
    
    # Verify validation failed
    assert result['validation_passed'] is False
    
    # Verify state stayed in COLLECT_PROJECT_NAME
    assert result['current_state'] == OnboardingState.COLLECT_PROJECT_NAME.value
    
    # Verify error message is present
    assert 'at least 2 characters' in result['reply'].lower()
    
    # Verify project name was NOT saved
    updated_session = await service.get_session(test_user_for_state_processing.id)
    assert updated_session.project_name is None


@pytest.mark.asyncio
async def test_collect_goal_valid(db_session, test_user_for_state_processing):
    """Test that valid project goal is extracted and state transitions correctly."""
    service = OnboardingService(db_session)
    
    # Create session in COLLECT_GOAL state with project name already set
    session = OnboardingSession(
        user_id=test_user_for_state_processing.id,
        discord_id=test_user_for_state_processing.discord_user_id,
        current_state=OnboardingState.COLLECT_GOAL,
        project_name="Website Redesign",
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
        conversation_history=[]
    )
    db_session.add(session)
    db_session.commit()
    
    # Process a valid project goal
    result = await service.process_message_with_state_logic(
        user_id=test_user_for_state_processing.id,
        message="Create a modern, responsive website for my business"
    )
    
    # Verify validation passed
    assert result['validation_passed'] is True
    
    # Verify state transitioned to COLLECT_DEADLINE
    assert result['current_state'] == OnboardingState.COLLECT_DEADLINE.value
    
    # Verify project goal was extracted and saved
    updated_session = await service.get_session(test_user_for_state_processing.id)
    assert updated_session.project_goal == "Create a modern, responsive website for my business"
    assert updated_session.current_state == OnboardingState.COLLECT_DEADLINE


@pytest.mark.asyncio
async def test_collect_deadline_valid(db_session, test_user_for_state_processing):
    """Test that valid deadline is extracted and state transitions correctly."""
    service = OnboardingService(db_session)
    
    # Create session in COLLECT_DEADLINE state
    session = OnboardingSession(
        user_id=test_user_for_state_processing.id,
        discord_id=test_user_for_state_processing.discord_user_id,
        current_state=OnboardingState.COLLECT_DEADLINE,
        project_name="Website Redesign",
        project_goal="Create a modern website",
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
        conversation_history=[]
    )
    db_session.add(session)
    db_session.commit()
    
    # Process a valid deadline (future date)
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    result = await service.process_message_with_state_logic(
        user_id=test_user_for_state_processing.id,
        message=future_date
    )
    
    # Verify validation passed
    assert result['validation_passed'] is True
    
    # Verify state transitioned to CONFIRM_DEADLINE (as required by state machine)
    assert result['current_state'] == OnboardingState.CONFIRM_DEADLINE.value
    
    # Verify deadline was extracted and saved
    updated_session = await service.get_session(test_user_for_state_processing.id)
    assert updated_session.deadline is not None
    assert updated_session.current_state == OnboardingState.CONFIRM_DEADLINE


@pytest.mark.asyncio
async def test_collect_deadline_past_date(db_session, test_user_for_state_processing):
    """Test that past deadline triggers validation error."""
    service = OnboardingService(db_session)
    
    # Create session in COLLECT_DEADLINE state
    session = OnboardingSession(
        user_id=test_user_for_state_processing.id,
        discord_id=test_user_for_state_processing.discord_user_id,
        current_state=OnboardingState.COLLECT_DEADLINE,
        project_name="Website Redesign",
        project_goal="Create a modern website",
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
        conversation_history=[]
    )
    db_session.add(session)
    db_session.commit()
    
    # Process a past deadline
    past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    result = await service.process_message_with_state_logic(
        user_id=test_user_for_state_processing.id,
        message=past_date
    )
    
    # Verify validation failed
    assert result['validation_passed'] is False
    
    # Verify state stayed in COLLECT_DEADLINE
    assert result['current_state'] == OnboardingState.COLLECT_DEADLINE.value
    
    # Verify error message mentions past date
    assert 'past' in result['reply'].lower()
    
    # Verify deadline was NOT saved
    updated_session = await service.get_session(test_user_for_state_processing.id)
    assert updated_session.deadline is None


@pytest.mark.asyncio
async def test_collect_tone_valid(db_session, test_user_for_state_processing):
    """Test that valid tone preference is extracted and state transitions correctly."""
    service = OnboardingService(db_session)
    
    # Create session in COLLECT_TONE state
    session = OnboardingSession(
        user_id=test_user_for_state_processing.id,
        discord_id=test_user_for_state_processing.discord_user_id,
        current_state=OnboardingState.COLLECT_TONE,
        project_name="Website Redesign",
        project_goal="Create a modern website",
        deadline=datetime.now() + timedelta(days=30),
        checkin_frequency="daily",
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
        conversation_history=[]
    )
    db_session.add(session)
    db_session.commit()
    
    # Process a valid tone preference
    result = await service.process_message_with_state_logic(
        user_id=test_user_for_state_processing.id,
        message="supportive"
    )
    
    # Verify validation passed
    assert result['validation_passed'] is True
    
    # Verify state transitioned to CONFIRM_DETAILS
    assert result['current_state'] == OnboardingState.CONFIRM_DETAILS.value
    
    # Verify tone was extracted and saved
    updated_session = await service.get_session(test_user_for_state_processing.id)
    assert updated_session.preferred_tone == "supportive"
    assert updated_session.current_state == OnboardingState.CONFIRM_DETAILS


@pytest.mark.asyncio
async def test_collect_checkin_frequency_valid(db_session, test_user_for_state_processing):
    """Test that valid check-in frequency is extracted and state transitions correctly."""
    service = OnboardingService(db_session)
    
    # Create session in COLLECT_CHECKIN_FREQUENCY state
    session = OnboardingSession(
        user_id=test_user_for_state_processing.id,
        discord_id=test_user_for_state_processing.discord_user_id,
        current_state=OnboardingState.COLLECT_CHECKIN_FREQUENCY,
        project_name="Website Redesign",
        project_goal="Create a modern website",
        deadline=datetime.now() + timedelta(days=30),
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
        conversation_history=[]
    )
    db_session.add(session)
    db_session.commit()
    
    # Process a valid check-in frequency
    result = await service.process_message_with_state_logic(
        user_id=test_user_for_state_processing.id,
        message="daily"
    )
    
    # Verify validation passed
    assert result['validation_passed'] is True
    
    # Verify state transitioned to COLLECT_TONE
    assert result['current_state'] == OnboardingState.COLLECT_TONE.value
    
    # Verify frequency was extracted and saved
    updated_session = await service.get_session(test_user_for_state_processing.id)
    assert updated_session.checkin_frequency == "daily"
    assert updated_session.current_state == OnboardingState.COLLECT_TONE


@pytest.mark.asyncio
async def test_welcome_state_accepts_project_name(db_session, test_user_for_state_processing):
    """Test that WELCOME state accepts project name and transitions to COLLECT_GOAL."""
    service = OnboardingService(db_session)
    
    # Create session in WELCOME state
    session = OnboardingSession(
        user_id=test_user_for_state_processing.id,
        discord_id=test_user_for_state_processing.discord_user_id,
        current_state=OnboardingState.WELCOME,
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
        conversation_history=[]
    )
    db_session.add(session)
    db_session.commit()
    
    # Process a project name in WELCOME state
    result = await service.process_message_with_state_logic(
        user_id=test_user_for_state_processing.id,
        message="My Awesome Project"
    )
    
    # Verify validation passed
    assert result['validation_passed'] is True
    
    # Verify state transitioned to COLLECT_GOAL
    assert result['current_state'] == OnboardingState.COLLECT_GOAL.value
    
    # Verify project name was extracted and saved
    updated_session = await service.get_session(test_user_for_state_processing.id)
    assert updated_session.project_name == "My Awesome Project"
    assert updated_session.current_state == OnboardingState.COLLECT_GOAL
