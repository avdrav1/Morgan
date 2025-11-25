"""
Project Plan Conversation Manager for managing conversation state and history.

This service handles conversation state tracking, history management,
and pending confirmation handling for project plan interactions.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.project_plan_conversation import ProjectPlanConversation
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class ProjectPlanConversationManager:
    """
    Manages conversation context and state for project plan interactions.
    
    Handles conversation history (last 10 messages), pending confirmations,
    and conversation state tracking.
    
    Validates: Requirements 2.2, 3.4, 4.3
    """
    
    MAX_HISTORY_LENGTH = 10
    
    def __init__(self, db: Session):
        """
        Initialize the conversation manager.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def get_or_create_conversation(
        self,
        user_id: UUID,
        project_id: UUID
    ) -> ProjectPlanConversation:
        """
        Get or create a conversation for a user and project.
        
        Args:
            user_id: UUID of the user
            project_id: UUID of the project
            
        Returns:
            ProjectPlanConversation instance
        """
        conversation = (
            self.db.query(ProjectPlanConversation)
            .filter(
                and_(
                    ProjectPlanConversation.user_id == user_id,
                    ProjectPlanConversation.project_id == project_id
                )
            )
            .first()
        )
        
        if not conversation:
            logger.info(
                "Creating new conversation",
                extra={
                    'extra_fields': {
                        'event': 'create_conversation',
                        'user_id': str(user_id),
                        'project_id': str(project_id)
                    }
                }
            )
            
            conversation = ProjectPlanConversation(
                user_id=user_id,
                project_id=project_id,
                conversation_history=[]
            )
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)
        
        return conversation
    
    def get_conversation_history(
        self,
        user_id: UUID,
        project_id: UUID,
        max_messages: int = MAX_HISTORY_LENGTH
    ) -> List[Dict[str, Any]]:
        """
        Retrieve conversation history for a user and project.
        
        Returns the last N messages (default 10) in chronological order.
        
        Args:
            user_id: UUID of the user
            project_id: UUID of the project
            max_messages: Maximum number of messages to retrieve
            
        Returns:
            List of conversation messages with role, content, and timestamp
            
        Validates: Requirements 2.2, 6.1
        """
        conversation = self.get_or_create_conversation(user_id, project_id)
        
        # Get the conversation history
        history = conversation.conversation_history or []
        
        # Return the last max_messages
        return history[-max_messages:]
    
    def add_message(
        self,
        user_id: UUID,
        project_id: UUID,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a message to the conversation history.
        
        Maintains a maximum of MAX_HISTORY_LENGTH messages by removing
        oldest messages when the limit is exceeded.
        
        Args:
            user_id: UUID of the user
            project_id: UUID of the project
            role: Role of the speaker ("user" or "assistant")
            content: Message content
            metadata: Optional metadata about the message
            
        Validates: Requirements 2.2
        """
        conversation = self.get_or_create_conversation(user_id, project_id)
        
        # Refresh to get latest data from database
        self.db.refresh(conversation)
        
        # Get existing history - make a copy to avoid mutation issues
        history = list(conversation.conversation_history or [])
        
        # Create message entry
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if metadata:
            message["metadata"] = metadata
        
        # Add message to history
        history.append(message)
        
        # Trim to MAX_HISTORY_LENGTH
        if len(history) > self.MAX_HISTORY_LENGTH:
            history = history[-self.MAX_HISTORY_LENGTH:]
        
        # Update conversation - force SQLAlchemy to detect the change
        conversation.conversation_history = history
        conversation.updated_at = datetime.utcnow()
        
        # Mark the field as modified to ensure SQLAlchemy updates it
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(conversation, "conversation_history")
        
        self.db.commit()
        self.db.refresh(conversation)
        
        logger.debug(
            "Message added to conversation",
            extra={
                'extra_fields': {
                    'event': 'message_added',
                    'user_id': str(user_id),
                    'project_id': str(project_id),
                    'role': role,
                    'history_length': len(history)
                }
            }
        )
    
    def set_last_intent(
        self,
        user_id: UUID,
        project_id: UUID,
        intent: str
    ) -> None:
        """
        Set the last classified intent for the conversation.
        
        Args:
            user_id: UUID of the user
            project_id: UUID of the project
            intent: The intent type (e.g., "VIEW_PLAN", "EDIT_DEADLINE")
        """
        conversation = self.get_or_create_conversation(user_id, project_id)
        
        conversation.last_intent = intent
        conversation.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        logger.debug(
            "Last intent updated",
            extra={
                'extra_fields': {
                    'event': 'intent_updated',
                    'user_id': str(user_id),
                    'project_id': str(project_id),
                    'intent': intent
                }
            }
        )
    
    def get_last_intent(
        self,
        user_id: UUID,
        project_id: UUID
    ) -> Optional[str]:
        """
        Get the last classified intent for the conversation.
        
        Args:
            user_id: UUID of the user
            project_id: UUID of the project
            
        Returns:
            The last intent type, or None if no intent has been set
        """
        conversation = self.get_or_create_conversation(user_id, project_id)
        return conversation.last_intent
    
    def set_pending_confirmation(
        self,
        user_id: UUID,
        project_id: UUID,
        confirmation_type: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Set a pending confirmation for the conversation.
        
        Used when the system needs user confirmation before applying changes
        (e.g., deadline adjustments, milestone deletions).
        
        Args:
            user_id: UUID of the user
            project_id: UUID of the project
            confirmation_type: Type of confirmation needed (e.g., "deadline_change", "delete_milestone")
            data: Data about the pending change
            
        Validates: Requirements 3.4, 4.3
        """
        conversation = self.get_or_create_conversation(user_id, project_id)
        
        pending = {
            "type": confirmation_type,
            "data": data,
            "created_at": datetime.utcnow().isoformat()
        }
        
        conversation.pending_confirmation = pending
        conversation.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        logger.info(
            "Pending confirmation set",
            extra={
                'extra_fields': {
                    'event': 'pending_confirmation_set',
                    'user_id': str(user_id),
                    'project_id': str(project_id),
                    'confirmation_type': confirmation_type
                }
            }
        )
    
    def get_pending_confirmation(
        self,
        user_id: UUID,
        project_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get the pending confirmation for the conversation.
        
        Args:
            user_id: UUID of the user
            project_id: UUID of the project
            
        Returns:
            Pending confirmation data, or None if no confirmation is pending
            
        Validates: Requirements 3.4, 4.3
        """
        conversation = self.get_or_create_conversation(user_id, project_id)
        return conversation.pending_confirmation
    
    def clear_pending_confirmation(
        self,
        user_id: UUID,
        project_id: UUID
    ) -> None:
        """
        Clear the pending confirmation for the conversation.
        
        Called after the user confirms or rejects the pending change.
        
        Args:
            user_id: UUID of the user
            project_id: UUID of the project
        """
        conversation = self.get_or_create_conversation(user_id, project_id)
        
        conversation.pending_confirmation = None
        conversation.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        logger.debug(
            "Pending confirmation cleared",
            extra={
                'extra_fields': {
                    'event': 'pending_confirmation_cleared',
                    'user_id': str(user_id),
                    'project_id': str(project_id)
                }
            }
        )
    
    def clear_conversation(
        self,
        user_id: UUID,
        project_id: UUID
    ) -> None:
        """
        Clear the conversation history and state.
        
        Useful for starting fresh or after completing a major action.
        
        Args:
            user_id: UUID of the user
            project_id: UUID of the project
        """
        conversation = self.get_or_create_conversation(user_id, project_id)
        
        conversation.conversation_history = []
        conversation.last_intent = None
        conversation.pending_confirmation = None
        conversation.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        logger.info(
            "Conversation cleared",
            extra={
                'extra_fields': {
                    'event': 'conversation_cleared',
                    'user_id': str(user_id),
                    'project_id': str(project_id)
                }
            }
        )
