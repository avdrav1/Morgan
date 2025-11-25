"""
Tests for project plan metrics collection.

Validates: Requirements 10.5
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.project_plan_metrics import ProjectPlanMetrics
from app.models.project_plan_conversation import ProjectPlanConversation


def test_record_intent(db_session):
    """Test recording intent classifications."""
    metrics = ProjectPlanMetrics(db_session)
    user_id = uuid4()
    project_id = uuid4()
    
    # Record some intents
    metrics.record_intent("VIEW_PLAN", user_id, project_id)
    metrics.record_intent("VIEW_PLAN", user_id, project_id)
    metrics.record_intent("EDIT_DEADLINE", user_id, project_id)
    
    # Get distribution
    distribution = metrics.get_intent_distribution()
    
    assert distribution["VIEW_PLAN"] == 2
    assert distribution["EDIT_DEADLINE"] == 1


def test_record_error(db_session):
    """Test recording errors by intent type."""
    metrics = ProjectPlanMetrics(db_session)
    user_id = uuid4()
    project_id = uuid4()
    
    # Record some errors
    metrics.record_error("VIEW_PLAN", "LLMError", user_id, project_id)
    metrics.record_error("VIEW_PLAN", "ValidationError", user_id, project_id)
    metrics.record_error("EDIT_DEADLINE", "LLMError", user_id, project_id)
    
    # Get error rates
    error_rates = metrics.get_error_rates()
    
    assert "VIEW_PLAN" in error_rates
    assert error_rates["VIEW_PLAN"]["total_errors"] == 2
    assert error_rates["VIEW_PLAN"]["error_types"]["LLMError"] == 1
    assert error_rates["VIEW_PLAN"]["error_types"]["ValidationError"] == 1


def test_error_rate_calculation(db_session):
    """Test error rate calculation with intent counts."""
    metrics = ProjectPlanMetrics(db_session)
    user_id = uuid4()
    project_id = uuid4()
    
    # Record intents and errors
    for _ in range(10):
        metrics.record_intent("VIEW_PLAN", user_id, project_id)
    
    metrics.record_error("VIEW_PLAN", "LLMError", user_id, project_id)
    metrics.record_error("VIEW_PLAN", "LLMError", user_id, project_id)
    
    # Get error rates
    error_rates = metrics.get_error_rates()
    
    assert "VIEW_PLAN" in error_rates
    assert error_rates["VIEW_PLAN"]["error_rate"] == 0.2  # 2 errors out of 10 requests


def test_record_conversation_activity(db_session):
    """Test recording conversation activity."""
    metrics = ProjectPlanMetrics(db_session)
    user_id = uuid4()
    project_id = uuid4()
    
    # Record activity
    metrics.record_conversation_activity(user_id, project_id, message_count=1)
    metrics.record_conversation_activity(user_id, project_id, message_count=2)
    
    # Get patterns
    patterns = metrics.get_conversation_patterns()
    
    assert patterns["total_conversations"] == 1
    assert patterns["total_messages"] == 3
    assert patterns["average_messages_per_conversation"] == 3.0


def test_conversation_patterns_multiple_conversations(db_session):
    """Test conversation patterns with multiple conversations."""
    metrics = ProjectPlanMetrics(db_session)
    
    # Create multiple conversations
    user1_id = uuid4()
    project1_id = uuid4()
    user2_id = uuid4()
    project2_id = uuid4()
    
    metrics.record_conversation_activity(user1_id, project1_id, message_count=5)
    metrics.record_conversation_activity(user2_id, project2_id, message_count=3)
    
    patterns = metrics.get_conversation_patterns()
    
    assert patterns["total_conversations"] == 2
    assert patterns["total_messages"] == 8
    assert patterns["average_messages_per_conversation"] == 4.0


def test_get_all_metrics(db_session):
    """Test getting all metrics at once."""
    metrics = ProjectPlanMetrics(db_session)
    user_id = uuid4()
    project_id = uuid4()
    
    # Record some data
    metrics.record_intent("VIEW_PLAN", user_id, project_id)
    metrics.record_error("VIEW_PLAN", "LLMError", user_id, project_id)
    metrics.record_conversation_activity(user_id, project_id)
    
    # Get all metrics
    all_metrics = metrics.get_all_metrics()
    
    assert "intent_distribution" in all_metrics
    assert "error_rates" in all_metrics
    assert "conversation_patterns" in all_metrics
    assert "database_stats" in all_metrics
    assert "timestamp" in all_metrics


def test_reset_metrics(db_session):
    """Test resetting metrics."""
    metrics = ProjectPlanMetrics(db_session)
    user_id = uuid4()
    project_id = uuid4()
    
    # Record some data
    metrics.record_intent("VIEW_PLAN", user_id, project_id)
    metrics.record_error("VIEW_PLAN", "LLMError", user_id, project_id)
    metrics.record_conversation_activity(user_id, project_id)
    
    # Reset
    metrics.reset_metrics()
    
    # Verify everything is cleared
    assert len(metrics.get_intent_distribution()) == 0
    assert len(metrics.get_error_rates()) == 0
    patterns = metrics.get_conversation_patterns()
    assert patterns["total_conversations"] == 0


def test_database_conversation_stats(db_session, test_user, test_project):
    """Test getting conversation stats from database."""
    metrics = ProjectPlanMetrics(db_session)
    
    # Create some conversations in the database
    conv1 = ProjectPlanConversation(
        user_id=test_user.id,
        project_id=test_project.id,
        conversation_history=[
            {"role": "user", "content": "test1"},
            {"role": "assistant", "content": "response1"}
        ]
    )
    
    conv2 = ProjectPlanConversation(
        user_id=test_user.id,
        project_id=test_project.id,
        conversation_history=[
            {"role": "user", "content": "test2"}
        ],
        pending_confirmation={"type": "test"}
    )
    
    db_session.add(conv1)
    db_session.add(conv2)
    db_session.commit()
    
    # Get stats
    stats = metrics.get_database_conversation_stats()
    
    assert stats["total_conversations"] == 2
    assert stats["conversations_with_history"] == 2
    assert stats["average_history_length"] == 1.5  # (2 + 1) / 2
    assert stats["conversations_with_pending_confirmations"] == 1


def test_database_conversation_stats_with_time_filter(db_session, test_user, test_project):
    """Test getting conversation stats with time filter."""
    metrics = ProjectPlanMetrics(db_session)
    
    # Create an old conversation
    old_conv = ProjectPlanConversation(
        user_id=test_user.id,
        project_id=test_project.id,
        conversation_history=[{"role": "user", "content": "old"}]
    )
    old_conv.updated_at = datetime.utcnow() - timedelta(days=10)
    
    # Create a recent conversation
    recent_conv = ProjectPlanConversation(
        user_id=test_user.id,
        project_id=test_project.id,
        conversation_history=[{"role": "user", "content": "recent"}]
    )
    
    db_session.add(old_conv)
    db_session.add(recent_conv)
    db_session.commit()
    
    # Get stats for last 7 days
    since = datetime.utcnow() - timedelta(days=7)
    stats = metrics.get_database_conversation_stats(since=since)
    
    # Should only count the recent conversation
    assert stats["total_conversations"] == 1


def test_active_conversations_tracking(db_session):
    """Test tracking of active conversations."""
    metrics = ProjectPlanMetrics(db_session)
    
    # Create an active conversation (recent activity)
    user1_id = uuid4()
    project1_id = uuid4()
    metrics.record_conversation_activity(user1_id, project1_id)
    
    # Create an inactive conversation (old activity)
    user2_id = uuid4()
    project2_id = uuid4()
    conversation_key = f"{user2_id}:{project2_id}"
    metrics._conversation_metrics[conversation_key] = {
        'message_count': 5,
        'session_start': datetime.utcnow() - timedelta(hours=2),
        'last_activity': datetime.utcnow() - timedelta(hours=2)
    }
    
    patterns = metrics.get_conversation_patterns()
    
    # Only the recent conversation should be active
    assert patterns["active_conversations"] == 1


def test_intent_distribution_multiple_types(db_session):
    """Test intent distribution with multiple intent types."""
    metrics = ProjectPlanMetrics(db_session)
    user_id = uuid4()
    project_id = uuid4()
    
    # Record various intents
    intents = [
        "VIEW_PLAN", "VIEW_PLAN", "VIEW_PLAN",
        "EDIT_DEADLINE", "EDIT_DEADLINE",
        "ADD_MILESTONE",
        "MARK_COMPLETE", "MARK_COMPLETE", "MARK_COMPLETE", "MARK_COMPLETE",
        "ASK_QUESTION"
    ]
    
    for intent in intents:
        metrics.record_intent(intent, user_id, project_id)
    
    distribution = metrics.get_intent_distribution()
    
    assert distribution["VIEW_PLAN"] == 3
    assert distribution["EDIT_DEADLINE"] == 2
    assert distribution["ADD_MILESTONE"] == 1
    assert distribution["MARK_COMPLETE"] == 4
    assert distribution["ASK_QUESTION"] == 1
    assert sum(distribution.values()) == len(intents)


def test_error_tracking_without_intents(db_session):
    """Test error tracking when no intents have been recorded."""
    metrics = ProjectPlanMetrics(db_session)
    user_id = uuid4()
    project_id = uuid4()
    
    # Record errors without recording intents
    metrics.record_error("VIEW_PLAN", "LLMError", user_id, project_id)
    
    error_rates = metrics.get_error_rates()
    
    assert "VIEW_PLAN" in error_rates
    assert error_rates["VIEW_PLAN"]["total_errors"] == 1
    # Error rate should not be calculated if no intents recorded
    assert "error_rate" not in error_rates["VIEW_PLAN"]
