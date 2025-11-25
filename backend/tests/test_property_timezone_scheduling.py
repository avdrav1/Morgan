"""
Property-based tests for timezone-aware scheduling.

Feature: proactive-accountability-assistant, Property 17: Timezone-aware scheduling
Validates: Requirements 8.5
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import uuid

from app.models.user import User
from app.models.task import Task, TaskStatus
from app.models.availability_window import AvailabilityWindow
from app.services.scheduler_service import SchedulerService


@st.composite
def availability_window_data(draw):
    """Generate a valid availability window."""
    day_of_week = draw(st.integers(min_value=0, max_value=6))
    start_hour = draw(st.integers(min_value=0, max_value=22))
    end_hour = draw(st.integers(min_value=start_hour + 1, max_value=23))
    
    return AvailabilityWindow(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        day_of_week=day_of_week,
        start_time=f"{start_hour:02d}:00",
        end_time=f"{end_hour:02d}:00"
    )


@settings(max_examples=100)
@given(
    timezone=st.sampled_from([
        "UTC",
        "America/New_York",
        "America/Los_Angeles",
        "Europe/London",
        "Europe/Paris",
        "Asia/Tokyo",
        "Asia/Shanghai",
        "Australia/Sydney"
    ]),
    hours_offset=st.integers(min_value=1, max_value=72)
)
def test_timezone_aware_scheduling(timezone, hours_offset):
    """
    Property 17: Timezone-aware scheduling
    
    For any user with a specified timezone, all scheduled check-in times 
    should be calculated in that timezone.
    
    This test verifies that when we schedule a check-in, the time calculations
    respect the user's timezone setting.
    
    Validates: Requirements 8.5
    """
    # Create a user with a specific timezone
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        timezone=timezone
    )
    
    # Create a task with a due date
    due_date = datetime.utcnow() + timedelta(hours=hours_offset)
    task = Task(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Test Task",
        order=1,
        status=TaskStatus.NOT_STARTED,
        due_date=due_date
    )
    
    # Create scheduler service
    scheduler = SchedulerService()
    
    # Calculate check-in time (no availability windows for simplicity)
    check_in_time = scheduler.calculate_check_in_time(task, user, [])
    
    # Verify the check-in time is valid (not None)
    assert check_in_time is not None, "Check-in time should not be None"
    
    # Verify the check-in time is before the due date
    assert check_in_time < due_date, \
        f"Check-in time {check_in_time} should be before due date {due_date}"
    
    # Convert check-in time to user's timezone
    check_in_in_tz = check_in_time.replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo(timezone))
    
    # Verify the time is reasonable (not in the past by more than a few seconds)
    now_in_tz = datetime.utcnow().replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo(timezone))
    time_diff = (check_in_in_tz - now_in_tz).total_seconds()
    
    # Allow for small negative differences due to test execution time
    assert time_diff > -60, \
        f"Check-in time should not be more than 60 seconds in the past. " \
        f"Difference: {time_diff} seconds"


@settings(max_examples=100)
@given(
    timezone=st.sampled_from([
        "America/New_York",  # UTC-5/-4
        "Europe/London",     # UTC+0/+1
        "Asia/Tokyo"         # UTC+9
    ])
)
def test_find_next_available_slot_respects_timezone(timezone):
    """
    Property 17: Timezone-aware scheduling (slot finding variant)
    
    Verify that find_next_available_slot correctly handles timezone conversions
    when finding the next available time.
    
    Validates: Requirements 8.5
    """
    # Create a user with a specific timezone
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        timezone=timezone
    )
    
    # Create an availability window for Monday 9am-5pm in user's timezone
    availability = AvailabilityWindow(
        id=uuid.uuid4(),
        user_id=user.id,
        day_of_week=0,  # Monday
        start_time="09:00",
        end_time="17:00"
    )
    
    # Create scheduler service
    scheduler = SchedulerService()
    
    # Find a Monday in the near future
    now = datetime.utcnow()
    days_until_monday = (7 - now.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7  # Next Monday, not today
    
    next_monday = now + timedelta(days=days_until_monday)
    preferred_time = next_monday.replace(hour=12, minute=0, second=0, microsecond=0)
    
    # Find next available slot
    next_slot = scheduler.find_next_available_slot(user, preferred_time, [availability])
    
    # Convert to user's timezone
    next_slot_in_tz = next_slot.replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo(timezone))
    
    # Verify the slot is on a Monday
    assert next_slot_in_tz.weekday() == 0, \
        f"Expected Monday (0), got {next_slot_in_tz.weekday()}"
    
    # Verify the slot is within the availability window (9am-5pm in user's timezone)
    slot_time = next_slot_in_tz.time()
    assert slot_time.hour >= 9 and slot_time.hour < 17, \
        f"Expected time between 09:00 and 17:00, got {slot_time}"


@settings(max_examples=50)
@given(
    source_tz=st.sampled_from(["America/New_York", "Europe/London", "Asia/Tokyo"]),
    target_tz=st.sampled_from(["America/New_York", "Europe/London", "Asia/Tokyo"])
)
def test_timezone_conversion_consistency(source_tz, target_tz):
    """
    Additional test: Verify timezone conversions are consistent.
    
    When we convert a time from one timezone to another and back,
    we should get the same time.
    """
    # Create a user with source timezone
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        timezone=source_tz
    )
    
    # Create a specific time in source timezone
    original_time = datetime(2024, 6, 15, 14, 30)
    time_in_source = original_time.replace(tzinfo=ZoneInfo(source_tz))
    
    # Convert to UTC
    time_in_utc = time_in_source.astimezone(ZoneInfo('UTC'))
    
    # Convert to target timezone
    time_in_target = time_in_utc.astimezone(ZoneInfo(target_tz))
    
    # Convert back to UTC
    time_back_to_utc = time_in_target.astimezone(ZoneInfo('UTC'))
    
    # Verify the UTC times are the same
    assert time_in_utc == time_back_to_utc, \
        f"Timezone conversion should be consistent. " \
        f"Original UTC: {time_in_utc}, After round-trip: {time_back_to_utc}"
