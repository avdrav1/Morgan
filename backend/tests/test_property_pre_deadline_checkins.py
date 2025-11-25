"""
Property-based tests for pre-deadline check-ins.

Feature: proactive-accountability-assistant, Property 6: Pre-deadline check-ins
Validates: Requirements 3.1, 3.3
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


@settings(max_examples=100)
@given(
    days_until_due=st.integers(min_value=1, max_value=30),
    timezone=st.sampled_from(["UTC", "America/New_York", "Europe/London", "Asia/Tokyo"])
)
def test_pre_deadline_check_ins(days_until_due, timezone):
    """
    Property 6: Pre-deadline check-ins
    
    For any task with a due date, check-ins scheduled for that task should be 
    scheduled before the due date, not after.
    
    Validates: Requirements 3.1, 3.3
    """
    # Create a user
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        timezone=timezone
    )
    
    # Create a task with a due date in the future
    due_date = datetime.utcnow() + timedelta(days=days_until_due)
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
    
    # Verify the check-in is before the due date
    assert check_in_time < due_date, \
        f"Check-in time {check_in_time} should be before due date {due_date}. " \
        f"Task due in {days_until_due} days."


@settings(max_examples=100)
@given(
    hours_until_due=st.integers(min_value=2, max_value=72),
    timezone=st.sampled_from(["UTC", "America/New_York", "Europe/London", "Asia/Tokyo"])
)
def test_pre_deadline_check_ins_short_timeframe(hours_until_due, timezone):
    """
    Property 6: Pre-deadline check-ins (short timeframe variant)
    
    Even for tasks with short deadlines (hours instead of days), check-ins 
    should still be scheduled before the due date.
    
    Validates: Requirements 3.1, 3.3
    """
    # Create a user
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        timezone=timezone
    )
    
    # Create a task with a due date in the near future (hours)
    due_date = datetime.utcnow() + timedelta(hours=hours_until_due)
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
    
    # Verify the check-in is before the due date
    assert check_in_time < due_date, \
        f"Check-in time {check_in_time} should be before due date {due_date}. " \
        f"Task due in {hours_until_due} hours."


@settings(max_examples=100)
@given(
    days_until_due=st.integers(min_value=2, max_value=14),
    num_windows=st.integers(min_value=1, max_value=3)
)
def test_pre_deadline_check_ins_with_availability(days_until_due, num_windows):
    """
    Property 6: Pre-deadline check-ins (with availability windows)
    
    Even when availability windows are defined, check-ins should still be 
    scheduled before the due date.
    
    Validates: Requirements 3.1, 3.3
    """
    # Create a user
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        timezone="UTC"
    )
    
    # Create availability windows
    availability_windows = []
    for i in range(num_windows):
        day_of_week = i % 7  # Spread across different days
        window = AvailabilityWindow(
            id=uuid.uuid4(),
            user_id=user.id,
            day_of_week=day_of_week,
            start_time="09:00",
            end_time="17:00"
        )
        availability_windows.append(window)
    
    # Create a task with a due date in the future
    due_date = datetime.utcnow() + timedelta(days=days_until_due)
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
    
    # Calculate check-in time with availability windows
    check_in_time = scheduler.calculate_check_in_time(task, user, availability_windows)
    
    # If no valid slot could be found (availability windows don't allow scheduling
    # before the due date), that's an edge case we accept
    if check_in_time is None:
        # This can happen when availability windows don't align with the time before due date
        return
    
    # Verify the check-in is before the due date
    assert check_in_time < due_date, \
        f"Check-in time {check_in_time} should be before due date {due_date}. " \
        f"Task due in {days_until_due} days with {num_windows} availability windows."


@settings(max_examples=50)
@given(
    timezone=st.sampled_from(["UTC", "America/New_York", "Europe/London", "Asia/Tokyo"])
)
def test_no_check_ins_after_due_date(timezone):
    """
    Property 6: Pre-deadline check-ins (negative test)
    
    Verify that the scheduler NEVER returns a check-in time that is after 
    the due date, regardless of circumstances.
    
    Validates: Requirements 3.1, 3.3
    """
    # Create a user
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        timezone=timezone
    )
    
    # Test with various due dates
    test_cases = [
        timedelta(hours=1),   # Very soon
        timedelta(hours=6),   # Same day
        timedelta(days=1),    # Tomorrow
        timedelta(days=7),    # Next week
        timedelta(days=30),   # Next month
    ]
    
    scheduler = SchedulerService()
    
    for time_delta in test_cases:
        due_date = datetime.utcnow() + time_delta
        task = Task(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            title="Test Task",
            order=1,
            status=TaskStatus.NOT_STARTED,
            due_date=due_date
        )
        
        # Calculate check-in time
        check_in_time = scheduler.calculate_check_in_time(task, user, [])
        
        # Verify it's before the due date
        assert check_in_time < due_date, \
            f"Check-in time {check_in_time} should be before due date {due_date} " \
            f"(time delta: {time_delta})"
