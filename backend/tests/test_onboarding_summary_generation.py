"""
Tests for onboarding completion summary generation.

This module tests the generate_completion_summary method that creates
a comprehensive summary with project plan for users completing onboarding.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock

from app.services.onboarding_service import OnboardingService
from app.models.onboarding_session import OnboardingSession, OnboardingState
from app.models.user import User
from app.models.project import Project


@pytest.mark.asyncio
async def test_generate_completion_summary_success(db_session):
    """Test successful generation of completion summary with project plan."""
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
    
    # Create an onboarding session with complete data
    session = OnboardingSession(
        id=uuid4(),
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.CONFIRM_DETAILS,
        project_name="Build a Mobile App",
        project_goal="Create a fitness tracking app for iOS and Android",
        deadline=datetime.utcnow() + timedelta(days=90),
        checkin_frequency="every 2-3 days",
        preferred_tone="supportive",
        conversation_history=[],
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow()
    )
    db_session.add(session)
    db_session.commit()
    
    # Mock the LLM service decompose_project method
    mock_tasks = [
        {
            "title": "Set up development environment",
            "description": "Install Xcode, Android Studio, and React Native",
            "estimated_duration_hours": 4,
            "order": 1
        },
        {
            "title": "Design app wireframes",
            "description": "Create mockups for all main screens",
            "estimated_duration_hours": 8,
            "order": 2
        },
        {
            "title": "Implement user authentication",
            "description": "Set up login and registration flows",
            "estimated_duration_hours": 12,
            "order": 3
        },
        {
            "title": "Build workout tracking feature",
            "description": "Create UI and logic for tracking exercises",
            "estimated_duration_hours": 16,
            "order": 4
        },
        {
            "title": "Add data visualization",
            "description": "Create charts for progress tracking",
            "estimated_duration_hours": 10,
            "order": 5
        }
    ]
    
    with patch('app.services.onboarding_service.llm_service') as mock_llm:
        mock_llm.decompose_project = AsyncMock(return_value=mock_tasks)
        
        # Create service and generate summary
        service = OnboardingService(db_session)
        summary = await service.generate_completion_summary(user.id)
        
        # Verify the summary contains expected elements
        assert "Build a Mobile App" in summary
        assert "Create a fitness tracking app for iOS and Android" in summary
        assert "supportive" in summary
        assert "every 2-3 days" in summary
        assert "5 tasks" in summary
        assert "50 hours" in summary or "50h" in summary
        
        # Verify all tasks are included
        assert "Set up development environment" in summary
        assert "Design app wireframes" in summary
        assert "Implement user authentication" in summary
        assert "Build workout tracking feature" in summary
        assert "Add data visualization" in summary
        
        # Verify task details are included
        assert "4h" in summary  # First task duration
        assert "Install Xcode, Android Studio, and React Native" in summary
        
        # Verify deadline is formatted
        assert session.deadline.strftime('%B %d, %Y') in summary
        
        # Verify LLM was called with correct parameters
        mock_llm.decompose_project.assert_called_once()
        call_args = mock_llm.decompose_project.call_args
        assert call_args[0][0].id == user.id  # User object
        temp_project = call_args[0][1]  # Project object
        assert temp_project.title == "Build a Mobile App"
        assert temp_project.goal == "Create a fitness tracking app for iOS and Android"


@pytest.mark.asyncio
async def test_generate_completion_summary_no_deadline(db_session):
    """Test summary generation when no deadline is set."""
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
    
    # Create session without deadline
    session = OnboardingSession(
        id=uuid4(),
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.CONFIRM_DETAILS,
        project_name="Learn Python",
        project_goal="Master Python programming fundamentals",
        deadline=None,  # No deadline
        checkin_frequency="daily",
        preferred_tone="direct",
        conversation_history=[],
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow()
    )
    db_session.add(session)
    db_session.commit()
    
    # Mock LLM service
    mock_tasks = [
        {"title": "Task 1", "description": "Desc 1", "estimated_duration_hours": 5, "order": 1},
        {"title": "Task 2", "description": "Desc 2", "estimated_duration_hours": 5, "order": 2},
        {"title": "Task 3", "description": "Desc 3", "estimated_duration_hours": 5, "order": 3},
        {"title": "Task 4", "description": "Desc 4", "estimated_duration_hours": 5, "order": 4},
        {"title": "Task 5", "description": "Desc 5", "estimated_duration_hours": 5, "order": 5}
    ]
    
    with patch('app.services.onboarding_service.llm_service') as mock_llm:
        mock_llm.decompose_project = AsyncMock(return_value=mock_tasks)
        
        service = OnboardingService(db_session)
        summary = await service.generate_completion_summary(user.id)
        
        # Verify summary doesn't contain deadline section
        assert "Target Completion:" not in summary
        
        # Verify other elements are present
        assert "Learn Python" in summary
        assert "direct" in summary
        assert "daily" in summary


@pytest.mark.asyncio
async def test_generate_completion_summary_llm_failure_fallback(db_session):
    """Test that summary generation falls back gracefully when LLM fails."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create session
    session = OnboardingSession(
        id=uuid4(),
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.CONFIRM_DETAILS,
        project_name="Write a Book",
        project_goal="Complete a 50,000 word novel",
        deadline=datetime.utcnow() + timedelta(days=180),
        checkin_frequency="weekly",
        preferred_tone="casual",
        conversation_history=[],
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow()
    )
    db_session.add(session)
    db_session.commit()
    
    # Mock LLM service to raise an exception
    with patch('app.services.onboarding_service.llm_service') as mock_llm:
        mock_llm.decompose_project = AsyncMock(side_effect=Exception("LLM API error"))
        
        service = OnboardingService(db_session)
        summary = await service.generate_completion_summary(user.id)
        
        # Verify fallback summary is generated
        assert "Write a Book" in summary
        assert "Complete a 50,000 word novel" in summary
        assert "casual" in summary
        assert "weekly" in summary
        
        # Verify it doesn't contain task breakdown (since LLM failed)
        assert "tasks" not in summary.lower() or "Action Plan" not in summary


@pytest.mark.asyncio
async def test_generate_completion_summary_missing_session(db_session):
    """Test that appropriate error is raised when session not found."""
    service = OnboardingService(db_session)
    
    with pytest.raises(ValueError, match="No onboarding session found"):
        await service.generate_completion_summary(uuid4())


@pytest.mark.asyncio
async def test_generate_completion_summary_missing_required_data(db_session):
    """Test that error is raised when required data is missing."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create session with missing project_goal
    session = OnboardingSession(
        id=uuid4(),
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.COLLECT_GOAL,
        project_name="Test Project",
        project_goal=None,  # Missing!
        conversation_history=[],
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow()
    )
    db_session.add(session)
    db_session.commit()
    
    service = OnboardingService(db_session)
    
    with pytest.raises(ValueError, match="Project name and goal are required"):
        await service.generate_completion_summary(user.id)


@pytest.mark.asyncio
async def test_format_completion_summary_with_various_task_counts(db_session):
    """Test summary formatting with different numbers of tasks."""
    # Create a user
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create session
    session = OnboardingSession(
        id=uuid4(),
        user_id=user.id,
        discord_id="123456789",
        current_state=OnboardingState.CONFIRM_DETAILS,
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
    
    service = OnboardingService(db_session)
    
    # Test with 5 tasks (minimum)
    tasks_5 = [
        {"title": f"Task {i}", "description": f"Desc {i}", "estimated_duration_hours": 2, "order": i}
        for i in range(1, 6)
    ]
    
    with patch('app.services.onboarding_service.llm_service') as mock_llm:
        mock_llm.decompose_project = AsyncMock(return_value=tasks_5)
        summary = await service.generate_completion_summary(user.id)
        assert "5 tasks" in summary
        assert "10 hours" in summary or "10h" in summary
    
    # Test with 20 tasks (maximum)
    tasks_20 = [
        {"title": f"Task {i}", "description": f"Desc {i}", "estimated_duration_hours": 3, "order": i}
        for i in range(1, 21)
    ]
    
    with patch('app.services.onboarding_service.llm_service') as mock_llm:
        mock_llm.decompose_project = AsyncMock(return_value=tasks_20)
        summary = await service.generate_completion_summary(user.id)
        assert "20 tasks" in summary
        assert "60 hours" in summary or "60h" in summary
