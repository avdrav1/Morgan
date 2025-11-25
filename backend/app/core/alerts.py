"""
Alerting system for critical failures.

Monitors:
- LLM API failures
- Message delivery failures
- Database connection issues
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict
import threading
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class AlertLevel:
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertManager:
    """Manages alerts for critical system failures."""
    
    def __init__(self):
        """Initialize alert manager with thread-safe tracking."""
        self._lock = threading.Lock()
        self._alert_counts = defaultdict(lambda: defaultdict(int))
        self._last_alert_time = defaultdict(lambda: None)
        self._alert_history = []
        
        # Alert thresholds
        self.thresholds = {
            'llm_api_failure': {
                'count': 5,
                'window_minutes': 10,
                'level': AlertLevel.ERROR,
            },
            'message_delivery_failure': {
                'count': 10,
                'window_minutes': 15,
                'level': AlertLevel.WARNING,
            },
            'database_connection_failure': {
                'count': 3,
                'window_minutes': 5,
                'level': AlertLevel.CRITICAL,
            },
        }
        
        # Alert cooldown (don't send same alert more than once per period)
        self.alert_cooldown_minutes = 30
    
    def record_failure(
        self,
        failure_type: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a failure and check if alert threshold is reached.
        
        Args:
            failure_type: Type of failure (llm_api_failure, message_delivery_failure, etc.)
            details: Additional details about the failure
        """
        with self._lock:
            now = datetime.utcnow()
            
            # Increment failure count
            self._alert_counts[failure_type][now.minute] += 1
            
            # Clean up old counts outside the window
            threshold_config = self.thresholds.get(failure_type)
            if threshold_config:
                window_minutes = threshold_config['window_minutes']
                cutoff_time = now - timedelta(minutes=window_minutes)
                
                # Remove counts older than the window
                keys_to_remove = [
                    minute for minute in self._alert_counts[failure_type].keys()
                    if minute < cutoff_time.minute
                ]
                for key in keys_to_remove:
                    del self._alert_counts[failure_type][key]
                
                # Calculate total failures in window
                total_failures = sum(self._alert_counts[failure_type].values())
                
                # Check if threshold is reached
                if total_failures >= threshold_config['count']:
                    # Check cooldown
                    last_alert = self._last_alert_time.get(failure_type)
                    if last_alert is None or (now - last_alert).total_seconds() / 60 >= self.alert_cooldown_minutes:
                        # Trigger alert
                        self._trigger_alert(
                            failure_type=failure_type,
                            level=threshold_config['level'],
                            count=total_failures,
                            window_minutes=window_minutes,
                            details=details
                        )
                        self._last_alert_time[failure_type] = now
    
    def _trigger_alert(
        self,
        failure_type: str,
        level: str,
        count: int,
        window_minutes: int,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Trigger an alert for a critical failure.
        
        Args:
            failure_type: Type of failure
            level: Alert severity level
            count: Number of failures in window
            window_minutes: Time window in minutes
            details: Additional details
        """
        alert = {
            'timestamp': datetime.utcnow().isoformat(),
            'failure_type': failure_type,
            'level': level,
            'count': count,
            'window_minutes': window_minutes,
            'details': details or {},
        }
        
        # Store in history
        self._alert_history.append(alert)
        
        # Keep only last 100 alerts
        if len(self._alert_history) > 100:
            self._alert_history = self._alert_history[-100:]
        
        # Log the alert
        log_message = (
            f"ALERT [{level.upper()}]: {failure_type} - "
            f"{count} failures in {window_minutes} minutes"
        )
        
        if level == AlertLevel.CRITICAL:
            logger.critical(
                log_message,
                extra={
                    'extra_fields': {
                        'alert_type': 'critical_failure',
                        'failure_type': failure_type,
                        'count': count,
                        'window_minutes': window_minutes,
                        'details': details or {},
                    }
                }
            )
        elif level == AlertLevel.ERROR:
            logger.error(
                log_message,
                extra={
                    'extra_fields': {
                        'alert_type': 'error_threshold',
                        'failure_type': failure_type,
                        'count': count,
                        'window_minutes': window_minutes,
                        'details': details or {},
                    }
                }
            )
        else:
            logger.warning(
                log_message,
                extra={
                    'extra_fields': {
                        'alert_type': 'warning_threshold',
                        'failure_type': failure_type,
                        'count': count,
                        'window_minutes': window_minutes,
                        'details': details or {},
                    }
                }
            )
        
        # In production, this would also:
        # - Send email/SMS to on-call engineer
        # - Post to Slack/PagerDuty
        # - Create incident ticket
        # For now, we just log it
    
    def get_alert_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent alert history.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of recent alerts
        """
        with self._lock:
            return self._alert_history[-limit:]
    
    def get_failure_counts(self) -> Dict[str, int]:
        """
        Get current failure counts for all types.
        
        Returns:
            Dictionary of failure types and their current counts
        """
        with self._lock:
            return {
                failure_type: sum(counts.values())
                for failure_type, counts in self._alert_counts.items()
            }
    
    def reset(self) -> None:
        """Reset all alert tracking (useful for testing)."""
        with self._lock:
            self._alert_counts.clear()
            self._last_alert_time.clear()
            self._alert_history.clear()


# Global alert manager instance
alert_manager = AlertManager()


# Convenience functions for recording failures

def record_llm_failure(operation: str, error: str) -> None:
    """Record an LLM API failure."""
    alert_manager.record_failure(
        'llm_api_failure',
        details={
            'operation': operation,
            'error': error,
        }
    )
    logger.error(
        "LLM API failure recorded",
        extra={
            'extra_fields': {
                'failure_type': 'llm_api_failure',
                'operation': operation,
                'error': error,
            }
        }
    )


def record_message_delivery_failure(platform: str, user_identifier: str, error: str) -> None:
    """Record a message delivery failure."""
    alert_manager.record_failure(
        'message_delivery_failure',
        details={
            'platform': platform,
            'error': error,
        }
    )
    logger.error(
        "Message delivery failure recorded",
        extra={
            'extra_fields': {
                'failure_type': 'message_delivery_failure',
                'platform': platform,
                'error': error,
            }
        }
    )


def record_database_failure(operation: str, error: str) -> None:
    """Record a database connection failure."""
    alert_manager.record_failure(
        'database_connection_failure',
        details={
            'operation': operation,
            'error': error,
        }
    )
    logger.critical(
        "Database connection failure recorded",
        extra={
            'extra_fields': {
                'failure_type': 'database_connection_failure',
                'operation': operation,
                'error': error,
            }
        }
    )
