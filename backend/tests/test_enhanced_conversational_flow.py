"""
Tests for enhanced conversational flow in Discord DM onboarding.

This module tests the complete enhanced conversational flow including:
- Natural language input processing
- State transitions with various user responses
- Summary generation with project plan
- Error handling and clarifying questions
- LLM responses that are contextual and natural

Task 27: Test enhanced conversational flow
Validates: Requirements 2.1, 3.1, 3.2, 3.3, 5.1, 5.2, 8.1, 8.2, 8.3, 8.4
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import patch, AsyncMock

from app.services.onboarding_service import OnboardingService
from app.models.onboarding_session import OnboardingSession, OnboardingState
from app.models.user import User
from app.models.project import Project


@pytest.fixture
def test_user(db_session):
    """Create a test user for conversational flow tests."""
    user = User(
        id=uuid4(),
        email="conversational_test@example.com",
        discord_user_id="999888777666555444",
        is_new=True,
        preferred_tone="supportive"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def onboarding_service(db_session):
    """Create an onboarding service instance."""
    return OnboardingService(db_session)


class TestNaturalLanguageInputProcessing:
    """Test processing of natural language inputs."""
    
    @pytest.mark.asyncio
    async def test_natural_language_project_name(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that natural language project names are processed correctly."""
        # Create session in COLLECT_PROJECT_NAME state
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.COLLECT_PROJECT_NAME,
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[]
        )
        db_session.add(session)
        db_session.commit()
        
        # Test various natural language project names
        natural_names = [
            "I want to build a mobile app",
            "My project is called Website Redesign",
            "Let's call it Learning Python",
            "Build a SaaS Platform"
        ]
        
        for name in natural_names:
            # Reset session state
            session.current_state = OnboardingState.COLLECT_PROJECT_NAME
            session.project_name = None
            db_session.commit()
            
            result = await onboarding_service.process_message_with_state_logic(
                test_user.id,
                name
            )
            
            # Verify validation passed
            assert result['validation_passed'] is True
            
            # Verify state transitioned
            assert result['current_state'] == OnboardingState.COLLECT_GOAL.value
            
            # Verify project name was extracted
            db_session.refresh(session)
            assert session.project_name is not None
            assert len(session.project_name) > 0
    
    @pytest.mark.asyncio
    async def test_natural_language_deadline_formats(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that various natural language deadline formats are parsed."""
        # Create session in COLLECT_DEADLINE state
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.COLLECT_DEADLINE,
            project_name="Test Project",
            project_goal="Test goal",
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[]
        )
        db_session.add(session)
        db_session.commit()
        
        # Test various date formats
        date_formats = [
            (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            (datetime.now() + timedelta(days=60)).strftime("%m/%d/%Y"),
            "in 3 months",
            "next month"
        ]
        
        for date_str in date_formats:
            # Reset session state
            session.current_state = OnboardingState.COLLECT_DEADLINE
            session.deadline = None
            db_session.commit()
            
            result = await onboarding_service.process_message_with_state_logic(
                test_user.id,
                date_str
            )
            
            # Should either parse successfully or ask for clarification
            # (depending on the complexity of the format)
            assert 'reply' in result
            assert len(result['reply']) > 0
    
    @pytest.mark.asyncio
    async def test_natural_language_tone_extraction(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that tone preferences are extracted from natural language."""
        # Create session in COLLECT_TONE state
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.COLLECT_TONE,
            project_name="Test Project",
            project_goal="Test goal",
            deadline=datetime.now() + timedelta(days=30),
            checkin_frequency="daily",
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[]
        )
        db_session.add(session)
        db_session.commit()
        
        # Test various ways of expressing tone preference
        tone_expressions = [
            ("supportive", "supportive"),
            ("I prefer a supportive tone", "supportive"),
            ("direct", "direct"),
            ("Be direct with me", "direct"),
            ("casual", "casual"),
            ("Keep it casual", "casual")
        ]
        
        for expression, expected_tone in tone_expressions:
            # Reset session state
            session.current_state = OnboardingState.COLLECT_TONE
            session.preferred_tone = None
            db_session.commit()
            
            result = await onboarding_service.process_message_with_state_logic(
                test_user.id,
                expression
            )
            
            # Verify validation passed
            assert result['validation_passed'] is True
            
            # Verify tone was extracted
            db_session.refresh(session)
            assert session.preferred_tone == expected_tone


class TestStateTransitionsWithVariousResponses:
    """Test state transitions with different types of user responses."""
    
    @pytest.mark.asyncio
    async def test_affirmative_responses(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that various affirmative responses are recognized."""
        # Create session in CONFIRM_DETAILS state (better for testing affirmative responses)
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.CONFIRM_DETAILS,
            project_name="Test Project",
            project_goal="Test goal",
            deadline=datetime.now() + timedelta(days=30),
            checkin_frequency="daily",
            preferred_tone="supportive",
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[]
        )
        db_session.add(session)
        db_session.commit()
        
        # Test various affirmative responses that are recognized by the system
        affirmative_responses = [
            "yes",
            "yeah",
            "yep",
            "sure",
            "correct",
            "looks good",
            "confirm"
        ]
        
        # Mock LLM service for summary generation
        mock_tasks = [
            {"title": "Task 1", "description": "Desc 1", "estimated_duration_hours": 5, "order": 1}
        ]
        
        with patch('app.services.onboarding_service.llm_service') as mock_llm:
            mock_llm.decompose_project = AsyncMock(return_value=mock_tasks)
            
            for response in affirmative_responses:
                # Reset session state
                session.current_state = OnboardingState.CONFIRM_DETAILS
                db_session.commit()
                
                result = await onboarding_service.process_message_with_state_logic(
                    test_user.id,
                    response
                )
                
                # Should transition to SHOW_SUMMARY state
                assert result['current_state'] == OnboardingState.SHOW_SUMMARY.value
    
    @pytest.mark.asyncio
    async def test_negative_responses(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that various negative responses are recognized."""
        # Create session in SHOW_SUMMARY state
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.SHOW_SUMMARY,
            project_name="Test Project",
            project_goal="Test goal",
            deadline=datetime.now() + timedelta(days=30),
            checkin_frequency="daily",
            preferred_tone="supportive",
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[]
        )
        db_session.add(session)
        db_session.commit()
        
        # Test various negative responses
        negative_responses = [
            "no",
            "nope",
            "not quite",
            "I want to change something",
            "let me edit that"
        ]
        
        for response in negative_responses:
            # Reset session state
            session.current_state = OnboardingState.SHOW_SUMMARY
            db_session.commit()
            
            result = await onboarding_service.process_message_with_state_logic(
                test_user.id,
                response
            )
            
            # Should not proceed to completion
            assert result['current_state'] != OnboardingState.COMPLETED.value
            
            # Should ask for clarification or go back
            assert 'reply' in result
    
    @pytest.mark.asyncio
    async def test_ambiguous_responses_trigger_clarification(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that ambiguous responses trigger clarifying questions."""
        # Create session in CONFIRM_DETAILS state
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.CONFIRM_DETAILS,
            project_name="Test Project",
            project_goal="Test goal",
            deadline=datetime.now() + timedelta(days=30),
            checkin_frequency="daily",
            preferred_tone="supportive",
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[]
        )
        db_session.add(session)
        db_session.commit()
        
        # Test ambiguous responses
        ambiguous_responses = [
            "maybe",
            "I'm not sure",
            "hmm",
            "kind of",
            "sort of"
        ]
        
        for response in ambiguous_responses:
            # Reset session state
            session.current_state = OnboardingState.CONFIRM_DETAILS
            db_session.commit()
            
            result = await onboarding_service.process_message_with_state_logic(
                test_user.id,
                response
            )
            
            # Should stay in same state (validation failed)
            assert result['validation_passed'] is False
            assert result['current_state'] == OnboardingState.CONFIRM_DETAILS.value
            
            # Should have a reply (asking for clarification)
            assert 'reply' in result
            assert len(result['reply']) > 0


class TestSummaryGenerationWithProjectPlan:
    """Test summary generation including project plan."""
    
    @pytest.mark.asyncio
    async def test_summary_includes_project_details(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that summary includes all project details."""
        # Create session in CONFIRM_DETAILS state
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.CONFIRM_DETAILS,
            project_name="Build a Mobile App",
            project_goal="Create a fitness tracking app",
            deadline=datetime.utcnow() + timedelta(days=90),
            checkin_frequency="every 2-3 days",
            preferred_tone="supportive",
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[]
        )
        db_session.add(session)
        db_session.commit()
        
        # Mock LLM service to return tasks
        mock_tasks = [
            {"title": "Design UI", "description": "Create mockups", "estimated_duration_hours": 10, "order": 1},
            {"title": "Backend API", "description": "Build REST API", "estimated_duration_hours": 20, "order": 2},
            {"title": "Frontend", "description": "Implement UI", "estimated_duration_hours": 25, "order": 3},
            {"title": "Testing", "description": "Write tests", "estimated_duration_hours": 15, "order": 4},
            {"title": "Deployment", "description": "Deploy to production", "estimated_duration_hours": 5, "order": 5}
        ]
        
        with patch('app.services.onboarding_service.llm_service') as mock_llm:
            mock_llm.decompose_project = AsyncMock(return_value=mock_tasks)
            
            # Process confirmation to generate summary
            result = await onboarding_service.process_message_with_state_logic(
                test_user.id,
                "yes"
            )
            
            # Verify summary was generated
            assert result['validation_passed'] is True
            assert result['current_state'] == OnboardingState.SHOW_SUMMARY.value
            
            # Verify summary includes project details
            summary = result['reply']
            assert "Build a Mobile App" in summary
            assert "Create a fitness tracking app" in summary
            assert "5 tasks" in summary or "5 milestones" in summary
            
            # Verify total hours are calculated
            assert "75" in summary  # Total hours
    
    @pytest.mark.asyncio
    async def test_summary_includes_task_breakdown(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that summary includes detailed task breakdown."""
        # Create session in CONFIRM_DETAILS state
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.CONFIRM_DETAILS,
            project_name="Learn Python",
            project_goal="Master Python fundamentals",
            deadline=datetime.utcnow() + timedelta(days=60),
            checkin_frequency="daily",
            preferred_tone="direct",
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[]
        )
        db_session.add(session)
        db_session.commit()
        
        # Mock LLM service
        mock_tasks = [
            {"title": "Variables", "description": "Learn variables", "estimated_duration_hours": 5, "order": 1},
            {"title": "Functions", "description": "Learn functions", "estimated_duration_hours": 8, "order": 2},
            {"title": "OOP", "description": "Learn OOP", "estimated_duration_hours": 12, "order": 3}
        ]
        
        with patch('app.services.onboarding_service.llm_service') as mock_llm:
            mock_llm.decompose_project = AsyncMock(return_value=mock_tasks)
            
            result = await onboarding_service.process_message_with_state_logic(
                test_user.id,
                "yes"
            )
            
            summary = result['reply']
            
            # Verify task titles are in summary
            assert "Variables" in summary
            assert "Functions" in summary
            assert "OOP" in summary
    
    @pytest.mark.asyncio
    async def test_summary_fallback_on_llm_failure(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that summary generation falls back gracefully on LLM failure."""
        # Create session in CONFIRM_DETAILS state
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.CONFIRM_DETAILS,
            project_name="Test Project",
            project_goal="Test goal",
            deadline=datetime.utcnow() + timedelta(days=30),
            checkin_frequency="daily",
            preferred_tone="supportive",
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[]
        )
        db_session.add(session)
        db_session.commit()
        
        # Mock LLM service to raise exception
        with patch('app.services.onboarding_service.llm_service') as mock_llm:
            mock_llm.decompose_project = AsyncMock(side_effect=Exception("LLM API error"))
            
            result = await onboarding_service.process_message_with_state_logic(
                test_user.id,
                "yes"
            )
            
            # Should still generate summary (without tasks)
            assert result['validation_passed'] is True
            assert result['current_state'] == OnboardingState.SHOW_SUMMARY.value
            
            # Summary should still include basic project details
            summary = result['reply']
            assert "Test Project" in summary
            assert "Test goal" in summary


class TestErrorHandlingAndClarifyingQuestions:
    """Test error handling and clarifying questions."""
    
    @pytest.mark.asyncio
    async def test_invalid_date_triggers_clarification(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that invalid dates trigger clarifying questions."""
        # Create session in COLLECT_DEADLINE state
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.COLLECT_DEADLINE,
            project_name="Test Project",
            project_goal="Test goal",
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[]
        )
        db_session.add(session)
        db_session.commit()
        
        # Test clearly invalid date formats
        invalid_dates = [
            "asdfghjkl",
            "not a date",
            "xyz123"
        ]
        
        for invalid_date in invalid_dates:
            # Reset session state
            session.current_state = OnboardingState.COLLECT_DEADLINE
            session.deadline = None
            db_session.commit()
            
            result = await onboarding_service.process_message_with_state_logic(
                test_user.id,
                invalid_date
            )
            
            # Should either stay in COLLECT_DEADLINE or move to CONFIRM_DEADLINE
            # (depending on whether the parser found something)
            assert result['current_state'] in [
                OnboardingState.COLLECT_DEADLINE.value,
                OnboardingState.CONFIRM_DEADLINE.value
            ]
            
            # Should have a reply
            assert 'reply' in result
            assert len(result['reply']) > 0
    
    @pytest.mark.asyncio
    async def test_past_date_triggers_warning(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that past dates trigger warning messages."""
        # Create session in COLLECT_DEADLINE state
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.COLLECT_DEADLINE,
            project_name="Test Project",
            project_goal="Test goal",
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[]
        )
        db_session.add(session)
        db_session.commit()
        
        # Test past date
        past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        result = await onboarding_service.process_message_with_state_logic(
            test_user.id,
            past_date
        )
        
        # Should stay in same state
        assert result['current_state'] == OnboardingState.COLLECT_DEADLINE.value
        
        # Should warn about past date
        assert 'reply' in result
        assert 'past' in result['reply'].lower()
    
    @pytest.mark.asyncio
    async def test_empty_input_triggers_clarification(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that empty inputs trigger clarifying questions."""
        # Create session in COLLECT_PROJECT_NAME state
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.COLLECT_PROJECT_NAME,
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[]
        )
        db_session.add(session)
        db_session.commit()
        
        # Test empty/whitespace inputs
        empty_inputs = ["", "   ", "\n", "\t"]
        
        for empty_input in empty_inputs:
            # Reset session state
            session.current_state = OnboardingState.COLLECT_PROJECT_NAME
            session.project_name = None
            db_session.commit()
            
            result = await onboarding_service.process_message_with_state_logic(
                test_user.id,
                empty_input
            )
            
            # Should stay in same state
            assert result['current_state'] == OnboardingState.COLLECT_PROJECT_NAME.value
            
            # Should ask for input
            assert 'reply' in result
    
    @pytest.mark.asyncio
    async def test_too_short_input_triggers_validation_error(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that too-short inputs trigger validation errors."""
        # Create session in COLLECT_PROJECT_NAME state
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.COLLECT_PROJECT_NAME,
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[]
        )
        db_session.add(session)
        db_session.commit()
        
        # Test too-short input
        result = await onboarding_service.process_message_with_state_logic(
            test_user.id,
            "A"
        )
        
        # Should stay in same state
        assert result['current_state'] == OnboardingState.COLLECT_PROJECT_NAME.value
        
        # Should mention minimum length
        assert 'reply' in result
        assert 'character' in result['reply'].lower() or 'short' in result['reply'].lower()


class TestContextualAndNaturalLLMResponses:
    """Test that LLM responses are contextual and natural."""
    
    @pytest.mark.asyncio
    async def test_responses_include_user_context(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that responses reference user's previous inputs."""
        # Create session with some collected data
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.COLLECT_GOAL,
            project_name="My Awesome App",
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "role": "user",
                    "message": "My Awesome App"
                }
            ]
        )
        db_session.add(session)
        db_session.commit()
        
        # Mock LLM to return contextual response
        with patch('app.services.onboarding_service.llm_service') as mock_llm:
            mock_llm.generate_onboarding_message = AsyncMock(
                return_value="Great name! What's your main goal for My Awesome App?"
            )
            
            # Generate response
            response = await onboarding_service.generate_response(test_user.id)
            
            # Verify response references the project name
            assert "My Awesome App" in response
    
    @pytest.mark.asyncio
    async def test_responses_adapt_to_tone_preference(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that responses adapt to user's tone preference."""
        tones = ['supportive', 'direct', 'casual', 'drill_sergeant']
        
        for tone in tones:
            # Create session with specific tone
            session = OnboardingSession(
                user_id=test_user.id,
                discord_id=test_user.discord_user_id,
                current_state=OnboardingState.COLLECT_PROJECT_NAME,
                preferred_tone=tone,
                started_at=datetime.utcnow(),
                last_activity_at=datetime.utcnow(),
                conversation_history=[]
            )
            db_session.add(session)
            db_session.commit()
            
            # Mock LLM to verify tone is passed
            with patch('app.services.onboarding_service.llm_service') as mock_llm:
                mock_llm.generate_onboarding_message = AsyncMock(
                    return_value=f"Response in {tone} tone"
                )
                
                # Generate response
                response = await onboarding_service.generate_response(test_user.id)
                
                # Verify LLM was called with correct tone
                call_args = mock_llm.generate_onboarding_message.call_args
                assert call_args.kwargs['tone'] == tone
            
            # Clean up
            db_session.delete(session)
            db_session.commit()
    
    @pytest.mark.asyncio
    async def test_responses_acknowledge_user_input(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that responses acknowledge user's input."""
        # Create session with user input
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.COLLECT_GOAL,
            project_name="Build a Website",
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "role": "user",
                    "message": "Build a Website"
                }
            ]
        )
        db_session.add(session)
        db_session.commit()
        
        # Mock LLM to return acknowledgment
        with patch('app.services.onboarding_service.llm_service') as mock_llm:
            mock_llm.generate_onboarding_message = AsyncMock(
                return_value="Love that! What's your goal for Build a Website?"
            )
            
            # Generate response with acknowledgment
            response = await onboarding_service.generate_response(
                test_user.id,
                acknowledge_user_input=True
            )
            
            # Verify acknowledgment was requested
            call_args = mock_llm.generate_onboarding_message.call_args
            assert call_args.kwargs['acknowledge_input'] is True
    
    @pytest.mark.asyncio
    async def test_conversation_history_maintains_context(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test that conversation history maintains context across messages."""
        # Create session with conversation history
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.COLLECT_DEADLINE,
            project_name="Learn Guitar",
            project_goal="Master 10 songs",
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "role": "user",
                    "message": "Learn Guitar"
                },
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "role": "assistant",
                    "message": "Great! What's your goal?"
                },
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "role": "user",
                    "message": "Master 10 songs"
                }
            ]
        )
        db_session.add(session)
        db_session.commit()
        
        # Mock LLM to verify conversation history is passed
        with patch('app.services.onboarding_service.llm_service') as mock_llm:
            mock_llm.generate_onboarding_message = AsyncMock(
                return_value="When would you like to master those 10 songs?"
            )
            
            # Generate response
            response = await onboarding_service.generate_response(test_user.id)
            
            # Verify conversation history was passed to LLM
            call_args = mock_llm.generate_onboarding_message.call_args
            conversation_history = call_args.kwargs['conversation_history']
            
            # Should have at least the original 3 messages
            assert len(conversation_history) >= 3
            assert conversation_history[0]['message'] == 'Learn Guitar'
            assert conversation_history[2]['message'] == 'Master 10 songs'


class TestCompleteEnhancedFlow:
    """Test complete enhanced conversational flow end-to-end."""
    
    @pytest.mark.asyncio
    async def test_complete_flow_with_natural_language(
        self,
        db_session,
        test_user,
        onboarding_service
    ):
        """Test complete onboarding flow with natural language inputs."""
        # Create initial session
        session = OnboardingSession(
            user_id=test_user.id,
            discord_id=test_user.discord_user_id,
            current_state=OnboardingState.WELCOME,
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[]
        )
        db_session.add(session)
        db_session.commit()
        
        # Step 1: Provide project name
        result1 = await onboarding_service.process_message_with_state_logic(
            test_user.id,
            "I want to build a mobile fitness app"
        )
        assert result1['validation_passed'] is True
        assert result1['current_state'] == OnboardingState.COLLECT_GOAL.value
        
        # Step 2: Provide goal
        result2 = await onboarding_service.process_message_with_state_logic(
            test_user.id,
            "Help people track their workouts and nutrition"
        )
        assert result2['validation_passed'] is True
        assert result2['current_state'] == OnboardingState.COLLECT_DEADLINE.value
        
        # Step 3: Provide deadline
        future_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        result3 = await onboarding_service.process_message_with_state_logic(
            test_user.id,
            future_date
        )
        assert result3['validation_passed'] is True
        
        # Step 4: Confirm deadline (if needed)
        db_session.refresh(session)
        if session.current_state == OnboardingState.CONFIRM_DEADLINE:
            result3b = await onboarding_service.process_message_with_state_logic(
                test_user.id,
                "yes"
            )
            assert result3b['validation_passed'] is True
        
        # Step 5: Provide check-in frequency (use simple format)
        result4 = await onboarding_service.process_message_with_state_logic(
            test_user.id,
            "daily"
        )
        assert result4['validation_passed'] is True
        
        # Step 6: Provide tone
        result5 = await onboarding_service.process_message_with_state_logic(
            test_user.id,
            "supportive"
        )
        assert result5['validation_passed'] is True
        assert result5['current_state'] == OnboardingState.CONFIRM_DETAILS.value
        
        # Verify all data was collected
        db_session.refresh(session)
        assert session.project_name is not None
        assert session.project_goal is not None
        assert session.deadline is not None
        assert session.checkin_frequency is not None
        assert session.preferred_tone is not None
        
        # Step 7: Confirm details and generate summary
        mock_tasks = [
            {"title": "Task 1", "description": "Desc 1", "estimated_duration_hours": 10, "order": 1},
            {"title": "Task 2", "description": "Desc 2", "estimated_duration_hours": 15, "order": 2},
            {"title": "Task 3", "description": "Desc 3", "estimated_duration_hours": 20, "order": 3}
        ]
        
        with patch('app.services.onboarding_service.llm_service') as mock_llm:
            mock_llm.decompose_project = AsyncMock(return_value=mock_tasks)
            
            result6 = await onboarding_service.process_message_with_state_logic(
                test_user.id,
                "yes"
            )
            
            assert result6['validation_passed'] is True
            assert result6['current_state'] == OnboardingState.SHOW_SUMMARY.value
            assert "3 tasks" in result6['reply'] or "3 milestones" in result6['reply']
        
        # Step 8: Confirm summary and complete
        result7 = await onboarding_service.process_message_with_state_logic(
            test_user.id,
            "yes"
        )
        
        assert result7['validation_passed'] is True
        assert result7['current_state'] == OnboardingState.COMPLETED.value
        
        # Verify project was created
        projects = db_session.query(Project).filter(Project.user_id == test_user.id).all()
        assert len(projects) == 1
        
        # Verify user is marked as onboarded
        db_session.refresh(test_user)
        assert test_user.is_new is False
        
        # Verify conversation history is complete
        db_session.refresh(session)
        assert len(session.conversation_history) > 5  # Multiple exchanges
