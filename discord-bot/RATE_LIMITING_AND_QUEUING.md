# Discord Bot Rate Limiting and Queuing

## Overview

The Discord bot implements comprehensive rate limiting, message queuing, and exponential backoff to ensure reliable message delivery while respecting Discord's API limits and handling transient failures gracefully.

## Features

### 1. Message Queuing

Each user has an independent message queue that stores messages to be sent. This ensures:
- Messages are sent in the order they were queued
- Multiple messages can be queued without blocking
- Users don't interfere with each other's message delivery

**Implementation:**
```python
self.message_queues: Dict[str, deque] = {}
```

### 2. Rate Limiting

Rate limiting is enforced **per user** at 1 message per second. This prevents:
- Hitting Discord's rate limits
- Overwhelming users with rapid-fire messages
- API throttling errors

**Implementation:**
- Tracks last message time per user
- Enforces minimum delay between messages
- Independent rate limits for each user (users don't block each other)

**Configuration:**
```python
rate_limit_delay: float = 1.0  # seconds between messages to same user
```

### 3. Exponential Backoff

When message delivery fails due to transient errors, the bot automatically retries with exponential backoff:

**Retry Delays:**
- Attempt 1: 1 second
- Attempt 2: 2 seconds
- Attempt 3: 4 seconds
- Attempt 4: 8 seconds
- Attempt 5: 16 seconds

**Formula:** `delay = base_delay * (2 ** retry_count)`

**Transient Errors (retried):**
- HTTP 500, 502, 503, 504 (server errors)
- HTTP 429 (rate limiting - uses Discord's retry_after value)
- Timeout errors
- Unexpected exceptions

**Permanent Errors (not retried):**
- HTTP 403 Forbidden (user blocked bot or DMs disabled)
- HTTP 404 Not Found (user doesn't exist)
- Invalid user ID format

**Configuration:**
```python
max_retries: int = 5
base_backoff_delay: float = 1.0  # seconds
```

## Architecture

### Queue Processing Flow

```
User Message → Queue Message → Start Queue Processor (if not running)
                                        ↓
                                Check Rate Limit
                                        ↓
                                Wait if needed
                                        ↓
                                Send Message
                                        ↓
                        Success? → Update last message time
                                        ↓
                        Failure? → Retry with exponential backoff
                                        ↓
                        Too many failures? → Stop processing queue
                                        ↓
                                Next message in queue
```

### Error Handling Strategy

1. **Permanent Failures**: Log and move on (don't retry)
2. **Transient Failures**: Retry with exponential backoff
3. **Rate Limiting**: Use Discord's suggested retry_after value
4. **Consecutive Failures**: Stop processing after 3 consecutive failures

## Usage

### Basic Usage

```python
from bot.onboarding_handler import OnboardingBotHandler

# Initialize handler
handler = OnboardingBotHandler(
    bot=discord_bot,
    api_base_url="http://backend:8000",
    rate_limit_delay=1.0,
    max_retries=5,
    base_backoff_delay=1.0
)

# Queue a message
await handler.send_onboarding_message(
    discord_user_id="123456789",
    message="Welcome to onboarding!"
)
```

### Monitoring Queue Status

```python
# Get queue statistics
stats = handler.get_queue_stats()

print(f"Active queues: {stats['total_queues']}")
print(f"Total messages: {stats['total_messages']}")
print(f"Active processors: {stats['active_processors']}")

# Per-user details
for user_id, queue_info in stats['queues'].items():
    print(f"User {user_id}:")
    print(f"  Messages: {queue_info['message_count']}")
    print(f"  Oldest message age: {queue_info['oldest_message_age']}s")
    print(f"  Processor active: {queue_info['processor_active']}")
```

## Configuration

### Recommended Settings

**Production:**
```python
rate_limit_delay=1.0        # 1 message/second per user
max_retries=5               # Up to 5 retry attempts
base_backoff_delay=1.0      # Start with 1 second delay
```

**Development/Testing:**
```python
rate_limit_delay=0.5        # Faster for testing
max_retries=3               # Fewer retries
base_backoff_delay=0.5      # Shorter delays
```

## Monitoring and Alerts

### Key Metrics to Track

1. **Queue Depth**: Number of messages waiting to be sent
2. **Message Age**: How long messages wait in queue
3. **Failure Rate**: Percentage of messages that fail after all retries
4. **Retry Rate**: How often messages need to be retried
5. **Processing Time**: Time from queue to delivery

### Alert Conditions

- Queue depth > 100 messages for any user
- Message age > 60 seconds
- Failure rate > 10%
- Consecutive failures >= 3 for any user

## Testing

The implementation includes comprehensive tests:

```bash
# Run rate limiting tests
docker-compose exec backend python -m pytest tests/test_onboarding_rate_limiting.py -v
```

**Test Coverage:**
- Message queuing per user
- Rate limiting enforcement
- Independent queues for multiple users
- Queue cleanup after processing
- Exponential backoff delays
- Per-user rate limiting
- Message order preservation

## Performance Considerations

### Memory Usage

- Each queued message stores: message content, timestamp
- Queues are cleaned up automatically when empty
- Old messages are logged if they wait > 60 seconds

### Concurrency

- Each user has an independent queue processor (asyncio Task)
- Queue processors run concurrently
- No global locks or blocking operations

### Scalability

- Scales linearly with number of users
- No shared state between users
- Efficient deque-based queue implementation

## Troubleshooting

### Messages Not Being Sent

1. Check queue stats: `handler.get_queue_stats()`
2. Look for error logs with user ID
3. Verify Discord bot has DM permissions
4. Check if user has blocked bot or disabled DMs

### Rate Limiting Errors

1. Verify rate_limit_delay is set correctly
2. Check for concurrent message sending outside the queue
3. Review Discord API rate limit documentation

### Queue Buildup

1. Check for consecutive failures stopping queue processing
2. Verify network connectivity to Discord API
3. Look for permanent errors (user blocked, not found)
4. Consider increasing max_retries for transient issues

## References

- [Discord API Rate Limits](https://discord.com/developers/docs/topics/rate-limits)
- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Exponential Backoff Best Practices](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
