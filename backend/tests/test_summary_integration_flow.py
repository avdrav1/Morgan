"""
Tests for integration of summary generation into completion flow.

This module tests that the summary is generated and shown to the user
before creating the project, and that user confirmation is required.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import patch, AsyncMock

from app.services.onboarding_service import OnboardingService
from app.models.onboarding_session import OnboardingSession, OnboardingState
from app.models.user import User
from app.models.project import Project


@pytest.mark.asyncio
async def test_confirm_details_generates_summary(db_session):
    """Test that confirming details generates and shows summary."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True,
        preferred_tone="supportive"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create an onboarding session at CONFIRM_DETAILS state
    session = OnboardingSession(
        id=uuid4(),
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.CONFIRM_DETAILS,
        project_name="Build a Mobile App",
        project_goal="Create a fitness tracking app",
        deadline=datetime.utcnow() + timedelta(days=90),
        checkin_frequency="every 2-3 days",
        preferred_tone="supportive",
        conversation_history=[],
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow()
    )
    db_session.add(session)
    db_session.commit()
    
    # Mock the LLM service
    mock_tasks = [
        {"title": "Task 1", "description": "Desc 1", "estimated_duration_hours": 5, "order": 1},
        {"title": "Task 2", "description": "Desc 2", "estimated_duration_hours": 5, "order": 2},
        {"title": "Task 3", "description": "Desc 3", "estimated_duration_hours": 5, "order": 3},
        {"title": "Task 4", "description": "Desc 4", "estimated_duration_hours": 5, "order": 4},
        {"title": "Task 5", "description": "Desc 5", "estimated_duration_hours": 5, "order": 5}
    ]
    
    with patch('app.services.onboarding_service.llm_service') as mock_llm:
        mock_llm.decompose_project = AsyncMock(return_value=mock_tasks)
        
        # Create service and process confirmation
        service = OnboardingService(db_session)
        result = await service.process_message_with_state_logic(user.id, "yes")
        
        # Verify summary was generated and returned
        assert result['validation_passed'] is True
        assert result['current_state'] == OnboardingState.SHOW_SUMMARY.value
        assert "Build a Mobile App" in result['reply']
        assert "5 tasks" in result['reply']
        assert "25 hours" in result['reply'] or "25h" in result['reply']
        
        # Verify session transitioned to SHOW_SUMMARY
        db_session.refresh(session)
        assert session.current_state == OnboardingState.SHOW_SUMMARY
        
        # Verify project was NOT created yet
        projects = db_session.query(Project).filter(Project.user_id == user.id).all()
        assert len(projects) == 0


@pytest.mark.asyncio
async def test_show_summary_confirmation_creates_project(db_session):
    """Test that confirming summary creates the project."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True,
        preferred_tone="supportive"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create an onboarding session at SHOW_SUMMARY state
    session = OnboardingSession(
        id=uuid4(),
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.SHOW_SUMMARY,
        project_name="Build a Mobile App",
        project_goal="Create a fitness tracking app",
        deadline=datetime.utcnow() + timedelta(days=90),
        checkin_frequency="every 2-3 days",
        preferred_tone="supportive",
        conversation_history=[],
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow()
    )
    db_session.add(session)
    db_session.commit()
    
    # Create service and process confirmation
    service = OnboardingService(db_session)
    result = await service.process_message_with_state_logic(user.id, "yes")
    
    # Verify project was created
    assert result['validation_passed'] is True
    assert result['current_state'] == OnboardingState.COMPLETED.value
    assert "Awesome!" in result['reply']
    assert "Build a Mobile App" in result['reply']
    
    # Verify session is completed
    db_session.refresh(session)
    assert session.current_state == OnboardingState.COMPLETED
    assert session.completed_at is not None
    
    # Verify project exists
    projects = db_session.query(Project).filter(Project.user_id == user.id).all()
    assert len(projects) == 1
    assert projects[0].title == "Build a Mobile App"
    
    # Verify user is marked as not new
    db_session.refresh(user)
    assert user.is_new is False


@pytest.mark.asyncio
async def test_show_summary_rejection_goes_back(db_session):
    """Test that rejecting summary goes back to CONFIRM_DETAILS."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create an onboarding session at SHOW_SUMMARY state
    session = OnboardingSession(
        id=uuid4(),
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.SHOW_SUMMARY,
        project_name="Test Project",
        project_goal="Test goal",
        checkin_frequency="daily",
        preferred_tone="supportive",
        conversation_history=[],
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow()
    )
    db_session.add(session)
    db_session.commit()
    
    # Create service and process rejection
    service = OnboardingService(db_session)
    result = await service.process_message_with_state_logic(user.id, "no")
    
    # Verify we went back to CONFIRM_DETAILS
    assert result['validation_passed'] is False
    assert "make" in result['reply'].lower() and "change" in result['reply'].lower()
    
    # Verify no project was created
    projects = db_session.query(Project).filter(Project.user_id == user.id).all()
    assert len(projects) == 0


@pytest.mark.asyncio
async def test_show_summary_ambiguous_response(db_session):
    """Test that ambiguous response at SHOW_SUMMARY asks for clarification."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create an onboarding session at SHOW_SUMMARY state
    session = OnboardingSession(
        id=uuid4(),
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.SHOW_SUMMARY,
        project_name="Test Project",
        project_goal="Test goal",
        conversation_history=[],
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow()
    )
    db_session.add(session)
    db_session.commit()
    
    # Create service and process ambiguous response
    service = OnboardingService(db_session)
    result = await service.process_message_with_state_logic(user.id, "maybe")
    
    # Verify we stay in SHOW_SUMMARY and ask for clarification
    assert result['validation_passed'] is False
    assert "not sure" in result['reply'].lower() or "clarif" in result['reply'].lower()
    
    # Verify session stayed in SHOW_SUMMARY
    db_session.refresh(session)
    assert session.current_state == OnboardingState.SHOW_SUMMARY
    
    # Verify no project was created
    projects = db_session.query(Project).filter(Project.user_id == user.id).all()
    assert len(projects) == 0


@pytest.mark.asyncio
async def test_complete_flow_with_summary(db_session):
    """Test complete flow from CONFIRM_DETAILS through SHOW_SUMMARY to COMPLETED."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True,
        preferred_tone="direct"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create an onboarding session at CONFIRM_DETAILS state
    session = OnboardingSession(
        id=uuid4(),
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.CONFIRM_DETAILS,
        project_name="Learn Python",
        project_goal="Master Python fundamentals",
        deadline=datetime.utcnow() + timedelta(days=60),
        checkin_frequency="daily",
        preferred_tone="direct",
        conversation_history=[],
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow()
    )
    db_session.add(session)
    db_session.commit()
    
    # Mock the LLM service
    mock_tasks = [
        {"title": "Learn basics", "description": "Variables and types", "estimated_duration_hours": 10, "order": 1},
        {"title": "Control flow", "description": "If/else and loops", "estimated_duration_hours": 8, "order": 2},
        {"title": "Functions", "description": "Define and use functions", "estimated_duration_hours": 12, "order": 3},
        {"title": "OOP", "description": "Classes and objects", "estimated_duration_hours": 15, "order": 4},
        {"title": "Projects", "description": "Build real projects", "estimated_duration_hours": 20, "order": 5}
    ]
    
    with patch('app.services.onboarding_service.llm_service') as mock_llm:
        mock_llm.decompose_project = AsyncMock(return_value=mock_tasks)
        
        service = OnboardingService(db_session)
        
        # Step 1: Confirm details - should generate summary
        result1 = await service.process_message_with_state_logic(user.id, "yes")
        
        assert result1['current_state'] == OnboardingState.SHOW_SUMMARY.value
        assert "Learn Python" in result1['reply']
        assert "5 tasks" in result1['reply']
        
        # Verify no project yet
        projects = db_session.query(Project).filter(Project.user_id == user.id).all()
        assert len(projects) == 0
        
        # Step 2: Confirm summary - should create project
        result2 = await service.process_message_with_state_logic(user.id, "ready")
        
        assert result2['current_state'] == OnboardingState.COMPLETED.value
        assert "Awesome!" in result2['reply']
        
        # Verify project was created
        projects = db_session.query(Project).filter(Project.user_id == user.id).all()
        assert len(projects) == 1
        assert projects[0].title == "Learn Python"
        
        # Verify user is marked as not new
        db_session.refresh(user)
        assert user.is_new is False


@pytest.mark.asyncio
async def test_summary_generation_failure_fallback(db_session):
    """Test that summary generation failure is handled gracefully."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create an onboarding session at CONFIRM_DETAILS state
    session = OnboardingSession(
        id=uuid4(),
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.CONFIRM_DETAILS,
        project_name="Test Project",
        project_goal="Test goal",
        conversation_history=[],
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow()
    )
    db_session.add(session)
    db_session.commit()
    
    # Mock the LLM service to raise an exception
    with patch('app.services.onboarding_service.llm_service') as mock_llm:
        mock_llm.decompose_project = AsyncMock(side_effect=Exception("LLM API error"))
        
        service = OnboardingService(db_session)
        result = await service.process_message_with_state_logic(user.id, "yes")
        
        # Should still show summary (fallback version without tasks)
        assert result['current_state'] == OnboardingState.SHOW_SUMMARY.value
        assert "Test Project" in result['reply']
        
        # Verify session transitioned to SHOW_SUMMARY
        db_session.refresh(session)
        assert session.current_state == OnboardingState.SHOW_SUMMARY
