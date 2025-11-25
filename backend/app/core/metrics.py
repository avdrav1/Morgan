"""
Metrics tracking for monitoring system performance and user engagement.

Tracks:
- Check-in response rate (Requirements: 3.4, 3.5)
- Message delivery success rate (Requirements: 7.4)
- Task completion rate
- Rescheduling frequency
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import threading
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """Thread-safe metrics collector for tracking system performance."""
    
    def __init__(self):
        """Initialize metrics collector with thread-safe counters."""
        self._lock = threading.Lock()
        self._metrics = defaultdict(lambda: defaultdict(int))
        self._timers = defaultdict(list)
        
    def increment(self, metric_name: str, labels: Optional[Dict[str, str]] = None, value: int = 1) -> None:
        """
        Increment a counter metric.
        
        Args:
            metric_name: Name of the metric
            labels: Optional labels for the metric (e.g., {'status': 'success'})
            value: Amount to increment by (default: 1)
        """
        with self._lock:
            label_key = self._make_label_key(labels) if labels else "default"
            self._metrics[metric_name][label_key] += value
            
        logger.debug(
            f"Metric incremented: {metric_name}",
            extra={
                'extra_fields': {
                    'metric_name': metric_name,
                    'labels': labels or {},
                    'value': value,
                }
            }
        )
    
    def record_duration(self, metric_name: str, duration_ms: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Record a duration metric.
        
        Args:
            metric_name: Name of the metric
            duration_ms: Duration in milliseconds
            labels: Optional labels for the metric
        """
        with self._lock:
            label_key = self._make_label_key(labels) if labels else "default"
            self._timers[metric_name].append({
                'duration_ms': duration_ms,
                'labels': label_key,
                'timestamp': datetime.utcnow()
            })
            
        logger.debug(
            f"Duration recorded: {metric_name}",
            extra={
                'extra_fields': {
                    'metric_name': metric_name,
                    'duration_ms': duration_ms,
                    'labels': labels or {},
                }
            }
        )
    
    def get_metric(self, metric_name: str, labels: Optional[Dict[str, str]] = None) -> int:
        """
        Get current value of a counter metric.
        
        Args:
            metric_name: Name of the metric
            labels: Optional labels to filter by
            
        Returns:
            Current value of the metric
        """
        with self._lock:
            if labels:
                label_key = self._make_label_key(labels)
                return self._metrics[metric_name].get(label_key, 0)
            else:
                # Return sum of all labels for this metric
                return sum(self._metrics[metric_name].values())
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all metrics as a dictionary.
        
        Returns:
            Dictionary of all metrics with their current values
        """
        with self._lock:
            return {
                'counters': dict(self._metrics),
                'timers': dict(self._timers),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._metrics.clear()
            self._timers.clear()
    
    @staticmethod
    def _make_label_key(labels: Dict[str, str]) -> str:
        """Create a consistent key from labels dictionary."""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))


# Global metrics collector instance
metrics = MetricsCollector()


# Convenience functions for common metrics

def track_check_in_sent(user_id: str, project_id: str) -> None:
    """Track that a check-in was sent."""
    metrics.increment('check_ins_sent', {'user_id': user_id, 'project_id': project_id})
    logger.info(
        "Check-in sent",
        extra={
            'extra_fields': {
                'metric': 'check_ins_sent',
                'user_id': user_id,
                'project_id': project_id,
            }
        }
    )


def track_check_in_responded(user_id: str, project_id: str, response_time_minutes: Optional[int] = None) -> None:
    """Track that a user responded to a check-in."""
    metrics.increment('check_ins_responded', {'user_id': user_id, 'project_id': project_id})
    
    extra_fields = {
        'metric': 'check_ins_responded',
        'user_id': user_id,
        'project_id': project_id,
    }
    
    if response_time_minutes is not None:
        metrics.record_duration('check_in_response_time', response_time_minutes * 60 * 1000, {'user_id': user_id})
        extra_fields['response_time_minutes'] = response_time_minutes
    
    logger.info(
        "Check-in responded",
        extra={'extra_fields': extra_fields}
    )


def track_check_in_missed(user_id: str, project_id: str) -> None:
    """Track that a check-in was missed (no response)."""
    metrics.increment('check_ins_missed', {'user_id': user_id, 'project_id': project_id})
    logger.info(
        "Check-in missed",
        extra={
            'extra_fields': {
                'metric': 'check_ins_missed',
                'user_id': user_id,
                'project_id': project_id,
            }
        }
    )


def track_message_delivery(platform: str, success: bool, retry_count: int = 0) -> None:
    """Track message delivery attempt."""
    status = 'success' if success else 'failed'
    metrics.increment('message_delivery', {'platform': platform, 'status': status})
    
    if retry_count > 0:
        metrics.increment('message_retries', {'platform': platform}, value=retry_count)
    
    logger.info(
        "Message delivery tracked",
        extra={
            'extra_fields': {
                'metric': 'message_delivery',
                'platform': platform,
                'status': status,
                'retry_count': retry_count,
            }
        }
    )


def track_task_completed(user_id: str, project_id: str, task_id: str, on_time: bool) -> None:
    """Track task completion."""
    status = 'on_time' if on_time else 'late'
    metrics.increment('tasks_completed', {'user_id': user_id, 'project_id': project_id, 'status': status})
    logger.info(
        "Task completed",
        extra={
            'extra_fields': {
                'metric': 'tasks_completed',
                'user_id': user_id,
                'project_id': project_id,
                'task_id': task_id,
                'status': status,
            }
        }
    )


def track_task_rescheduled(user_id: str, project_id: str, task_id: str, blocker_type: Optional[str] = None) -> None:
    """Track task rescheduling."""
    labels = {'user_id': user_id, 'project_id': project_id}
    if blocker_type:
        labels['blocker_type'] = blocker_type
    
    metrics.increment('tasks_rescheduled', labels)
    logger.info(
        "Task rescheduled",
        extra={
            'extra_fields': {
                'metric': 'tasks_rescheduled',
                'user_id': user_id,
                'project_id': project_id,
                'task_id': task_id,
                'blocker_type': blocker_type,
            }
        }
    )


def track_llm_request(operation: str, success: bool, duration_ms: float, tokens_used: Optional[int] = None) -> None:
    """Track LLM API request."""
    status = 'success' if success else 'failed'
    metrics.increment('llm_requests', {'operation': operation, 'status': status})
    metrics.record_duration('llm_request_duration', duration_ms, {'operation': operation})
    
    extra_fields = {
        'metric': 'llm_requests',
        'operation': operation,
        'status': status,
        'duration_ms': duration_ms,
    }
    
    if tokens_used:
        metrics.increment('llm_tokens_used', {'operation': operation}, value=tokens_used)
        extra_fields['tokens_used'] = tokens_used
    
    logger.info(
        "LLM request tracked",
        extra={'extra_fields': extra_fields}
    )


def get_check_in_response_rate(user_id: Optional[str] = None) -> float:
    """
    Calculate check-in response rate.
    
    Args:
        user_id: Optional user ID to filter by
        
    Returns:
        Response rate as a percentage (0-100)
    """
    labels = {'user_id': user_id} if user_id else None
    
    sent = metrics.get_metric('check_ins_sent', labels)
    responded = metrics.get_metric('check_ins_responded', labels)
    
    if sent == 0:
        return 0.0
    
    rate = (responded / sent) * 100
    
    logger.info(
        "Check-in response rate calculated",
        extra={
            'extra_fields': {
                'user_id': user_id,
                'sent': sent,
                'responded': responded,
                'rate_percent': round(rate, 2),
            }
        }
    )
    
    return rate


def get_message_delivery_success_rate(platform: Optional[str] = None) -> float:
    """
    Calculate message delivery success rate.
    
    Args:
        platform: Optional platform to filter by
        
    Returns:
        Success rate as a percentage (0-100)
    """
    success_labels = {'status': 'success'}
    failed_labels = {'status': 'failed'}
    
    if platform:
        success_labels['platform'] = platform
        failed_labels['platform'] = platform
    
    success = metrics.get_metric('message_delivery', success_labels)
    failed = metrics.get_metric('message_delivery', failed_labels)
    total = success + failed
    
    if total == 0:
        return 0.0
    
    rate = (success / total) * 100
    
    logger.info(
        "Message delivery success rate calculated",
        extra={
            'extra_fields': {
                'platform': platform,
                'success': success,
                'failed': failed,
                'rate_percent': round(rate, 2),
            }
        }
    )
    
    return rate


def get_task_completion_rate(user_id: Optional[str] = None, project_id: Optional[str] = None) -> float:
    """
    Calculate task completion rate (on-time vs late).
    
    Args:
        user_id: Optional user ID to filter by
        project_id: Optional project ID to filter by
        
    Returns:
        On-time completion rate as a percentage (0-100)
    """
    on_time_labels = {'status': 'on_time'}
    late_labels = {'status': 'late'}
    
    if user_id:
        on_time_labels['user_id'] = user_id
        late_labels['user_id'] = user_id
    
    if project_id:
        on_time_labels['project_id'] = project_id
        late_labels['project_id'] = project_id
    
    on_time = metrics.get_metric('tasks_completed', on_time_labels)
    late = metrics.get_metric('tasks_completed', late_labels)
    total = on_time + late
    
    if total == 0:
        return 0.0
    
    rate = (on_time / total) * 100
    
    logger.info(
        "Task completion rate calculated",
        extra={
            'extra_fields': {
                'user_id': user_id,
                'project_id': project_id,
                'on_time': on_time,
                'late': late,
                'rate_percent': round(rate, 2),
            }
        }
    )
    
    return rate


def get_rescheduling_frequency(user_id: Optional[str] = None, project_id: Optional[str] = None) -> Dict[str, int]:
    """
    Get rescheduling frequency by blocker type.
    
    Args:
        user_id: Optional user ID to filter by
        project_id: Optional project ID to filter by
        
    Returns:
        Dictionary with blocker types and their counts
    """
    blocker_types = ['time', 'clarity', 'emotional', 'external', 'scope']
    result = {}
    
    for blocker_type in blocker_types:
        labels = {'blocker_type': blocker_type}
        if user_id:
            labels['user_id'] = user_id
        if project_id:
            labels['project_id'] = project_id
        
        count = metrics.get_metric('tasks_rescheduled', labels)
        if count > 0:
            result[blocker_type] = count
    
    logger.info(
        "Rescheduling frequency calculated",
        extra={
            'extra_fields': {
                'user_id': user_id,
                'project_id': project_id,
                'frequency_by_blocker': result,
            }
        }
    )
    
    return result


# Onboarding-specific metrics (Requirements: 10.1, 10.2, 10.3, 10.4, 10.5)

def track_onboarding_started(dm_enabled: bool) -> None:
    """Track that an onboarding flow was started."""
    metrics.increment('onboarding_started', {'dm_enabled': str(dm_enabled)})
    logger.info(
        "Onboarding started",
        extra={
            'extra_fields': {
                'metric': 'onboarding_started',
                'dm_enabled': dm_enabled,
            }
        }
    )


def track_onboarding_completed(duration_minutes: float, has_deadline: bool) -> None:
    """Track that an onboarding flow was completed."""
    metrics.increment('onboarding_completed', {'has_deadline': str(has_deadline)})
    metrics.record_duration('onboarding_total_duration', duration_minutes * 60 * 1000)
    
    logger.info(
        "Onboarding completed",
        extra={
            'extra_fields': {
                'metric': 'onboarding_completed',
                'duration_minutes': duration_minutes,
                'has_deadline': has_deadline,
            }
        }
    )


def track_onboarding_cancelled(from_state: str) -> None:
    """Track that an onboarding flow was cancelled."""
    metrics.increment('onboarding_cancelled', {'from_state': from_state})
    logger.info(
        "Onboarding cancelled",
        extra={
            'extra_fields': {
                'metric': 'onboarding_cancelled',
                'from_state': from_state,
            }
        }
    )


def track_onboarding_state_transition(from_state: str, to_state: str) -> None:
    """Track an onboarding state transition."""
    metrics.increment('onboarding_state_transitions', {
        'from_state': from_state,
        'to_state': to_state
    })
    logger.info(
        "Onboarding state transition",
        extra={
            'extra_fields': {
                'metric': 'onboarding_state_transitions',
                'from_state': from_state,
                'to_state': to_state,
            }
        }
    )


def track_onboarding_error(error_type: str) -> None:
    """Track an onboarding error."""
    metrics.increment('onboarding_errors', {'error_type': error_type})
    logger.error(
        "Onboarding error",
        extra={
            'extra_fields': {
                'metric': 'onboarding_errors',
                'error_type': error_type,
            }
        }
    )


def get_onboarding_completion_rate() -> float:
    """
    Calculate onboarding completion rate.
    
    Returns:
        Completion rate as a percentage (0-100)
    """
    started = metrics.get_metric('onboarding_started')
    completed = metrics.get_metric('onboarding_completed')
    
    if started == 0:
        return 0.0
    
    rate = (completed / started) * 100
    
    logger.info(
        "Onboarding completion rate calculated",
        extra={
            'extra_fields': {
                'started': started,
                'completed': completed,
                'rate_percent': round(rate, 2),
            }
        }
    )
    
    return rate


def get_onboarding_drop_off_by_state() -> Dict[str, int]:
    """
    Get onboarding drop-off counts by state.
    
    Returns:
        Dictionary with states and their cancellation counts
    """
    states = [
        'welcome', 'collect_project_name', 'collect_goal', 'collect_deadline',
        'collect_checkin_frequency', 'collect_tone', 'confirm_details'
    ]
    result = {}
    
    for state in states:
        count = metrics.get_metric('onboarding_cancelled', {'from_state': state})
        if count > 0:
            result[state] = count
    
    logger.info(
        "Onboarding drop-off by state calculated",
        extra={
            'extra_fields': {
                'drop_off_by_state': result,
            }
        }
    )
    
    return result


def get_onboarding_dm_failure_rate() -> float:
    """
    Calculate DM failure rate for onboarding.
    
    Returns:
        Failure rate as a percentage (0-100)
    """
    dm_enabled_started = metrics.get_metric('onboarding_started', {'dm_enabled': 'True'})
    dm_failed = metrics.get_metric('onboarding_dm_failed')
    total_attempts = dm_enabled_started + dm_failed
    
    if total_attempts == 0:
        return 0.0
    
    rate = (dm_failed / total_attempts) * 100
    
    logger.info(
        "Onboarding DM failure rate calculated",
        extra={
            'extra_fields': {
                'dm_enabled_started': dm_enabled_started,
                'dm_failed': dm_failed,
                'rate_percent': round(rate, 2),
            }
        }
    )
    
    return rate
