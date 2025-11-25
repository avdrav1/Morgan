"""
Project Plan Metrics Collection Service.

This service collects and tracks metrics for project plan management,
including request types, conversation patterns, and error rates.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.project_plan_conversation import ProjectPlanConversation
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class ProjectPlanMetrics:
    """
    Service for collecting and tracking project plan metrics.
    
    Tracks:
    - Common request types (intent distribution)
    - Conversation patterns (message counts, session lengths)
    - Error rates by intent type
    
    Validates: Requirements 10.5
    """
    
    def __init__(self, db: Session):
        """
        Initialize the metrics service.
        
        Args:
            db: Database session
        """
        self.db = db
        # In-memory metrics storage (could be replaced with Redis or similar)
        self._intent_counts = defaultdict(int)
        self._error_counts = defaultdict(int)
        self._conversation_metrics = defaultdict(lambda: {
            'message_count': 0,
            'session_start': None,
            'last_activity': None
        })
    
    def record_intent(self, intent_type: str, user_id: UUID, project_id: UUID) -> None:
        """
        Record an intent classification.
        
        Args:
            intent_type: The classified intent type
            user_id: UUID of the user
            project_id: UUID of the project
            
        Validates: Requirements 10.5
        """
        self._intent_counts[intent_type] += 1
        
        logger.info(
            "Intent recorded for metrics",
            extra={
                'extra_fields': {
                    'event': 'metrics_intent_recorded',
                    'intent_type': intent_type,
                    'user_id': str(user_id),
                    'project_id': str(project_id),
                    'total_count': self._intent_counts[intent_type]
                }
            }
        )
    
    def record_error(
        self,
        intent_type: str,
        error_type: str,
        user_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None
    ) -> None:
        """
        Record an error occurrence.
        
        Args:
            intent_type: The intent type where error occurred
            error_type: Type of error (e.g., 'LLMError', 'ValidationError')
            user_id: Optional UUID of the user
            project_id: Optional UUID of the project
            
        Validates: Requirements 10.5
        """
        error_key = f"{intent_type}:{error_type}"
        self._error_counts[error_key] += 1
        
        logger.error(
            "Error recorded for metrics",
            extra={
                'extra_fields': {
                    'event': 'metrics_error_recorded',
                    'intent_type': intent_type,
                    'error_type': error_type,
                    'user_id': str(user_id) if user_id else None,
                    'project_id': str(project_id) if project_id else None,
                    'total_count': self._error_counts[error_key]
                }
            }
        )
    
    def record_conversation_activity(
        self,
        user_id: UUID,
        project_id: UUID,
        message_count: int = 1
    ) -> None:
        """
        Record conversation activity.
        
        Args:
            user_id: UUID of the user
            project_id: UUID of the project
            message_count: Number of messages in this activity (default 1)
            
        Validates: Requirements 10.5
        """
        conversation_key = f"{user_id}:{project_id}"
        
        if self._conversation_metrics[conversation_key]['session_start'] is None:
            self._conversation_metrics[conversation_key]['session_start'] = datetime.utcnow()
        
        self._conversation_metrics[conversation_key]['message_count'] += message_count
        self._conversation_metrics[conversation_key]['last_activity'] = datetime.utcnow()
        
        logger.debug(
            "Conversation activity recorded",
            extra={
                'extra_fields': {
                    'event': 'metrics_conversation_activity',
                    'user_id': str(user_id),
                    'project_id': str(project_id),
                    'message_count': self._conversation_metrics[conversation_key]['message_count']
                }
            }
        )
    
    def get_intent_distribution(self) -> Dict[str, int]:
        """
        Get the distribution of intent types.
        
        Returns:
            Dictionary mapping intent types to counts
            
        Validates: Requirements 10.5
        """
        return dict(self._intent_counts)
    
    def get_error_rates(self) -> Dict[str, Dict[str, Any]]:
        """
        Get error rates by intent type.
        
        Returns:
            Dictionary with error statistics by intent type
            
        Validates: Requirements 10.5
        """
        error_stats = {}
        
        for error_key, count in self._error_counts.items():
            intent_type, error_type = error_key.split(':', 1)
            
            if intent_type not in error_stats:
                error_stats[intent_type] = {
                    'total_errors': 0,
                    'error_types': {}
                }
            
            error_stats[intent_type]['total_errors'] += count
            error_stats[intent_type]['error_types'][error_type] = count
            
            # Calculate error rate if we have intent counts
            if intent_type in self._intent_counts:
                total_requests = self._intent_counts[intent_type]
                error_stats[intent_type]['error_rate'] = (
                    error_stats[intent_type]['total_errors'] / total_requests
                    if total_requests > 0 else 0
                )
        
        return error_stats
    
    def get_conversation_patterns(self) -> Dict[str, Any]:
        """
        Get conversation pattern statistics.
        
        Returns:
            Dictionary with conversation statistics
            
        Validates: Requirements 10.5
        """
        if not self._conversation_metrics:
            return {
                'total_conversations': 0,
                'average_messages_per_conversation': 0,
                'average_session_duration_minutes': 0
            }
        
        total_conversations = len(self._conversation_metrics)
        total_messages = sum(
            metrics['message_count']
            for metrics in self._conversation_metrics.values()
        )
        
        # Calculate session durations
        session_durations = []
        for metrics in self._conversation_metrics.values():
            if metrics['session_start'] and metrics['last_activity']:
                duration = (metrics['last_activity'] - metrics['session_start']).total_seconds() / 60
                session_durations.append(duration)
        
        avg_duration = (
            sum(session_durations) / len(session_durations)
            if session_durations else 0
        )
        
        return {
            'total_conversations': total_conversations,
            'total_messages': total_messages,
            'average_messages_per_conversation': total_messages / total_conversations if total_conversations > 0 else 0,
            'average_session_duration_minutes': avg_duration,
            'active_conversations': sum(
                1 for metrics in self._conversation_metrics.values()
                if metrics['last_activity'] and
                (datetime.utcnow() - metrics['last_activity']).total_seconds() < 3600  # Active in last hour
            )
        }
    
    def get_database_conversation_stats(
        self,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get conversation statistics from the database.
        
        Args:
            since: Optional datetime to filter conversations since
            
        Returns:
            Dictionary with database conversation statistics
            
        Validates: Requirements 10.5
        """
        query = self.db.query(ProjectPlanConversation)
        
        if since:
            query = query.filter(ProjectPlanConversation.updated_at >= since)
        
        conversations = query.all()
        
        if not conversations:
            return {
                'total_conversations': 0,
                'conversations_with_history': 0,
                'average_history_length': 0,
                'conversations_with_pending_confirmations': 0
            }
        
        total = len(conversations)
        with_history = sum(
            1 for c in conversations
            if c.conversation_history and len(c.conversation_history) > 0
        )
        
        history_lengths = [
            len(c.conversation_history)
            for c in conversations
            if c.conversation_history
        ]
        
        avg_history = (
            sum(history_lengths) / len(history_lengths)
            if history_lengths else 0
        )
        
        with_pending = sum(
            1 for c in conversations
            if c.pending_confirmation is not None
        )
        
        return {
            'total_conversations': total,
            'conversations_with_history': with_history,
            'average_history_length': avg_history,
            'conversations_with_pending_confirmations': with_pending,
            'since': since.isoformat() if since else None
        }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all metrics in a single call.
        
        Returns:
            Dictionary with all metrics
            
        Validates: Requirements 10.5
        """
        return {
            'intent_distribution': self.get_intent_distribution(),
            'error_rates': self.get_error_rates(),
            'conversation_patterns': self.get_conversation_patterns(),
            'database_stats': self.get_database_conversation_stats(
                since=datetime.utcnow() - timedelta(days=7)  # Last 7 days
            ),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def reset_metrics(self) -> None:
        """
        Reset all in-memory metrics.
        
        Useful for testing or periodic resets.
        """
        self._intent_counts.clear()
        self._error_counts.clear()
        self._conversation_metrics.clear()
        
        logger.info(
            "Metrics reset",
            extra={
                'extra_fields': {
                    'event': 'metrics_reset',
                    'timestamp': datetime.utcnow().isoformat()
                }
            }
        )


# Global metrics instance (singleton pattern)
_metrics_instance: Optional[ProjectPlanMetrics] = None


def get_metrics_instance(db: Session) -> ProjectPlanMetrics:
    """
    Get or create the global metrics instance.
    
    Args:
        db: Database session
        
    Returns:
        ProjectPlanMetrics instance
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = ProjectPlanMetrics(db)
    return _metrics_instance
