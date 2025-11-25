# Onboarding Logging and Monitoring Implementation

This document describes the comprehensive logging and monitoring implementation for the Discord DM onboarding flow.

## Overview

The onboarding flow now includes comprehensive logging and metrics tracking to support debugging, monitoring, and analytics. All logging follows structured JSON format with PII redaction and correlation IDs for request tracing.

## Requirements Validated

- **10.1**: Log all onboarding events with correlation IDs
- **10.2**: Log state transitions
- **10.3**: Log errors with full context
- **10.4**: Implement PII redaction in logs
- **10.5**: Add metrics for completion rates and drop-offs

## Logging Implementation

### Correlation IDs

Every onboarding flow is assigned a unique correlation ID that propagates through all related operations:

```python
from app.core.logging_config import set_correlation_id, get_correlation_id

# Set correlation ID at the start of a flow
correlation_id = set_correlation_id()

# Get current correlation ID
correlation_id = get_correlation_id()
```

Correlation IDs are automatically included in all structured log entries.

### Structured Logging

All logs are emitted in JSON format with consistent fields:

```json
{
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "level": "INFO",
  "logger": "app.services.onboarding_service",
  "message": "Onboarding session created",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "event": "onboarding_session_created",
  "session_id": "[UUID_REDACTED]",
  "user_id": "[UUID_REDACTED]",
  "state": "welcome"
}
```

### PII Redaction

The logging system automatically redacts personally identifiable information:

- **Emails**: `test@example.com` → `[EMAIL_REDACTED]`
- **Discord IDs**: `123456789012345678` → `[DISCORD_ID_REDACTED]`
- **UUIDs**: `a1b2c3d4-e5f6-7890-abcd-ef1234567890` → `[UUID_REDACTED]`

This is handled by the `PIIRedactor` class in `app.core.logging_config`.

### Event Types

The following event types are logged throughout the onboarding flow:

#### Session Management
- `onboarding_start` - Onboarding flow initiated
- `onboarding_session_created` - New session created
- `onboarding_session_resumed` - Existing session resumed
- `onboarding_dm_failed` - DM delivery failed
- `onboarding_session_not_found` - Session lookup failed

#### State Transitions
- `onboarding_state_transition` - State changed
- `onboarding_invalid_transition` - Invalid transition attempted

#### Message Processing
- `onboarding_message_received` - User message received
- `onboarding_session_updated` - Session data updated

#### Completion and Cancellation
- `onboarding_completed` - Onboarding successfully completed
- `onboarding_cancel_requested` - User requested cancellation
- `onboarding_cancelled` - Onboarding cancelled

#### Errors
- `onboarding_session_creation_failed` - Failed to create session
- `onboarding_session_update_failed` - Failed to update session
- `onboarding_completion_failed` - Failed to complete onboarding
- `onboarding_completion_error` - Error during completion
- `onboarding_inconsistent_state` - Data inconsistency detected

## Metrics Implementation

### Metrics Tracked

The following metrics are tracked for monitoring and analytics:

#### Onboarding Flow Metrics
- `onboarding_started` - Count of onboarding flows started
  - Labels: `dm_enabled` (true/false)
- `onboarding_completed` - Count of completed onboarding flows
  - Labels: `has_deadline` (true/false)
- `onboarding_cancelled` - Count of cancelled flows
  - Labels: `from_state` (state where cancellation occurred)
- `onboarding_dm_failed` - Count of DM delivery failures

#### Session Metrics
- `onboarding_session_created` - Count of new sessions created
- `onboarding_session_resumed` - Count of resumed sessions

#### State Transition Metrics
- `onboarding_state_transitions` - Count of state transitions
  - Labels: `from_state`, `to_state`

#### Error Metrics
- `onboarding_errors` - Count of errors by type
  - Labels: `error_type` (session_not_found, invalid_state_transition, etc.)

#### Duration Metrics
- `onboarding_completion_time` - Time to complete onboarding operation (ms)
- `onboarding_total_duration` - Total time from start to completion (ms)

#### Webhook Metrics
- `webhook_requests` - Count of webhook requests
  - Labels: `endpoint` (onboarding_start, etc.)

### Accessing Metrics

Metrics can be accessed programmatically:

```python
from app.core.metrics import metrics, get_onboarding_completion_rate

# Get specific metric
started_count = metrics.get_metric('onboarding_started')

# Get metric with labels
dm_failures = metrics.get_metric('onboarding_dm_failed')

# Get calculated rates
completion_rate = get_onboarding_completion_rate()  # Returns percentage
```

### Metrics Functions

Convenience functions are provided for common metrics:

```python
from app.core.metrics import (
    track_onboarding_started,
    track_onboarding_completed,
    track_onboarding_cancelled,
    track_onboarding_state_transition,
    track_onboarding_error,
    get_onboarding_completion_rate,
    get_onboarding_drop_off_by_state,
    get_onboarding_dm_failure_rate
)

# Track events
track_onboarding_started(dm_enabled=True)
track_onboarding_completed(duration_minutes=5.2, has_deadline=True)
track_onboarding_cancelled(from_state='collect_goal')

# Get analytics
completion_rate = get_onboarding_completion_rate()
drop_offs = get_onboarding_drop_off_by_state()
dm_failure_rate = get_onboarding_dm_failure_rate()
```

## Key Analytics

### Completion Rate

Calculate the percentage of users who complete onboarding:

```python
completion_rate = get_onboarding_completion_rate()
# Returns: 75.5 (meaning 75.5% completion rate)
```

### Drop-off Analysis

Identify which states users are most likely to abandon:

```python
drop_offs = get_onboarding_drop_off_by_state()
# Returns: {
#   'collect_goal': 15,
#   'collect_deadline': 8,
#   'collect_tone': 3
# }
```

### DM Failure Rate

Monitor Discord DM delivery success:

```python
dm_failure_rate = get_onboarding_dm_failure_rate()
# Returns: 5.2 (meaning 5.2% of DM attempts fail)
```

## Testing

Comprehensive tests validate the logging and metrics implementation:

- `test_onboarding_logging_metrics.py` - Tests for logging and metrics
  - Correlation ID propagation
  - Event logging
  - State transition logging
  - Error logging with context
  - PII redaction
  - Metrics tracking
  - Completion duration tracking

Run tests:

```bash
docker-compose exec backend pytest tests/test_onboarding_logging_metrics.py -v
```

## Monitoring Recommendations

### Alerts to Configure

1. **High DM Failure Rate**
   - Trigger: DM failure rate > 10%
   - Action: Check Discord bot status and permissions

2. **Low Completion Rate**
   - Trigger: Completion rate < 50%
   - Action: Review onboarding flow for UX issues

3. **High Error Rate**
   - Trigger: Error count > 5% of started sessions
   - Action: Investigate error logs for root cause

4. **Long Completion Times**
   - Trigger: Average completion time > 30 minutes
   - Action: Review if users are getting stuck

### Dashboard Metrics

Recommended metrics to display on monitoring dashboards:

1. **Onboarding Funnel**
   - Started → Session Created → Completed
   - Show conversion rates at each step

2. **Drop-off Heatmap**
   - Visualize which states have highest abandonment
   - Track trends over time

3. **DM Delivery Health**
   - Success rate
   - Failure reasons breakdown

4. **Completion Time Distribution**
   - Histogram of completion times
   - Identify outliers

5. **Error Rate by Type**
   - Track different error types
   - Identify patterns

## Log Query Examples

### Find all events for a specific user

```bash
# Using correlation_id
grep "correlation_id.*a1b2c3d4" logs/app.log | jq .
```

### Find all state transitions

```bash
grep "onboarding_state_transition" logs/app.log | jq .
```

### Find all errors

```bash
grep '"level":"ERROR"' logs/app.log | jq .
```

### Find DM failures

```bash
grep "onboarding_dm_failed" logs/app.log | jq .
```

## Integration with Existing Systems

The logging and metrics implementation integrates with:

1. **Existing Logging Infrastructure** (`app.core.logging_config`)
   - Uses the same structured logging format
   - Shares PII redaction logic
   - Consistent correlation ID handling

2. **Existing Metrics System** (`app.core.metrics`)
   - Uses the same MetricsCollector
   - Follows same labeling conventions
   - Compatible with existing metric queries

3. **Webhook Handlers** (`app.api.webhooks`)
   - Correlation IDs set at webhook entry
   - All webhook events logged
   - Webhook-specific metrics tracked

## Future Enhancements

Potential improvements for the logging and monitoring system:

1. **Real-time Dashboards**
   - Integrate with Grafana or similar
   - Live metrics visualization
   - Alert configuration UI

2. **Log Aggregation**
   - Send logs to centralized system (ELK, Splunk, etc.)
   - Enable cross-service correlation
   - Advanced search and analysis

3. **User Journey Tracking**
   - Track complete user journey from OAuth to first check-in
   - Identify friction points
   - A/B testing support

4. **Predictive Analytics**
   - Predict likelihood of completion based on early signals
   - Identify users who may need intervention
   - Optimize onboarding flow based on data

5. **Performance Monitoring**
   - Track API response times
   - Database query performance
   - LLM service latency
