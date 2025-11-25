"""
Integration tests for Discord project plan handler.

Tests the end-to-end flow of handling Discord messages for project plan management.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock

from app.models.user import User
from app.models.project import Project
from app.models.milestone import Milestone, MilestoneStatus


@pytest.fixture
def test_user(db_session):
    """Create a test user with Discord ID."""
    user = User(
        id=uuid4(),
        email="test@example.com",
        full_name="Test User",
        discord_user_id="123456789",
        timezone="America/New_York"
    )
    db_session.add(user)
    db_session.commit()
    # No refresh needed with expire_on_commit=False
    return user


@pytest.fixture
def test_project(db_session, test_user):
    """Create a test project."""
    project = Project(
        id=uuid4(),
        user_id=test_user.id,
        title="Test Project",
        description="A test project for integration testing",
        goal="Build a test application",
        target_completion_date=datetime.utcnow() + timedelta(days=30),
        status="active"
    )
    db_session.add(project)
    db_session.commit()
    # No refresh needed with expire_on_commit=False
    return project


@pytest.fixture
def test_milestones(db_session, test_project):
    """Create test milestones."""
    milestones = []
    for i in range(3):
        milestone = Milestone(
            id=uuid4(),
            project_id=test_project.id,
            title=f"Milestone {i+1}",
            description=f"Description for milestone {i+1}",
            target_date=datetime.utcnow() + timedelta(days=(i+1)*10),
            status=MilestoneStatus.PENDING,
            order=i
        )
        db_session.add(milestone)
        milestones.append(milestone)
    
    db_session.commit()
    # No refresh needed with expire_on_commit=False
    
    return milestones


class TestProjectPlanHandlerIntegration:
    """
    Integration tests for Discord project plan handler.
    
    Validates: Requirements 1.1, 2.1, 3.1, 4.1, 5.1
    """
    
    @pytest.mark.asyncio
    async def test_view_plan_flow(self, db_session, test_user, test_project, test_milestones):
        """
        Test end-to-end flow: view plan.
        
        Validates: Requirements 1.1, 1.2, 1.3
        """
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        
        # Create request
        request = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="Show me my project plan"
        )
        
        # Mock LLM service to return VIEW_PLAN intent
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_llm:
            mock_llm.return_value = '''
            {
                "intent_type": "VIEW_PLAN",
                "parameters": {},
                "confidence": 0.95
            }
            '''
            
            # Handle the message
            response = await handle_project_plan_message(request, db_session)
            
            # Verify response
            assert "reply" in response
            reply = response["reply"]
            
            # Should contain project name
            assert test_project.title in reply
            
            # Should contain milestone titles
            for milestone in test_milestones:
                assert milestone.title in reply
            
            # Should contain status emojis
            assert "⏳" in reply  # Pending emoji
    
    @pytest.mark.asyncio
    async def test_view_plan_generates_milestones_if_none_exist(
        self,
        db_session,
        test_user,
        test_project
    ):
        """
        Test that viewing a plan generates initial milestones if none exist.
        
        Validates: Requirements 1.4, 1.5
        """
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        
        # Ensure no milestones exist
        assert len(test_project.milestones) == 0
        
        # Create request
        request = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="Show me my project plan"
        )
        
        # Mock LLM service
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_llm:
            mock_llm.return_value = '''
            {
                "intent_type": "VIEW_PLAN",
                "parameters": {},
                "confidence": 0.95
            }
            '''
            
            # Mock milestone generation
            with patch('app.services.milestone_generator.MilestoneGenerator.generate_milestones') as mock_gen:
                # Create mock milestones
                mock_milestones = [
                    Milestone(
                        id=uuid4(),
                        project_id=test_project.id,
                        title=f"Generated Milestone {i+1}",
                        target_date=datetime.utcnow() + timedelta(days=(i+1)*10),
                        status=MilestoneStatus.PENDING,
                        order=i
                    )
                    for i in range(3)
                ]
                mock_gen.return_value = mock_milestones
                
                # Handle the message
                response = await handle_project_plan_message(request, db_session)
                
                # Verify milestone generation was called
                mock_gen.assert_called_once()
                
                # Verify response contains generated milestones
                reply = response["reply"]
                for milestone in mock_milestones:
                    assert milestone.title in reply
    
    @pytest.mark.asyncio
    async def test_ask_question_flow(self, db_session, test_user, test_project, test_milestones):
        """
        Test end-to-end flow: ask question.
        
        Validates: Requirements 2.1, 2.2, 2.5
        """
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        
        # Create request
        request = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="When is my next milestone?"
        )
        
        # Mock LLM service for intent classification
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_intent:
            mock_intent.return_value = '''
            {
                "intent_type": "ASK_QUESTION",
                "parameters": {"question": "When is my next milestone?"},
                "confidence": 0.90
            }
            '''
            
            # Mock LLM service for answering the question
            with patch('app.services.llm_service.llm_service.client.messages.create') as mock_answer:
                mock_response = Mock()
                mock_response.content = [Mock(text="Your next milestone is Milestone 1, due in 10 days.")]
                mock_answer.return_value = mock_response
                
                # Handle the message
                response = await handle_project_plan_message(request, db_session)
                
                # Verify response
                assert "reply" in response
                reply = response["reply"]
                
                # Should contain the answer
                assert "Milestone 1" in reply or "milestone" in reply.lower()
    
    @pytest.mark.asyncio
    async def test_unclear_intent_flow(self, db_session, test_user, test_project):
        """
        Test end-to-end flow: unclear intent.
        
        Validates: Requirements 2.3, 6.4
        """
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        
        # Create request with ambiguous message
        request = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="hmm"
        )
        
        # Mock LLM service to return UNCLEAR intent
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_llm:
            mock_llm.return_value = '''
            {
                "intent_type": "UNCLEAR",
                "parameters": {},
                "confidence": 0.30
            }
            '''
            
            # Handle the message
            response = await handle_project_plan_message(request, db_session)
            
            # Verify response
            assert "reply" in response
            reply = response["reply"]
            
            # Should provide guidance
            assert "help" in reply.lower() or "can" in reply.lower()
            
            # Should list available actions
            assert "view" in reply.lower() or "plan" in reply.lower()
    
    @pytest.mark.asyncio
    async def test_conversation_history_preserved(
        self,
        db_session,
        test_user,
        test_project,
        test_milestones
    ):
        """
        Test that conversation history is preserved across messages.
        
        Validates: Requirements 2.2, 6.1
        """
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        from app.services.project_plan_conversation_manager import ProjectPlanConversationManager
        
        # Send first message
        request1 = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="Show me my project plan"
        )
        
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_llm:
            mock_llm.return_value = '''
            {
                "intent_type": "VIEW_PLAN",
                "parameters": {},
                "confidence": 0.95
            }
            '''
            
            await handle_project_plan_message(request1, db_session)
        
        # Send second message
        request2 = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="When is the deadline?"
        )
        
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_llm:
            mock_llm.return_value = '''
            {
                "intent_type": "ASK_QUESTION",
                "parameters": {"question": "When is the deadline?"},
                "confidence": 0.90
            }
            '''
            
            with patch('app.services.llm_service.llm_service.client.messages.create') as mock_answer:
                mock_response = Mock()
                mock_response.content = [Mock(text="The deadline is in 30 days.")]
                mock_answer.return_value = mock_response
                
                await handle_project_plan_message(request2, db_session)
        
        # Check conversation history
        conversation_manager = ProjectPlanConversationManager(db_session)
        history = conversation_manager.get_conversation_history(
            test_user.id,
            test_project.id
        )
        
        # Should have 4 messages (2 user + 2 assistant)
        assert len(history) >= 2
        
        # Verify messages are in history
        user_messages = [msg for msg in history if msg['role'] == 'user']
        assert len(user_messages) >= 2
        assert any("project plan" in msg['content'].lower() for msg in user_messages)
        assert any("deadline" in msg['content'].lower() for msg in user_messages)
    
    @pytest.mark.asyncio
    async def test_no_project_found_error(self, db_session, test_user):
        """
        Test error handling when user has no projects.
        
        Validates: Requirements 1.1
        """
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        from fastapi import HTTPException
        
        # Ensure user has no projects
        assert len(test_user.projects) == 0
        
        # Create request
        request = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="Show me my project plan"
        )
        
        # Should raise 404 error
        with pytest.raises(HTTPException) as exc_info:
            await handle_project_plan_message(request, db_session)
        
        assert exc_info.value.status_code == 404
        assert "project" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_invalid_user_id_error(self, db_session):
        """
        Test error handling with invalid user ID format.
        
        Validates: Requirements 1.1
        """
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        from fastapi import HTTPException
        
        # Create request with invalid user ID
        request = ProjectPlanMessageRequest(
            user_id="not-a-uuid",
            discord_user_id="123456789",
            message="Show me my project plan"
        )
        
        # Should raise 400 error
        with pytest.raises(HTTPException) as exc_info:
            await handle_project_plan_message(request, db_session)
        
        assert exc_info.value.status_code == 400
        assert "user_id" in exc_info.value.detail.lower()
