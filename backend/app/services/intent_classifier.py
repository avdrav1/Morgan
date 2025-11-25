"""
Intent Classification Service for Project Plan Management.

This service classifies user intents from natural language messages
and extracts relevant parameters for project plan operations.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID

from app.services.llm_service import LLMService
from app.models.project import Project
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class IntentType(Enum):
    """
    Types of intents that can be classified from user messages.
    
    Validates: Requirements 6.1, 6.2
    """
    VIEW_PLAN = "view_plan"
    EDIT_DEADLINE = "edit_deadline"
    ADD_MILESTONE = "add_milestone"
    EDIT_MILESTONE = "edit_milestone"
    DELETE_MILESTONE = "delete_milestone"
    MARK_COMPLETE = "mark_complete"
    ASK_QUESTION = "ask_question"
    UNCLEAR = "unclear"


@dataclass
class Intent:
    """
    Represents a classified user intent.
    
    Attributes:
        type: The type of intent (VIEW_PLAN, EDIT_DEADLINE, etc.)
        parameters: Extracted entities (dates, milestone names, etc.)
        confidence: Confidence score 0-1
        
    Validates: Requirements 6.1, 6.2
    """
    type: IntentType
    parameters: Dict[str, Any]
    confidence: float
    
    def __post_init__(self):
        """Validate confidence is between 0 and 1."""
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")


class IntentClassifier:
    """
    Classifies user intent from natural language messages.
    
    Uses the LLM service to understand user intent and extract
    relevant parameters for project plan operations.
    
    Validates: Requirements 6.1, 6.2, 6.3, 6.4
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Initialize the intent classifier.
        
        Args:
            llm_service: Optional LLM service instance (uses singleton if not provided)
        """
        from app.services.llm_service import llm_service as default_llm
        self.llm_service = llm_service or default_llm
    
    async def classify_intent(
        self,
        message: str,
        conversation_history: List[Dict[str, str]],
        project_context: Dict[str, Any]
    ) -> Intent:
        """
        Classify the user's intent from their message.
        
        Uses the LLM service to parse natural language and determine
        what the user wants to do with their project plan.
        
        Args:
            message: The user's message
            conversation_history: Recent conversation context
            project_context: Current project information
            
        Returns:
            Intent object with type and extracted parameters
            
        Validates: Requirements 6.1, 6.2, 6.3, 6.4
        """
        logger.info(
            "Classifying intent",
            extra={
                'extra_fields': {
                    'event': 'classify_intent',
                    'message_length': len(message),
                    'has_conversation_history': len(conversation_history) > 0,
                    'project_id': project_context.get('project_id')
                }
            }
        )
        
        # Build the LLM prompt for intent classification
        prompt = self._build_classification_prompt(
            message=message,
            conversation_history=conversation_history,
            project_context=project_context
        )
        
        # Call LLM service
        try:
            # Log LLM prompt (PII-redacted)
            logger.info(
                "Calling LLM for intent classification",
                extra={
                    'extra_fields': {
                        'event': 'llm_intent_classification_request',
                        'prompt_length': len(prompt),
                        'project_id': project_context.get('project_id'),
                        'has_conversation_history': len(conversation_history) > 0
                    }
                }
            )
            
            response = await self._call_llm_for_classification(prompt)
            
            # Log LLM response (PII-redacted)
            logger.info(
                "LLM intent classification response received",
                extra={
                    'extra_fields': {
                        'event': 'llm_intent_classification_response',
                        'response_length': len(response),
                        'project_id': project_context.get('project_id')
                    }
                }
            )
            
            # Parse the response
            intent = self._parse_llm_response(response)
            
            logger.info(
                "Intent classified",
                extra={
                    'extra_fields': {
                        'event': 'intent_classified',
                        'intent_type': intent.type.value,
                        'confidence': intent.confidence,
                        'parameters': list(intent.parameters.keys()),
                        'project_id': project_context.get('project_id')
                    }
                }
            )
            
            return intent
            
        except Exception as e:
            logger.error(
                "Failed to classify intent",
                extra={
                    'extra_fields': {
                        'event': 'intent_classification_failed',
                        'error': str(e),
                        'error_type': type(e).__name__,
                        'project_id': project_context.get('project_id')
                    }
                },
                exc_info=True
            )
            
            # Return UNCLEAR intent on failure
            return Intent(
                type=IntentType.UNCLEAR,
                parameters={},
                confidence=0.0
            )
    
    def _build_classification_prompt(
        self,
        message: str,
        conversation_history: List[Dict[str, str]],
        project_context: Dict[str, Any]
    ) -> str:
        """
        Build the prompt for LLM intent classification.
        
        Args:
            message: The user's message
            conversation_history: Recent conversation context
            project_context: Current project information
            
        Returns:
            The formatted prompt string
        """
        # Format conversation history
        history_text = ""
        if conversation_history:
            history_lines = []
            for msg in conversation_history[-5:]:  # Last 5 messages
                role = msg.get('role', 'user')
                content = msg.get('content', msg.get('message', ''))
                history_lines.append(f"{role}: {content}")
            history_text = "\n".join(history_lines)
        
        # Format project context
        project_name = project_context.get('project_name', 'Unknown Project')
        project_goal = project_context.get('project_goal', 'Not specified')
        deadline = project_context.get('deadline', 'Not set')
        
        prompt = f"""You are analyzing a message from a user about their project plan.

Project Context:
- Project: {project_name}
- Goal: {project_goal}
- Deadline: {deadline}

Recent Conversation:
{history_text if history_text else "No previous conversation"}

User Message: "{message}"

Classify the user's intent into ONE of these categories:
- VIEW_PLAN: User wants to see their project plan
- EDIT_DEADLINE: User wants to change the project deadline
- ADD_MILESTONE: User wants to add a new milestone
- EDIT_MILESTONE: User wants to modify an existing milestone
- DELETE_MILESTONE: User wants to remove a milestone
- MARK_COMPLETE: User wants to mark a milestone as complete
- ASK_QUESTION: User has a question about their project
- UNCLEAR: Intent cannot be determined

Extract any relevant parameters:
- For EDIT_DEADLINE: extract "new_deadline" (date string)
- For ADD_MILESTONE: extract "milestone_title" and "target_date"
- For EDIT_MILESTONE: extract "milestone_identifier" and any changes
- For DELETE_MILESTONE: extract "milestone_identifier"
- For MARK_COMPLETE: extract "milestone_identifier"

Return a JSON object with this structure:
{{
  "intent_type": "one of the intent types above",
  "parameters": {{
    "param_name": "param_value"
  }},
  "confidence": 0.95
}}

Confidence scoring:
- 0.9-1.0: Very clear intent with explicit keywords
- 0.7-0.9: Clear intent but less explicit
- 0.5-0.7: Probable intent but some ambiguity
- 0.0-0.5: Unclear or ambiguous

Return ONLY the JSON object, no other text."""
        
        return prompt
    
    async def _call_llm_for_classification(self, prompt: str) -> str:
        """
        Call the LLM service for intent classification.
        
        Args:
            prompt: The classification prompt
            
        Returns:
            The LLM response as a string
        """
        # Use the LLM client directly
        response = self.llm_service.client.messages.create(
            model=self.llm_service.model,
            max_tokens=500,
            system="You are an intent classification system. Analyze user messages and classify their intent accurately.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    
    def _parse_llm_response(self, response: str) -> Intent:
        """
        Parse the LLM response into an Intent object.
        
        Args:
            response: The LLM response string
            
        Returns:
            Parsed Intent object
        """
        import json
        
        # Remove markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            # Remove first and last lines (code block markers)
            response = "\n".join(lines[1:-1])
        
        # Parse JSON
        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse LLM response as JSON",
                extra={
                    'extra_fields': {
                        'event': 'json_parse_error',
                        'error': str(e),
                        'response': response[:200]
                    }
                }
            )
            # Return UNCLEAR intent
            return Intent(
                type=IntentType.UNCLEAR,
                parameters={},
                confidence=0.0
            )
        
        # Extract fields
        intent_type_str = data.get('intent_type', 'UNCLEAR')
        parameters = data.get('parameters', {})
        confidence = data.get('confidence', 0.5)
        
        # Convert intent type string to enum
        try:
            intent_type = IntentType[intent_type_str]
        except KeyError:
            logger.warning(
                f"Unknown intent type: {intent_type_str}",
                extra={
                    'extra_fields': {
                        'event': 'unknown_intent_type',
                        'intent_type_str': intent_type_str
                    }
                }
            )
            intent_type = IntentType.UNCLEAR
        
        return Intent(
            type=intent_type,
            parameters=parameters,
            confidence=confidence
        )
