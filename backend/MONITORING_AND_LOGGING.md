# Monitoring and Logging Implementation

This document describes the monitoring and logging infrastructure implemented for the Proactive Accountability Assistant.

## Overview

The system now includes comprehensive structured logging, metrics tracking, and alerting for critical failures.

## 1. Structured Logging

### Features
- **JSON-formatted logs** with structured fields for easy parsing
- **Correlation IDs** automatically added to all HTTP requests for request tracing
- **PII redaction** to protect user privacy (emails, Discord IDs, UUIDs)
- **Contextual logging** with extra fields for rich debugging information

### Components

#### `app/core/logging_config.py`
- `PIIRedactor`: Automatically redacts PII from log messages
- `StructuredFormatter`: Formats logs as JSON with timestamp, level, logger, message, and correlation ID
- `CorrelationIdFilter`: Adds correlation IDs to log records
- `setup_logging()`: Configures application-wide logging
- `get_logger()`: Returns configured logger instances

#### `app/core/middleware.py`
- `CorrelationIdMiddleware`: FastAPI middleware that:
  - Generates or extracts correlation IDs from request headers
  - Logs incoming requests with method, path, and query params
  - Logs completed requests with status code and duration
  - Adds correlation ID to response headers
  - Logs errors with full context

### Usage Example

```python
from app.core.logging_config import get_logger

logger = get_logger(__name__)

logger.info(
    "Processing user request",
    extra={
        'extra_fields': {
            'user_id': user_id,
            'operation': 'create_project',
            'project_count': 5,
        }
    }
)
```

### Log Format

```json
{
  "timestamp": "2024-11-22T10:30:45.123456Z",
  "level": "INFO",
  "logger": "app.services.llm_service",
  "message": "LLM request: generate_check_in_message",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "operation": "generate_check_in_message",
  "tone": "coach",
  "model": "claude-sonnet-4-20250514"
}
```

## 2. Metrics Tracking

### Features
- **Thread-safe metrics collection** for concurrent operations
- **Counter metrics** for tracking events (check-ins sent, tasks completed, etc.)
- **Duration metrics** for tracking timing (response times, LLM latency, etc.)
- **Labeled metrics** for filtering by user, project, platform, etc.

### Components

#### `app/core/metrics.py`
- `MetricsCollector`: Thread-safe metrics collection with counters and timers
- Convenience functions for common metrics:
  - `track_check_in_sent()`
  - `track_check_in_responded()`
  - `track_check_in_missed()`
  - `track_message_delivery()`
  - `track_task_completed()`
  - `track_task_rescheduled()`
  - `track_llm_request()`

### Tracked Metrics

1. **Check-in Response Rate** (Requirements: 3.4, 3.5)
   - `check_ins_sent`: Total check-ins sent
   - `check_ins_responded`: Total check-ins with user responses
   - `check_ins_missed`: Total check-ins without responses
   - `check_in_response_time`: Duration from sent to responded

2. **Message Delivery Success Rate** (Requirements: 7.4)
   - `message_delivery`: Success/failure counts by platform
   - `message_retries`: Number of retry attempts

3. **Task Completion Rate**
   - `tasks_completed`: On-time vs late completion counts
   - Tracked by user and project

4. **Rescheduling Frequency**
   - `tasks_rescheduled`: Count by blocker type
   - Helps identify common obstacles

5. **LLM Performance**
   - `llm_requests`: Success/failure counts by operation
   - `llm_request_duration`: Latency by operation
   - `llm_tokens_used`: Token consumption tracking

### API Endpoints

#### `GET /api/metrics/summary`
Returns key metrics for the current user:
- Check-in response rate
- Task completion rate
- Rescheduling frequency
- Message delivery success rate

#### `GET /api/metrics/project/{project_id}`
Returns metrics for a specific project

#### `GET /api/metrics/all`
Returns all raw metrics data (for debugging)

### Usage Example

```python
from app.core.metrics import track_check_in_sent, get_check_in_response_rate

# Track an event
track_check_in_sent(user_id=str(user.id), project_id=str(project.id))

# Get calculated metrics
response_rate = get_check_in_response_rate(user_id=str(user.id))
print(f"Response rate: {response_rate}%")
```

## 3. Alerting System

### Features
- **Threshold-based alerting** for critical failures
- **Alert cooldown** to prevent alert spam
- **Alert history** for debugging and analysis
- **Configurable thresholds** per failure type

### Components

#### `app/core/alerts.py`
- `AlertManager`: Manages alert thresholds and triggers
- Convenience functions:
  - `record_llm_failure()`
  - `record_message_delivery_failure()`
  - `record_database_failure()`

### Alert Thresholds

1. **LLM API Failures**
   - Threshold: 5 failures in 10 minutes
   - Level: ERROR
   - Triggers when Anthropic API is unavailable or returning errors

2. **Message Delivery Failures**
   - Threshold: 10 failures in 15 minutes
   - Level: WARNING
   - Triggers when Discord/web messages fail to deliver

3. **Database Connection Failures**
   - Threshold: 3 failures in 5 minutes
   - Level: CRITICAL
   - Triggers when PostgreSQL connection issues occur

### Alert Cooldown
- Alerts for the same failure type won't trigger more than once per 30 minutes
- Prevents alert fatigue while ensuring visibility

### API Endpoints

#### `GET /api/alerts/history`
Returns recent alert history and current failure counts

#### `GET /api/health/detailed`
Returns comprehensive health status including:
- Database connectivity
- Key metrics
- Current failure counts
- Recent alerts

### Usage Example

```python
from app.core.alerts import record_llm_failure

try:
    response = await llm_service.generate_message(...)
except Exception as e:
    # Record failure for alerting
    record_llm_failure('generate_message', str(e))
    # Use fallback...
```

## Integration Points

### LLM Service
- Logs all LLM requests with operation, tone, model
- Logs responses with length and token usage
- Records failures for alerting
- Uses PII redaction for user responses

### Scheduler Service
- Logs scheduling decisions with task and user context
- Logs when no available slots are found
- Tracks check-in timing calculations

### Messaging Adapters
- Logs message delivery attempts with platform
- Logs retry attempts with exponential backoff delays
- Records delivery failures for alerting
- Tracks delivery success/failure metrics

### API Endpoints
- Automatic correlation ID tracking via middleware
- Request/response logging with duration
- Error logging with full context

### Database Layer
- Logs connection failures
- Records failures for alerting
- Tracks retry attempts

### Celery Tasks
- Logs check-in processing
- Tracks metrics for sent check-ins
- Records message delivery outcomes

## Monitoring Best Practices

### For Development
1. Set log level to DEBUG in `.env`: `DEBUG=True`
2. Monitor logs for correlation IDs to trace requests
3. Use `/api/metrics/all` to inspect raw metrics
4. Check `/api/alerts/history` for any triggered alerts

### For Production
1. Set log level to INFO: `DEBUG=False`
2. Configure log aggregation (e.g., ELK stack, CloudWatch)
3. Set up alert notifications (email, Slack, PagerDuty)
4. Monitor key metrics dashboards
5. Set up automated health checks

### Key Metrics to Monitor
- Check-in response rate (should be > 50%)
- Message delivery success rate (should be > 95%)
- Task completion rate (on-time vs late)
- LLM API latency (should be < 5 seconds)
- Database connection health

### Alert Response
When an alert triggers:
1. Check `/api/health/detailed` for current status
2. Review `/api/alerts/history` for failure patterns
3. Check logs with correlation IDs for detailed context
4. Investigate root cause (API outage, network issue, etc.)
5. Apply fixes and monitor for resolution

## Future Enhancements

1. **Metrics Export**
   - Prometheus metrics endpoint
   - StatsD integration
   - CloudWatch metrics

2. **Advanced Alerting**
   - Email/SMS notifications
   - Slack/PagerDuty integration
   - Incident management system integration

3. **Dashboards**
   - Grafana dashboards for metrics visualization
   - Real-time monitoring UI
   - Historical trend analysis

4. **Distributed Tracing**
   - OpenTelemetry integration
   - Cross-service request tracing
   - Performance profiling

5. **Log Analysis**
   - Automated log analysis for anomaly detection
   - Error pattern recognition
   - Performance bottleneck identification
