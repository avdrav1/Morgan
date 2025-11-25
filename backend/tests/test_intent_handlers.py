"""
Tests for specific intent handlers.

Tests each intent handler individually to ensure they work correctly.
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
        timezone="America/New_York",
        preferred_tone="friendly"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
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
    db_session.refresh(project)
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
    for milestone in milestones:
        db_session.refresh(milestone)
    
    return milestones


class TestEditDeadlineHandler:
    """
    Tests for EDIT_DEADLINE intent handler.
    
    Validates: Requirements 3.1, 4.1, 4.2, 4.3, 4.5
    """
    
    @pytest.mark.asyncio
    async def test_edit_deadline_with_confirmation(
        self,
        db_session,
        test_user,
        test_project,
        test_milestones
    ):
        """Test editing deadline with milestone adjustments and confirmation."""
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        
        # First request to change deadline
        request1 = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="Change my deadline to next month"
        )
        
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_llm:
            mock_llm.return_value = '''
            {
                "intent_type": "EDIT_DEADLINE",
                "parameters": {"new_deadline": "2024-12-31"},
                "confidence": 0.90
            }
            '''
            
            response1 = await handle_project_plan_message(request1, db_session)
            
            # Should ask for confirmation
            assert "reply" in response1
            reply1 = response1["reply"]
            assert "confirm" in reply1.lower() or "yes" in reply1.lower()
        
        # Second request to confirm
        request2 = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="yes"
        )
        
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_llm:
            mock_llm.return_value = '''
            {
                "intent_type": "EDIT_DEADLINE",
                "parameters": {"confirmation": "yes"},
                "confidence": 0.95
            }
            '''
            
            response2 = await handle_project_plan_message(request2, db_session)
            
            # Should confirm the change
            assert "reply" in response2
            reply2 = response2["reply"]
            assert "updated" in reply2.lower() or "✅" in reply2


class TestAddMilestoneHandler:
    """
    Tests for ADD_MILESTONE intent handler.
    
    Validates: Requirements 3.3
    """
    
    @pytest.mark.asyncio
    async def test_add_milestone_success(
        self,
        db_session,
        test_user,
        test_project
    ):
        """Test successfully adding a milestone."""
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        
        request = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="Add a milestone called 'Complete design' for December 15"
        )
        
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_llm:
            mock_llm.return_value = '''
            {
                "intent_type": "ADD_MILESTONE",
                "parameters": {
                    "milestone_title": "Complete design",
                    "target_date": "2024-12-15"
                },
                "confidence": 0.90
            }
            '''
            
            response = await handle_project_plan_message(request, db_session)
            
            # Should confirm addition
            assert "reply" in response
            reply = response["reply"]
            assert "added" in reply.lower() or "✅" in reply
            assert "Complete design" in reply
    
    @pytest.mark.asyncio
    async def test_add_milestone_after_deadline_error(
        self,
        db_session,
        test_user,
        test_project
    ):
        """Test error when adding milestone after project deadline."""
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        
        # Set project deadline to soon
        test_project.target_completion_date = datetime.utcnow() + timedelta(days=10)
        db_session.commit()
        
        request = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="Add a milestone for next year"
        )
        
        # Calculate a date after the deadline
        future_date = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d")
        
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_llm:
            mock_llm.return_value = f'''
            {{
                "intent_type": "ADD_MILESTONE",
                "parameters": {{
                    "milestone_title": "Future milestone",
                    "target_date": "{future_date}"
                }},
                "confidence": 0.90
            }}
            '''
            
            response = await handle_project_plan_message(request, db_session)
            
            # Should show error
            assert "reply" in response
            reply = response["reply"]
            assert "after" in reply.lower() and "deadline" in reply.lower()


class TestMarkCompleteHandler:
    """
    Tests for MARK_COMPLETE intent handler.
    
    Validates: Requirements 5.1, 5.2, 5.3, 5.4
    """
    
    @pytest.mark.asyncio
    async def test_mark_milestone_complete(
        self,
        db_session,
        test_user,
        test_project,
        test_milestones
    ):
        """Test marking a milestone as complete."""
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        
        request = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="I completed Milestone 1"
        )
        
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_llm:
            mock_llm.return_value = '''
            {
                "intent_type": "MARK_COMPLETE",
                "parameters": {"milestone_identifier": "Milestone 1"},
                "confidence": 0.95
            }
            '''
            
            response = await handle_project_plan_message(request, db_session)
            
            # Should celebrate and show next milestone
            assert "reply" in response
            reply = response["reply"]
            
            # Should have celebration
            assert any(emoji in reply for emoji in ["🎉", "🌟", "🚀", "💪", "✨"])
            
            # Should mention the completed milestone
            assert "Milestone 1" in reply
            
            # Should show next milestone
            assert "Milestone 2" in reply or "next" in reply.lower()
    
    @pytest.mark.asyncio
    async def test_mark_all_milestones_complete(
        self,
        db_session,
        test_user,
        test_project,
        test_milestones
    ):
        """Test marking the last milestone as complete."""
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        
        # Mark first two milestones as complete
        for milestone in test_milestones[:2]:
            milestone.status = MilestoneStatus.COMPLETED
            milestone.completed_at = datetime.utcnow()
        db_session.commit()
        
        # Mark the last one
        request = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="I completed Milestone 3"
        )
        
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_llm:
            mock_llm.return_value = '''
            {
                "intent_type": "MARK_COMPLETE",
                "parameters": {"milestone_identifier": "Milestone 3"},
                "confidence": 0.95
            }
            '''
            
            response = await handle_project_plan_message(request, db_session)
            
            # Should celebrate project completion
            assert "reply" in response
            reply = response["reply"]
            
            # Should have celebration
            assert "🎊" in reply or "Congratulations" in reply
            
            # Should mention all milestones complete
            assert "all" in reply.lower() and "complete" in reply.lower()


class TestDeleteMilestoneHandler:
    """
    Tests for DELETE_MILESTONE intent handler.
    
    Validates: Requirements 3.4
    """
    
    @pytest.mark.asyncio
    async def test_delete_milestone_with_confirmation(
        self,
        db_session,
        test_user,
        test_project,
        test_milestones
    ):
        """Test deleting a milestone with confirmation."""
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        
        # First request to delete
        request1 = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="Remove Milestone 2"
        )
        
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_llm:
            mock_llm.return_value = '''
            {
                "intent_type": "DELETE_MILESTONE",
                "parameters": {"milestone_identifier": "Milestone 2"},
                "confidence": 0.90
            }
            '''
            
            response1 = await handle_project_plan_message(request1, db_session)
            
            # Should ask for confirmation
            assert "reply" in response1
            reply1 = response1["reply"]
            assert "sure" in reply1.lower() or "confirm" in reply1.lower()
            assert "Milestone 2" in reply1
        
        # Second request to confirm
        request2 = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="yes, delete it"
        )
        
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_llm:
            mock_llm.return_value = '''
            {
                "intent_type": "DELETE_MILESTONE",
                "parameters": {"confirmation": "yes"},
                "confidence": 0.95
            }
            '''
            
            response2 = await handle_project_plan_message(request2, db_session)
            
            # Should confirm deletion
            assert "reply" in response2
            reply2 = response2["reply"]
            assert "removed" in reply2.lower() or "deleted" in reply2.lower()


class TestEditMilestoneHandler:
    """
    Tests for EDIT_MILESTONE intent handler.
    
    Validates: Requirements 3.2
    """
    
    @pytest.mark.asyncio
    async def test_edit_milestone_title(
        self,
        db_session,
        test_user,
        test_project,
        test_milestones
    ):
        """Test editing a milestone's title."""
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        
        request = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="Change Milestone 1 to 'Complete initial setup'"
        )
        
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_llm:
            mock_llm.return_value = '''
            {
                "intent_type": "EDIT_MILESTONE",
                "parameters": {
                    "milestone_identifier": "Milestone 1",
                    "new_title": "Complete initial setup"
                },
                "confidence": 0.90
            }
            '''
            
            response = await handle_project_plan_message(request, db_session)
            
            # Should confirm the change
            assert "reply" in response
            reply = response["reply"]
            assert "updated" in reply.lower() or "✅" in reply
            assert "Complete initial setup" in reply


class TestAskQuestionHandler:
    """
    Tests for ASK_QUESTION intent handler.
    
    Validates: Requirements 2.1, 2.2, 2.5
    """
    
    @pytest.mark.asyncio
    async def test_ask_question_with_context(
        self,
        db_session,
        test_user,
        test_project,
        test_milestones
    ):
        """Test asking a question about the project."""
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        
        request = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="How much time do I have until my deadline?"
        )
        
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_intent:
            mock_intent.return_value = '''
            {
                "intent_type": "ASK_QUESTION",
                "parameters": {"question": "How much time do I have until my deadline?"},
                "confidence": 0.90
            }
            '''
            
            # Mock LLM answer
            with patch('app.services.llm_service.llm_service.client.messages.create') as mock_answer:
                mock_response = Mock()
                mock_response.content = [Mock(text="You have 30 days until your deadline.")]
                mock_answer.return_value = mock_response
                
                response = await handle_project_plan_message(request, db_session)
                
                # Should provide an answer
                assert "reply" in response
                reply = response["reply"]
                assert len(reply) > 0
                
                # LLM should have been called with project context
                mock_answer.assert_called_once()
                call_args = mock_answer.call_args
                prompt = call_args[1]['messages'][0]['content']
                
                # Should include project details in context
                assert test_project.title in prompt
                assert test_project.goal in prompt


class TestUnclearHandler:
    """
    Tests for UNCLEAR intent handler.
    
    Validates: Requirements 2.3, 6.4
    """
    
    @pytest.mark.asyncio
    async def test_unclear_intent_provides_help(
        self,
        db_session,
        test_user,
        test_project
    ):
        """Test that unclear intent provides helpful guidance."""
        from app.api.discord import handle_project_plan_message, ProjectPlanMessageRequest
        
        request = ProjectPlanMessageRequest(
            user_id=str(test_user.id),
            discord_user_id=test_user.discord_user_id,
            message="umm"
        )
        
        with patch('app.services.intent_classifier.IntentClassifier._call_llm_for_classification') as mock_llm:
            mock_llm.return_value = '''
            {
                "intent_type": "UNCLEAR",
                "parameters": {},
                "confidence": 0.20
            }
            '''
            
            response = await handle_project_plan_message(request, db_session)
            
            # Should provide help
            assert "reply" in response
            reply = response["reply"]
            
            # Should list available actions
            assert "view" in reply.lower() or "plan" in reply.lower()
            assert "milestone" in reply.lower()
            assert "deadline" in reply.lower()
