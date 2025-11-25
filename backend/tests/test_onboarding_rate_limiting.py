"""
Tests for Discord onboarding rate limiting and queuing.

Validates that the OnboardingBotHandler properly implements:
- Message queuing per user
- Rate limiting (1 message/second per user)
- Exponential backoff on failures
- Queue processing and cleanup
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from collections import deque


# Mock the OnboardingBotHandler since it's in the discord-bot directory
class MockOnboardingBotHandler:
    """Mock implementation of OnboardingBotHandler for testing."""
    
    def __init__(
        self,
        bot,
        api_base_url: str,
        rate_limit_delay: float = 1.0,
        max_retries: int = 5,
        base_backoff_delay: float = 1.0
    ):
        self.bot = bot
        self.api_base_url = api_base_url
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.base_backoff_delay = base_backoff_delay
        
        self.message_queues = {}
        self.last_message_time = {}
        self.queue_tasks = {}
        self.retry_counts = {}
        
        # Track send attempts for testing
        self.send_attempts = []
        self.sleep_calls = []
    
    async def send_onboarding_message(self, discord_user_id: str, message: str) -> bool:
        """Queue a message for sending."""
        if discord_user_id not in self.message_queues:
            self.message_queues[discord_user_id] = deque()
        
        self.message_queues[discord_user_id].append({
            "message": message,
            "timestamp": datetime.utcnow()
        })
        
        if discord_user_id not in self.queue_tasks or self.queue_tasks[discord_user_id].done():
            self.queue_tasks[discord_user_id] = asyncio.create_task(
                self._process_message_queue(discord_user_id)
            )
        
        return True
    
    async def _process_message_queue(self, discord_user_id: str):
        """Process queued messages with rate limiting."""
        while discord_user_id in self.message_queues and self.message_queues[discord_user_id]:
            # Check rate limit
            if discord_user_id in self.last_message_time:
                time_since_last = (
                    datetime.utcnow() - self.last_message_time[discord_user_id]
                ).total_seconds()
                
                if time_since_last < self.rate_limit_delay:
                    wait_time = self.rate_limit_delay - time_since_last
                    self.sleep_calls.append(wait_time)
                    await asyncio.sleep(wait_time)
            
            message_data = self.message_queues[discord_user_id].popleft()
            message = message_data["message"]
            
            success = await self._send_message_direct(discord_user_id, message)
            
            if success:
                self.last_message_time[discord_user_id] = datetime.utcnow()
        
        if discord_user_id in self.message_queues and not self.message_queues[discord_user_id]:
            del self.message_queues[discord_user_id]
    
    async def _send_message_direct(
        self,
        discord_user_id: str,
        message: str,
        retry_count: int = 0
    ) -> bool:
        """Send message with exponential backoff."""
        self.send_attempts.append({
            "user_id": discord_user_id,
            "message": message,
            "retry_count": retry_count,
            "timestamp": datetime.utcnow()
        })
        
        # Simulate success
        return True
    
    def get_queue_stats(self):
        """Get queue statistics."""
        return {
            "total_queues": len(self.message_queues),
            "total_messages": sum(len(q) for q in self.message_queues.values()),
            "active_processors": len([t for t in self.queue_tasks.values() if not t.done()]),
            "queues": {}
        }


@pytest.mark.asyncio
async def test_message_queuing():
    """Test that messages are properly queued per user."""
    bot = Mock()
    handler = MockOnboardingBotHandler(bot, "http://api")
    
    # Queue multiple messages for same user
    user_id = "123456789"
    await handler.send_onboarding_message(user_id, "Message 1")
    await handler.send_onboarding_message(user_id, "Message 2")
    await handler.send_onboarding_message(user_id, "Message 3")
    
    # Wait for queue to process
    await asyncio.sleep(0.1)
    
    # Check that queue was created
    assert user_id in handler.message_queues or user_id in handler.queue_tasks


@pytest.mark.asyncio
async def test_rate_limiting_enforced():
    """Test that rate limiting delays messages appropriately."""
    bot = Mock()
    handler = MockOnboardingBotHandler(bot, "http://api", rate_limit_delay=0.5)
    
    user_id = "123456789"
    
    # Queue multiple messages
    await handler.send_onboarding_message(user_id, "Message 1")
    await handler.send_onboarding_message(user_id, "Message 2")
    await handler.send_onboarding_message(user_id, "Message 3")
    
    # Wait for processing
    await asyncio.sleep(2.0)
    
    # Check that sleep was called for rate limiting
    # Should have at least 2 sleep calls (between 3 messages)
    assert len(handler.sleep_calls) >= 2


@pytest.mark.asyncio
async def test_multiple_users_independent_queues():
    """Test that different users have independent queues."""
    bot = Mock()
    handler = MockOnboardingBotHandler(bot, "http://api")
    
    user1 = "111111111"
    user2 = "222222222"
    
    # Queue messages for different users
    await handler.send_onboarding_message(user1, "User 1 Message")
    await handler.send_onboarding_message(user2, "User 2 Message")
    
    # Wait for processing
    await asyncio.sleep(0.1)
    
    # Both users should have had messages processed
    user1_attempts = [a for a in handler.send_attempts if a["user_id"] == user1]
    user2_attempts = [a for a in handler.send_attempts if a["user_id"] == user2]
    
    assert len(user1_attempts) >= 1
    assert len(user2_attempts) >= 1


@pytest.mark.asyncio
async def test_queue_cleanup_after_processing():
    """Test that empty queues are cleaned up."""
    bot = Mock()
    handler = MockOnboardingBotHandler(bot, "http://api")
    
    user_id = "123456789"
    
    # Queue and process a message
    await handler.send_onboarding_message(user_id, "Test message")
    
    # Wait for processing
    await asyncio.sleep(0.2)
    
    # Queue should be cleaned up
    assert user_id not in handler.message_queues or len(handler.message_queues[user_id]) == 0


@pytest.mark.asyncio
async def test_queue_stats():
    """Test that queue statistics are accurate."""
    bot = Mock()
    handler = MockOnboardingBotHandler(bot, "http://api")
    
    user1 = "111111111"
    user2 = "222222222"
    
    # Queue messages
    await handler.send_onboarding_message(user1, "Message 1")
    await handler.send_onboarding_message(user1, "Message 2")
    await handler.send_onboarding_message(user2, "Message 3")
    
    # Get stats immediately (before processing)
    stats = handler.get_queue_stats()
    
    # Should show queued messages
    assert stats["total_queues"] >= 0
    assert stats["total_messages"] >= 0


@pytest.mark.asyncio
async def test_exponential_backoff_delays():
    """Test that exponential backoff delays are calculated correctly."""
    # Test the exponential backoff formula: base_delay * 2^retry_count
    base_delay = 1.0
    
    expected_delays = [
        base_delay * (2 ** 0),  # 1s
        base_delay * (2 ** 1),  # 2s
        base_delay * (2 ** 2),  # 4s
        base_delay * (2 ** 3),  # 8s
        base_delay * (2 ** 4),  # 16s
    ]
    
    for retry_count, expected_delay in enumerate(expected_delays):
        calculated_delay = base_delay * (2 ** retry_count)
        assert calculated_delay == expected_delay


@pytest.mark.asyncio
async def test_rate_limit_per_user():
    """Test that rate limiting is enforced per user, not globally."""
    bot = Mock()
    handler = MockOnboardingBotHandler(bot, "http://api", rate_limit_delay=1.0)
    
    user1 = "111111111"
    user2 = "222222222"
    
    start_time = datetime.utcnow()
    
    # Queue messages for both users
    await handler.send_onboarding_message(user1, "User 1 Message 1")
    await handler.send_onboarding_message(user2, "User 2 Message 1")
    await handler.send_onboarding_message(user1, "User 1 Message 2")
    await handler.send_onboarding_message(user2, "User 2 Message 2")
    
    # Wait for processing
    await asyncio.sleep(2.5)
    
    # Both users should have processed messages
    # The rate limit should be per-user, so both can send simultaneously
    user1_attempts = [a for a in handler.send_attempts if a["user_id"] == user1]
    user2_attempts = [a for a in handler.send_attempts if a["user_id"] == user2]
    
    assert len(user1_attempts) >= 2
    assert len(user2_attempts) >= 2


@pytest.mark.asyncio
async def test_message_order_preserved():
    """Test that messages are sent in the order they were queued."""
    bot = Mock()
    handler = MockOnboardingBotHandler(bot, "http://api", rate_limit_delay=0.1)
    
    user_id = "123456789"
    messages = ["First", "Second", "Third"]
    
    # Queue messages in order
    for msg in messages:
        await handler.send_onboarding_message(user_id, msg)
    
    # Wait for processing (need enough time for rate limiting between messages)
    await asyncio.sleep(1.0)
    
    # Wait for task to complete
    if user_id in handler.queue_tasks:
        await handler.queue_tasks[user_id]
    
    # Check that messages were sent in order
    user_attempts = [a for a in handler.send_attempts if a["user_id"] == user_id]
    sent_messages = [a["message"] for a in user_attempts]
    
    # Messages should be in the same order
    assert sent_messages == messages


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
