"""
Unit tests for intent classification.

Tests various phrasings for each intent type, parameter extraction accuracy,
and ambiguous input handling.

Validates: Requirements 6.1, 6.2, 6.3, 6.4
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime

from app.services.intent_classifier import IntentClassifier, IntentType, Intent


class TestIntentClassification:
    """Test suite for intent classification."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.project_context = {
            'project_id': 'test-project-id',
            'project_name': 'Test Project',
            'project_goal': 'Build a great app',
            'deadline': '2024-12-31T00:00:00'
        }
        self.conversation_history = []
    
    def create_mock_llm_response(self, intent_type: str, parameters: dict = None, confidence: float = 0.9):
        """Helper to create mock LLM responses."""
        if parameters is None:
            parameters = {}
        
        return f'''{{
  "intent_type": "{intent_type}",
  "parameters": {str(parameters).replace("'", '"')},
  "confidence": {confidence}
}}'''
    
    @pytest.mark.asyncio
    async def test_view_plan_intent_various_phrasings(self):
        """
        Test VIEW_PLAN intent with various phrasings.
        
        Validates: Requirements 6.1, 6.2
        """
        test_messages = [
            "show me my project plan",
            "what's my plan?",
            "can I see my project?",
            "display my milestones",
            "view plan",
            "show plan",
        ]
        
        for message in test_messages:
            # Create mock LLM service
            mock_llm_service = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text=self.create_mock_llm_response("VIEW_PLAN"))]
            mock_llm_service.client.messages.create = Mock(return_value=mock_response)
            mock_llm_service.model = "claude-3-5-sonnet-20241022"
            
            # Create classifier
            classifier = IntentClassifier(llm_service=mock_llm_service)
            
            # Classify intent
            result = await classifier.classify_intent(
                message=message,
                conversation_history=self.conversation_history,
                project_context=self.project_context
            )
            
            assert result.type == IntentType.VIEW_PLAN, \
                f"Message '{message}' should be classified as VIEW_PLAN"
            assert result.confidence >= 0.7, \
                f"Confidence should be high for clear VIEW_PLAN message"
    
    @pytest.mark.asyncio
    async def test_edit_deadline_intent_with_parameter_extraction(self):
        """
        Test EDIT_DEADLINE intent with parameter extraction.
        
        Validates: Requirements 6.1, 6.2, 6.3
        """
        test_cases = [
            ("change my deadline to December 15", {"new_deadline": "2024-12-15"}),
            ("move the deadline to next Friday", {"new_deadline": "next Friday"}),
            ("extend deadline to 2024-12-31", {"new_deadline": "2024-12-31"}),
            ("I need more time, push deadline to Jan 1", {"new_deadline": "Jan 1"}),
        ]
        
        for message, expected_params in test_cases:
            # Create mock LLM service
            mock_llm_service = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text=self.create_mock_llm_response("EDIT_DEADLINE", expected_params))]
            mock_llm_service.client.messages.create = Mock(return_value=mock_response)
            mock_llm_service.model = "claude-3-5-sonnet-20241022"
            
            # Create classifier
            classifier = IntentClassifier(llm_service=mock_llm_service)
            
            # Classify intent
            result = await classifier.classify_intent(
                message=message,
                conversation_history=self.conversation_history,
                project_context=self.project_context
            )
            
            assert result.type == IntentType.EDIT_DEADLINE, \
                f"Message '{message}' should be classified as EDIT_DEADLINE"
            assert "new_deadline" in result.parameters, \
                f"Should extract new_deadline parameter from '{message}'"
    
    @pytest.mark.asyncio
    async def test_add_milestone_intent_with_parameters(self):
        """
        Test ADD_MILESTONE intent with parameter extraction.
        
        Validates: Requirements 6.1, 6.2, 6.3
        """
        test_cases = [
            ("add a milestone for testing phase", {"milestone_title": "testing phase"}),
            ("create milestone: Design Review on Dec 10", {"milestone_title": "Design Review", "target_date": "Dec 10"}),
            ("I want to add a milestone called 'Prototype Complete'", {"milestone_title": "Prototype Complete"}),
        ]
        
        for message, expected_params in test_cases:
            # Create mock LLM service
            mock_llm_service = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text=self.create_mock_llm_response("ADD_MILESTONE", expected_params))]
            mock_llm_service.client.messages.create = Mock(return_value=mock_response)
            mock_llm_service.model = "claude-3-5-sonnet-20241022"
            
            # Create classifier
            classifier = IntentClassifier(llm_service=mock_llm_service)
            
            # Classify intent
            result = await classifier.classify_intent(
                message=message,
                conversation_history=self.conversation_history,
                project_context=self.project_context
            )
            
            assert result.type == IntentType.ADD_MILESTONE, \
                f"Message '{message}' should be classified as ADD_MILESTONE"
            assert "milestone_title" in result.parameters, \
                f"Should extract milestone_title from '{message}'"
    
    @pytest.mark.asyncio
    async def test_edit_milestone_intent_with_identifier(self):
        """
        Test EDIT_MILESTONE intent with milestone identifier extraction.
        
        Validates: Requirements 6.1, 6.2, 6.3
        """
        test_cases = [
            ("change the Testing milestone date", {"milestone_identifier": "Testing"}),
            ("update milestone 2", {"milestone_identifier": "2"}),
            ("modify the first milestone", {"milestone_identifier": "first"}),
            ("edit Design Review milestone to next week", {"milestone_identifier": "Design Review"}),
        ]
        
        for message, expected_params in test_cases:
            # Create mock LLM service
            mock_llm_service = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text=self.create_mock_llm_response("EDIT_MILESTONE", expected_params))]
            mock_llm_service.client.messages.create = Mock(return_value=mock_response)
            mock_llm_service.model = "claude-3-5-sonnet-20241022"
            
            # Create classifier
            classifier = IntentClassifier(llm_service=mock_llm_service)
            
            # Classify intent
            result = await classifier.classify_intent(
                message=message,
                conversation_history=self.conversation_history,
                project_context=self.project_context
            )
            
            assert result.type == IntentType.EDIT_MILESTONE, \
                f"Message '{message}' should be classified as EDIT_MILESTONE"
            assert "milestone_identifier" in result.parameters, \
                f"Should extract milestone_identifier from '{message}'"
    
    @pytest.mark.asyncio
    async def test_delete_milestone_intent(self):
        """
        Test DELETE_MILESTONE intent.
        
        Validates: Requirements 6.1, 6.2, 6.3
        """
        test_cases = [
            ("remove the Testing milestone", {"milestone_identifier": "Testing"}),
            ("delete milestone 3", {"milestone_identifier": "3"}),
            ("get rid of Design Review", {"milestone_identifier": "Design Review"}),
        ]
        
        for message, expected_params in test_cases:
            # Create mock LLM service
            mock_llm_service = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text=self.create_mock_llm_response("DELETE_MILESTONE", expected_params))]
            mock_llm_service.client.messages.create = Mock(return_value=mock_response)
            mock_llm_service.model = "claude-3-5-sonnet-20241022"
            
            # Create classifier
            classifier = IntentClassifier(llm_service=mock_llm_service)
            
            # Classify intent
            result = await classifier.classify_intent(
                message=message,
                conversation_history=self.conversation_history,
                project_context=self.project_context
            )
            
            assert result.type == IntentType.DELETE_MILESTONE, \
                f"Message '{message}' should be classified as DELETE_MILESTONE"
            assert "milestone_identifier" in result.parameters, \
                f"Should extract milestone_identifier from '{message}'"
    
    @pytest.mark.asyncio
    async def test_mark_complete_intent(self):
        """
        Test MARK_COMPLETE intent.
        
        Validates: Requirements 6.1, 6.2, 6.3
        """
        test_cases = [
            ("I completed the Testing milestone", {"milestone_identifier": "Testing"}),
            ("mark Design Review as done", {"milestone_identifier": "Design Review"}),
            ("finished milestone 2", {"milestone_identifier": "2"}),
            ("the first milestone is complete", {"milestone_identifier": "first"}),
        ]
        
        for message, expected_params in test_cases:
            # Create mock LLM service
            mock_llm_service = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text=self.create_mock_llm_response("MARK_COMPLETE", expected_params))]
            mock_llm_service.client.messages.create = Mock(return_value=mock_response)
            mock_llm_service.model = "claude-3-5-sonnet-20241022"
            
            # Create classifier
            classifier = IntentClassifier(llm_service=mock_llm_service)
            
            # Classify intent
            result = await classifier.classify_intent(
                message=message,
                conversation_history=self.conversation_history,
                project_context=self.project_context
            )
            
            assert result.type == IntentType.MARK_COMPLETE, \
                f"Message '{message}' should be classified as MARK_COMPLETE"
            assert "milestone_identifier" in result.parameters, \
                f"Should extract milestone_identifier from '{message}'"
    
    @pytest.mark.asyncio
    async def test_ask_question_intent(self):
        """
        Test ASK_QUESTION intent.
        
        Validates: Requirements 6.1, 6.2
        """
        test_messages = [
            "how much time do I have left?",
            "what should I focus on next?",
            "when is my next milestone?",
            "am I on track?",
            "what's the status of my project?",
        ]
        
        for message in test_messages:
            # Create mock LLM service
            mock_llm_service = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text=self.create_mock_llm_response("ASK_QUESTION"))]
            mock_llm_service.client.messages.create = Mock(return_value=mock_response)
            mock_llm_service.model = "claude-3-5-sonnet-20241022"
            
            # Create classifier
            classifier = IntentClassifier(llm_service=mock_llm_service)
            
            # Classify intent
            result = await classifier.classify_intent(
                message=message,
                conversation_history=self.conversation_history,
                project_context=self.project_context
            )
            
            assert result.type == IntentType.ASK_QUESTION, \
                f"Message '{message}' should be classified as ASK_QUESTION"
    
    @pytest.mark.asyncio
    async def test_ambiguous_input_handling(self):
        """
        Test handling of ambiguous inputs.
        
        Validates: Requirements 6.4
        """
        ambiguous_messages = [
            "hmm",
            "maybe",
            "I don't know",
            "what?",
            "help",
        ]
        
        for message in ambiguous_messages:
            # Create mock LLM service that returns UNCLEAR
            mock_llm_service = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text=self.create_mock_llm_response("UNCLEAR", confidence=0.3))]
            mock_llm_service.client.messages.create = Mock(return_value=mock_response)
            mock_llm_service.model = "claude-3-5-sonnet-20241022"
            
            # Create classifier
            classifier = IntentClassifier(llm_service=mock_llm_service)
            
            # Classify intent
            result = await classifier.classify_intent(
                message=message,
                conversation_history=self.conversation_history,
                project_context=self.project_context
            )
            
            assert result.type == IntentType.UNCLEAR, \
                f"Ambiguous message '{message}' should be classified as UNCLEAR"
            assert result.confidence < 0.5, \
                f"Confidence should be low for ambiguous message '{message}'"
    
    @pytest.mark.asyncio
    async def test_llm_failure_returns_unclear(self):
        """
        Test that LLM failures gracefully return UNCLEAR intent.
        
        Validates: Requirements 6.1, 6.4
        """
        # Create mock LLM service that raises an exception
        mock_llm_service = Mock()
        mock_llm_service.client.messages.create = Mock(side_effect=Exception("API Error"))
        mock_llm_service.model = "claude-3-5-sonnet-20241022"
        
        # Create classifier
        classifier = IntentClassifier(llm_service=mock_llm_service)
        
        # Classify intent
        result = await classifier.classify_intent(
            message="show me my plan",
            conversation_history=self.conversation_history,
            project_context=self.project_context
        )
        
        assert result.type == IntentType.UNCLEAR, \
            "LLM failure should return UNCLEAR intent"
        assert result.confidence == 0.0, \
            "Confidence should be 0.0 for failed classification"
    
    @pytest.mark.asyncio
    async def test_invalid_json_response_returns_unclear(self):
        """
        Test that invalid JSON responses return UNCLEAR intent.
        
        Validates: Requirements 6.1, 6.4
        """
        # Create mock LLM service that returns invalid JSON
        mock_llm_service = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="This is not valid JSON")]
        mock_llm_service.client.messages.create = Mock(return_value=mock_response)
        mock_llm_service.model = "claude-3-5-sonnet-20241022"
        
        # Create classifier
        classifier = IntentClassifier(llm_service=mock_llm_service)
        
        # Classify intent
        result = await classifier.classify_intent(
            message="show me my plan",
            conversation_history=self.conversation_history,
            project_context=self.project_context
        )
        
        assert result.type == IntentType.UNCLEAR, \
            "Invalid JSON should return UNCLEAR intent"
        assert result.confidence == 0.0, \
            "Confidence should be 0.0 for invalid JSON"
    
    @pytest.mark.asyncio
    async def test_unknown_intent_type_returns_unclear(self):
        """
        Test that unknown intent types return UNCLEAR intent.
        
        Validates: Requirements 6.1, 6.4
        """
        # Create mock LLM service that returns unknown intent type
        mock_llm_service = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text=self.create_mock_llm_response("UNKNOWN_INTENT_TYPE"))]
        mock_llm_service.client.messages.create = Mock(return_value=mock_response)
        mock_llm_service.model = "claude-3-5-sonnet-20241022"
        
        # Create classifier
        classifier = IntentClassifier(llm_service=mock_llm_service)
        
        # Classify intent
        result = await classifier.classify_intent(
            message="show me my plan",
            conversation_history=self.conversation_history,
            project_context=self.project_context
        )
        
        assert result.type == IntentType.UNCLEAR, \
            "Unknown intent type should return UNCLEAR intent"
    
    @pytest.mark.asyncio
    async def test_conversation_history_included_in_prompt(self):
        """
        Test that conversation history is included in the classification prompt.
        
        Validates: Requirements 6.1
        """
        conversation_history = [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi! How can I help?'},
            {'role': 'user', 'content': 'I want to work on my project'},
        ]
        
        # Create mock LLM service
        mock_llm_service = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text=self.create_mock_llm_response("VIEW_PLAN"))]
        mock_llm_service.client.messages.create = Mock(return_value=mock_response)
        mock_llm_service.model = "claude-3-5-sonnet-20241022"
        
        # Create classifier
        classifier = IntentClassifier(llm_service=mock_llm_service)
        
        # Classify intent
        result = await classifier.classify_intent(
            message="show it to me",
            conversation_history=conversation_history,
            project_context=self.project_context
        )
        
        # Verify that the LLM was called
        assert mock_llm_service.client.messages.create.called, \
            "LLM should be called for classification"
        
        # Verify that the prompt includes conversation history
        call_args = mock_llm_service.client.messages.create.call_args
        messages = call_args[1]['messages']
        prompt = messages[0]['content']
        
        assert 'Hello' in prompt or 'conversation' in prompt.lower(), \
            "Prompt should include conversation history context"
    
    def test_intent_confidence_validation(self):
        """
        Test that Intent validates confidence is between 0 and 1.
        
        Validates: Requirements 6.1
        """
        # Valid confidence values
        Intent(type=IntentType.VIEW_PLAN, parameters={}, confidence=0.0)
        Intent(type=IntentType.VIEW_PLAN, parameters={}, confidence=0.5)
        Intent(type=IntentType.VIEW_PLAN, parameters={}, confidence=1.0)
        
        # Invalid confidence values
        with pytest.raises(ValueError):
            Intent(type=IntentType.VIEW_PLAN, parameters={}, confidence=-0.1)
        
        with pytest.raises(ValueError):
            Intent(type=IntentType.VIEW_PLAN, parameters={}, confidence=1.1)
