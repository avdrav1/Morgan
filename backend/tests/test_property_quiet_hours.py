"""
Property-based tests for quiet hours enforcement.

Feature: proactive-accountability-assistant, Property 7: Quiet hours enforcement
Validates: Requirements 3.2, 8.3
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.models.user import User
from app.services.scheduler_service import SchedulerService


# Strategy for generating valid time strings in HH:MM format
@st.composite
def time_string(draw):
    """Generate a valid time string in HH:MM format."""
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    return f"{hour:02d}:{minute:02d}"


@st.composite
def quiet_hours_pair(draw):
    """Generate a pair of quiet hours (start, end)."""
    start = draw(time_string())
    end = draw(time_string())
    # Ensure they're different to have meaningful quiet hours
    assume(start != end)
    return start, end


@st.composite
def datetime_in_timezone(draw, timezone_str="UTC"):
    """Generate a datetime in a specific timezone."""
    year = draw(st.integers(min_value=2024, max_value=2025))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=28))  # Safe for all months
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    
    dt = datetime(year, month, day, hour, minute)
    return dt.replace(tzinfo=ZoneInfo(timezone_str))


@settings(max_examples=100)
@given(
    quiet_hours=quiet_hours_pair(),
    check_time=datetime_in_timezone(),
    timezone=st.sampled_from(["UTC", "America/New_York", "Europe/London", "Asia/Tokyo"])
)
def test_quiet_hours_enforcement(quiet_hours, check_time, timezone):
    """
    Property 7: Quiet hours enforcement
    
    For any user with defined quiet hours, no messages should be sent during 
    those time periods.
    
    This test verifies that the is_within_quiet_hours method correctly identifies
    times that fall within quiet hours, including cases where quiet hours span midnight.
    
    Validates: Requirements 3.2, 8.3
    """
    # Create a user with quiet hours
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        timezone=timezone,
        quiet_hours_start=quiet_hours[0],
        quiet_hours_end=quiet_hours[1]
    )
    
    # Create scheduler service
    scheduler = SchedulerService()
    
    # Convert check_time to user's timezone
    check_time_in_tz = check_time.astimezone(ZoneInfo(timezone))
    
    # Check if time is within quiet hours
    is_quiet = scheduler.is_within_quiet_hours(user, check_time_in_tz)
    
    # Parse quiet hours
    start_hour, start_minute = map(int, quiet_hours[0].split(':'))
    end_hour, end_minute = map(int, quiet_hours[1].split(':'))
    
    quiet_start = time(start_hour, start_minute)
    quiet_end = time(end_hour, end_minute)
    check_time_only = check_time_in_tz.time()
    
    # Verify the result matches expected behavior
    if quiet_start > quiet_end:
        # Quiet hours span midnight
        expected_quiet = check_time_only >= quiet_start or check_time_only <= quiet_end
    else:
        # Normal quiet hours
        expected_quiet = quiet_start <= check_time_only <= quiet_end
    
    assert is_quiet == expected_quiet, \
        f"Quiet hours {quiet_hours[0]}-{quiet_hours[1]}, check time {check_time_only}, " \
        f"expected quiet={expected_quiet}, got {is_quiet}"


@settings(max_examples=100)
@given(
    quiet_hours=quiet_hours_pair(),
    timezone=st.sampled_from(["UTC", "America/New_York", "Europe/London", "Asia/Tokyo"])
)
def test_no_messages_during_quiet_hours(quiet_hours, timezone):
    """
    Property 7: Quiet hours enforcement (scheduling variant)
    
    Verify that when finding the next available slot, the scheduler never returns
    a time that falls within quiet hours.
    
    Validates: Requirements 3.2, 8.3
    """
    # Create a user with quiet hours
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        timezone=timezone,
        quiet_hours_start=quiet_hours[0],
        quiet_hours_end=quiet_hours[1]
    )
    
    # Create scheduler service
    scheduler = SchedulerService()
    
    # Generate a preferred time (in UTC)
    preferred_time = datetime(2024, 6, 15, 12, 0)  # Fixed time for consistency
    
    # Find next available slot (with no availability windows, only quiet hours apply)
    next_slot = scheduler.find_next_available_slot(user, preferred_time, [])
    
    # If no slot could be found (quiet hours cover almost entire day), that's acceptable
    if next_slot is None:
        # This is expected when quiet hours are configured to cover almost the entire day
        # The system correctly identified that no valid slot exists
        return
    
    # Convert to user's timezone for checking
    next_slot_in_tz = next_slot.replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo(timezone))
    
    # Verify the returned slot is NOT in quiet hours
    is_quiet = scheduler.is_within_quiet_hours(user, next_slot_in_tz)
    
    assert not is_quiet, \
        f"Scheduler returned a time in quiet hours: {next_slot_in_tz.time()} " \
        f"(quiet hours: {quiet_hours[0]}-{quiet_hours[1]})"
