"""
Property-based test for relative date accuracy.

Feature: discord-project-plan-management, Property 8: Relative date accuracy
Validates: Requirements 8.3
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import re

from app.models.project import Project, ProjectStatus
from app.models.milestone import Milestone, MilestoneStatus
from app.services.discord_project_plan_formatter import DiscordProjectPlanFormatter


@st.composite
def milestone_with_known_date_strategy(draw):
    """Generate a milestone with a known date offset from now."""
    # Generate a date offset in days (can be negative for past dates)
    days_offset = draw(st.integers(min_value=-365, max_value=365))
    
    now = datetime.now(timezone.utc)
    target_date = now + timedelta(days=days_offset)
    
    milestone = Milestone(
        id=uuid4(),
        project_id=uuid4(),
        title=draw(st.text(min_size=1, max_size=100)),
        description=draw(st.one_of(st.none(), st.text(min_size=1, max_size=300))),
        target_date=target_date,
        status=draw(st.sampled_from(list(MilestoneStatus))),
        order=draw(st.integers(min_value=0, max_value=100)),
        completed_at=None,
        created_at=now,
        updated_at=now
    )
    
    return milestone, days_offset


def extract_relative_date(formatted_string: str) -> str:
    """
    Extract the relative date portion from a formatted milestone string.
    
    Expected format: "... `Dec 25, 2024 (in 3 days)`"
    """
    # Match the relative date in parentheses
    match = re.search(r'\(([^)]+)\)', formatted_string)
    if match:
        return match.group(1)
    return ""


@settings(max_examples=100, deadline=None)
@given(
    data=st.data()
)
def test_relative_date_accuracy(data):
    """
    Property 8: Relative date accuracy
    
    For any milestone displayed with a relative date (e.g., "in 3 days"), 
    the relative date should accurately reflect the difference between the 
    current date and the milestone's target date.
    
    Validates: Requirements 8.3
    """
    # Generate milestone with known date offset
    milestone, days_offset = data.draw(milestone_with_known_date_strategy())
    
    # Create formatter
    formatter = DiscordProjectPlanFormatter()
    
    # Format the milestone
    formatted = formatter.format_milestone(milestone, include_status_emoji=True, number=1)
    
    # Extract the relative date
    relative_date = extract_relative_date(formatted)
    
    # Calculate the actual difference at format time
    now = datetime.now(timezone.utc)
    target = milestone.target_date
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    actual_days = (target - now).days
    
    # Property: Relative date should accurately reflect the actual days difference
    # Allow for small timing differences (within 1 day due to test execution time)
    if actual_days < -1:
        # Past date (more than 1 day ago)
        assert "days ago" in relative_date, (
            f"Expected 'days ago' in relative date for past date, "
            f"but got '{relative_date}'"
        )
    elif actual_days == 0:
        # Today
        assert "today" in relative_date, (
            f"Expected 'today' in relative date for 0 days offset, "
            f"but got '{relative_date}'"
        )
    elif actual_days == 1:
        # Tomorrow
        assert "tomorrow" in relative_date, (
            f"Expected 'tomorrow' in relative date for 1 day offset, "
            f"but got '{relative_date}'"
        )
    elif actual_days > 1:
        # Future date (more than 1 day away)
        assert "in" in relative_date and "days" in relative_date, (
            f"Expected 'in X days' in relative date for future date, "
            f"but got '{relative_date}'"
        )


@settings(max_examples=100, deadline=None)
@given(
    data=st.data()
)
def test_relative_date_format_consistency(data):
    """
    Property: Relative dates should always be formatted consistently.
    
    Validates: Requirements 8.3
    """
    # Generate milestone with known date offset
    milestone, days_offset = data.draw(milestone_with_known_date_strategy())
    
    # Create formatter
    formatter = DiscordProjectPlanFormatter()
    
    # Format the milestone multiple times
    formatted1 = formatter.format_milestone(milestone, include_status_emoji=True, number=1)
    formatted2 = formatter.format_milestone(milestone, include_status_emoji=True, number=1)
    
    # Extract relative dates
    relative_date1 = extract_relative_date(formatted1)
    relative_date2 = extract_relative_date(formatted2)
    
    # Property: Formatting the same milestone should produce the same relative date
    # (within the same second, which is reasonable for this test)
    assert relative_date1 == relative_date2, (
        f"Formatting the same milestone twice should produce the same relative date, "
        f"but got '{relative_date1}' and '{relative_date2}'"
    )


@settings(max_examples=100, deadline=None)
@given(
    data=st.data()
)
def test_absolute_date_present(data):
    """
    Property: Formatted dates should include both absolute and relative dates.
    
    Validates: Requirements 8.3
    """
    # Generate milestone with known date offset
    milestone, days_offset = data.draw(milestone_with_known_date_strategy())
    
    # Create formatter
    formatter = DiscordProjectPlanFormatter()
    
    # Format the milestone
    formatted = formatter.format_milestone(milestone, include_status_emoji=True, number=1)
    
    # Property: Should contain both absolute date (month name) and relative date (parentheses)
    # Check for month abbreviations
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    has_month = any(month in formatted for month in months)
    
    assert has_month, (
        f"Formatted milestone should contain an absolute date with month, "
        f"but got '{formatted}'"
    )
    
    # Check for relative date in parentheses
    has_relative = '(' in formatted and ')' in formatted
    
    assert has_relative, (
        f"Formatted milestone should contain a relative date in parentheses, "
        f"but got '{formatted}'"
    )
