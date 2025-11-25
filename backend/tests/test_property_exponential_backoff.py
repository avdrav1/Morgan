"""
Property-based tests for exponential backoff on message delivery retry.

Feature: proactive-accountability-assistant, Property 16: Exponential backoff on retry
Validates: Requirements 7.4
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from hypothesis import given, strategies as st, settings
from app.services.messaging_adapter import MessagingAdapter
from typing import Optional, Dict, Any


class MockAdapter(MessagingAdapter):
    """Mock adapter for testing retry logic."""
    
    def __init__(self, max_retries: int = 5, base_delay: float = 1.0):
        super().__init__(max_retries=max_retries, base_delay=base_delay)
        self.send_attempts = []
        self.should_fail = True
        self.fail_count = 0
    
    async def send_message(
        self,
        user_identifier: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Mock send_message that tracks attempts."""
        self.send_attempts.append({
            'user_identifier': user_identifier,
            'message': message,
            'metadata': metadata
        })
        
        if self.should_fail and len(self.send_attempts) <= self.fail_count:
            return False
        
        return True
    
    async def handle_incoming_message(
        self,
        user_identifier: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Mock handle_incoming_message."""
        pass
    
    def format_message(self, message: str) -> str:
        """Mock format_message."""
        return message


@pytest.mark.asyncio
@settings(max_examples=100)
@given(
    fail_count=st.integers(min_value=1, max_value=4),
    base_delay=st.floats(min_value=0.01, max_value=0.1)
)
async def test_exponential_backoff_delays(fail_count, base_delay):
    """
    Property: For any number of failures, retry delays should follow exponential backoff.
    
    The delays between retries should be: base_delay * 2^0, base_delay * 2^1, 
    base_delay * 2^2, etc.
    """
    adapter = MockAdapter(max_retries=5, base_delay=base_delay)
    adapter.fail_count = fail_count
    
    # Track sleep calls
    sleep_calls = []
    
    async def mock_sleep(delay):
        sleep_calls.append(delay)
    
    with patch('asyncio.sleep', side_effect=mock_sleep):
        result = await adapter.send_message_with_retry("user123", "test message")
    
    # Should have succeeded after fail_count attempts
    assert result is True
    assert len(adapter.send_attempts) == fail_count + 1
    
    # Check exponential backoff delays
    assert len(sleep_calls) == fail_count
    
    for i, delay in enumerate(sleep_calls):
        expected_delay = base_delay * (2 ** i)
        # Allow small floating point tolerance
        assert abs(delay - expected_delay) < 0.001, \
            f"Delay {i} should be {expected_delay}, got {delay}"


@pytest.mark.asyncio
@settings(max_examples=100)
@given(
    max_retries=st.integers(min_value=1, max_value=10),
    user_id=st.text(min_size=1, max_size=50)
)
async def test_max_retries_respected(max_retries, user_id):
    """
    Property: For any max_retries setting, the adapter should not exceed that number of attempts.
    
    If all attempts fail, the total number of send attempts should equal max_retries.
    """
    adapter = MockAdapter(max_retries=max_retries, base_delay=0.01)
    adapter.should_fail = True
    adapter.fail_count = max_retries + 10  # Fail more than max_retries
    
    with patch('asyncio.sleep', new_callable=AsyncMock):
        result = await adapter.send_message_with_retry(user_id, "test message")
    
    # Should have failed after max_retries attempts
    assert result is False
    assert len(adapter.send_attempts) == max_retries


@pytest.mark.asyncio
@settings(max_examples=100)
@given(
    success_on_attempt=st.integers(min_value=1, max_value=5),
    message=st.text(min_size=1, max_size=100)
)
async def test_stops_retrying_on_success(success_on_attempt, message):
    """
    Property: For any successful attempt, retrying should stop immediately.
    
    If a message succeeds on attempt N, there should be exactly N attempts total,
    not max_retries attempts.
    """
    adapter = MockAdapter(max_retries=5, base_delay=0.01)
    adapter.fail_count = success_on_attempt - 1  # Succeed on this attempt
    
    with patch('asyncio.sleep', new_callable=AsyncMock):
        result = await adapter.send_message_with_retry("user123", message)
    
    # Should have succeeded
    assert result is True
    # Should have stopped after success
    assert len(adapter.send_attempts) == success_on_attempt


@pytest.mark.asyncio
async def test_exponential_backoff_sequence():
    """
    Test the exact exponential backoff sequence: 1s, 2s, 4s, 8s, 16s.
    
    This is a concrete test to verify the specific sequence mentioned in requirements.
    """
    adapter = MockAdapter(max_retries=5, base_delay=1.0)
    adapter.fail_count = 4  # Fail first 4 attempts, succeed on 5th
    
    sleep_calls = []
    
    async def mock_sleep(delay):
        sleep_calls.append(delay)
    
    with patch('asyncio.sleep', side_effect=mock_sleep):
        result = await adapter.send_message_with_retry("user123", "test")
    
    assert result is True
    assert len(sleep_calls) == 4
    assert sleep_calls == [1.0, 2.0, 4.0, 8.0]


@pytest.mark.asyncio
@settings(max_examples=100)
@given(base_delay=st.floats(min_value=0.01, max_value=2.0))
async def test_first_retry_uses_base_delay(base_delay):
    """
    Property: For any base_delay, the first retry should wait exactly base_delay seconds.
    
    The first retry delay should be base_delay * 2^0 = base_delay.
    """
    adapter = MockAdapter(max_retries=5, base_delay=base_delay)
    adapter.fail_count = 1  # Fail first attempt, succeed on second
    
    sleep_calls = []
    
    async def mock_sleep(delay):
        sleep_calls.append(delay)
    
    with patch('asyncio.sleep', side_effect=mock_sleep):
        result = await adapter.send_message_with_retry("user123", "test")
    
    assert result is True
    assert len(sleep_calls) == 1
    assert abs(sleep_calls[0] - base_delay) < 0.001


@pytest.mark.asyncio
@settings(max_examples=100)
@given(
    max_retries=st.integers(min_value=2, max_value=10),
    base_delay=st.floats(min_value=0.01, max_value=0.5)
)
async def test_each_delay_doubles_previous(max_retries, base_delay):
    """
    Property: For any retry sequence, each delay should be double the previous delay.
    
    This verifies the exponential nature of the backoff.
    """
    adapter = MockAdapter(max_retries=max_retries, base_delay=base_delay)
    adapter.fail_count = max_retries  # Fail all attempts
    
    sleep_calls = []
    
    async def mock_sleep(delay):
        sleep_calls.append(delay)
    
    with patch('asyncio.sleep', side_effect=mock_sleep):
        result = await adapter.send_message_with_retry("user123", "test")
    
    assert result is False
    assert len(sleep_calls) == max_retries - 1  # No sleep after last attempt
    
    # Each delay should be double the previous
    for i in range(1, len(sleep_calls)):
        ratio = sleep_calls[i] / sleep_calls[i-1]
        assert abs(ratio - 2.0) < 0.01, \
            f"Delay {i} should be 2x delay {i-1}, got ratio {ratio}"


@pytest.mark.asyncio
async def test_no_delay_on_first_attempt():
    """
    Test that there is no delay before the first attempt.
    
    The first send_message call should happen immediately without any sleep.
    """
    adapter = MockAdapter(max_retries=5, base_delay=1.0)
    adapter.fail_count = 0  # Succeed on first attempt
    
    sleep_calls = []
    
    async def mock_sleep(delay):
        sleep_calls.append(delay)
    
    with patch('asyncio.sleep', side_effect=mock_sleep):
        result = await adapter.send_message_with_retry("user123", "test")
    
    assert result is True
    assert len(sleep_calls) == 0  # No sleep before first attempt
    assert len(adapter.send_attempts) == 1


@pytest.mark.asyncio
async def test_no_delay_after_final_failure():
    """
    Test that there is no delay after the final failed attempt.
    
    After the last retry fails, the function should return immediately
    without sleeping.
    """
    adapter = MockAdapter(max_retries=3, base_delay=1.0)
    adapter.fail_count = 10  # Fail all attempts
    
    sleep_calls = []
    
    async def mock_sleep(delay):
        sleep_calls.append(delay)
    
    with patch('asyncio.sleep', side_effect=mock_sleep):
        result = await adapter.send_message_with_retry("user123", "test")
    
    assert result is False
    assert len(adapter.send_attempts) == 3
    assert len(sleep_calls) == 2  # Sleep between attempts 1-2 and 2-3, but not after 3
