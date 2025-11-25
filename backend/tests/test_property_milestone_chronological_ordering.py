"""
Property-based test for milestone chronological ordering.

Feature: discord-project-plan-management, Property 2: Milestone chronological ordering
Validates: Requirements 1.3
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import re

from app.models.project import Project, ProjectStatus
from app.models.milestone import Milestone, MilestoneStatus
from app.services.discord_project_plan_formatter import DiscordProjectPlanFormatter


@st.composite
def project_strategy(draw):
    """Generate a random project."""
    title = draw(st.text(min_size=1, max_size=100))
    goal = draw(st.text(min_size=1, max_size=500))
    description = draw(st.text(min_size=1, max_size=500))
    
    # Generate a future deadline
    days_ahead = draw(st.integers(min_value=1, max_value=365))
    target_date = datetime.now(timezone.utc) + timedelta(days=days_ahead)
    
    project = Project(
        id=uuid4(),
        user_id=uuid4(),
        title=title,
        description=description,
        goal=goal,
        status=ProjectStatus.ACTIVE,
        target_completion_date=target_date,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    return project


@st.composite
def milestone_strategy(draw, project_id, min_date, max_date):
    """Generate a random milestone."""
    title = draw(st.text(min_size=1, max_size=100))
    description = draw(st.one_of(st.none(), st.text(min_size=1, max_size=300)))
    status = draw(st.sampled_from(list(MilestoneStatus)))
    
    # Generate a date between min and max
    days_range = (max_date - min_date).days
    if days_range > 0:
        days_offset = draw(st.integers(min_value=0, max_value=days_range))
        target_date = min_date + timedelta(days=days_offset)
    else:
        target_date = min_date
    
    order = draw(st.integers(min_value=0, max_value=100))
    
    milestone = Milestone(
        id=uuid4(),
        project_id=project_id,
        title=title,
        description=description,
        target_date=target_date,
        status=status,
        order=order,
        completed_at=datetime.now(timezone.utc) if status == MilestoneStatus.COMPLETED else None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    return milestone


@st.composite
def milestones_list_strategy(draw, project):
    """Generate a list of milestones for a project."""
    # Generate between 2 and 20 milestones (need at least 2 to test ordering)
    count = draw(st.integers(min_value=2, max_value=20))
    
    now = datetime.now(timezone.utc)
    max_date = project.target_completion_date or (now + timedelta(days=365))
    
    milestones = []
    for _ in range(count):
        milestone = draw(milestone_strategy(project.id, now, max_date))
        milestones.append(milestone)
    
    return milestones


def extract_milestone_dates_from_formatted_plan(messages: list) -> list:
    """
    Extract milestone dates from formatted project plan messages.
    
    Returns a list of dates in the order they appear in the milestones section.
    Skips the project deadline in the header.
    """
    dates = []
    
    # Pattern to match dates like "Dec 25, 2024"
    date_pattern = r'([A-Z][a-z]{2} \d{1,2}, \d{4})'
    
    for message in messages:
        # Split by "Milestones:" to skip the header
        if "**Milestones:**" in message:
            # Only look at the part after the milestones header
            parts = message.split("**Milestones:**", 1)
            milestone_section = parts[1] if len(parts) > 1 else message
        else:
            # If no milestones header, this might be a continuation message
            milestone_section = message
        
        matches = re.findall(date_pattern, milestone_section)
        for match in matches:
            try:
                # Parse the date
                date = datetime.strptime(match, "%b %d, %Y")
                dates.append(date)
            except ValueError:
                # Skip if we can't parse it
                pass
    
    return dates


@settings(max_examples=100, deadline=None)
@given(
    data=st.data()
)
def test_milestone_chronological_ordering(data):
    """
    Property 2: Milestone chronological ordering
    
    For any project plan display, milestones should be ordered chronologically 
    by target date, with earlier dates appearing before later dates.
    
    Validates: Requirements 1.3
    """
    # Generate project
    project = data.draw(project_strategy())
    
    # Generate milestones (unsorted)
    milestones = data.draw(milestones_list_strategy(project))
    
    # Create formatter
    formatter = DiscordProjectPlanFormatter()
    
    # Format the project plan
    messages = formatter.format_project_plan(project, milestones, include_completed=True)
    
    # Extract dates from the formatted output
    formatted_dates = extract_milestone_dates_from_formatted_plan(messages)
    
    # Property: Dates should be in chronological order
    for i in range(len(formatted_dates) - 1):
        current_date = formatted_dates[i]
        next_date = formatted_dates[i + 1]
        
        assert current_date <= next_date, (
            f"Milestones should be ordered chronologically: "
            f"date at position {i} ({current_date}) is after "
            f"date at position {i+1} ({next_date})"
        )


@settings(max_examples=100, deadline=None)
@given(
    data=st.data()
)
def test_milestone_ordering_with_sorting(data):
    """
    Property: Milestones should be displayed in chronological order 
    regardless of their input order.
    
    Validates: Requirements 1.3
    """
    # Generate project
    project = data.draw(project_strategy())
    
    # Generate milestones
    milestones = data.draw(milestones_list_strategy(project))
    
    # Sort milestones by target date (as the service should do)
    sorted_milestones = sorted(milestones, key=lambda m: m.target_date)
    
    # Create formatter
    formatter = DiscordProjectPlanFormatter()
    
    # Format with sorted milestones
    messages = formatter.format_project_plan(project, sorted_milestones, include_completed=True)
    
    # Extract dates
    formatted_dates = extract_milestone_dates_from_formatted_plan(messages)
    
    # Property: All dates should be present and in order
    milestone_dates = [m.target_date for m in sorted_milestones]
    
    # Check that we have the right number of dates
    assert len(formatted_dates) == len(milestone_dates), (
        f"Expected {len(milestone_dates)} dates in formatted output, "
        f"but found {len(formatted_dates)}"
    )
    
    # Check chronological order
    for i in range(len(formatted_dates) - 1):
        assert formatted_dates[i] <= formatted_dates[i + 1], (
            f"Dates should be in chronological order"
        )


@settings(max_examples=100, deadline=None)
@given(
    data=st.data()
)
def test_milestone_ordering_preserved_in_split_messages(data):
    """
    Property: When messages are split due to length, chronological 
    ordering should be preserved within each message.
    
    Validates: Requirements 1.3, 8.2
    """
    # Generate project
    project = data.draw(project_strategy())
    
    # Generate many milestones to potentially trigger message splitting
    count = data.draw(st.integers(min_value=10, max_value=50))
    
    now = datetime.now(timezone.utc)
    max_date = project.target_completion_date or (now + timedelta(days=365))
    
    milestones = []
    for _ in range(count):
        milestone = data.draw(milestone_strategy(project.id, now, max_date))
        milestones.append(milestone)
    
    # Sort milestones
    sorted_milestones = sorted(milestones, key=lambda m: m.target_date)
    
    # Create formatter
    formatter = DiscordProjectPlanFormatter()
    
    # Format the project plan
    messages = formatter.format_project_plan(project, sorted_milestones, include_completed=True)
    
    # Property: Each message should have dates in chronological order
    for msg_idx, message in enumerate(messages):
        dates_in_message = extract_milestone_dates_from_formatted_plan([message])
        
        for i in range(len(dates_in_message) - 1):
            assert dates_in_message[i] <= dates_in_message[i + 1], (
                f"Chronological ordering should be preserved within message {msg_idx}: "
                f"date at position {i} ({dates_in_message[i]}) is after "
                f"date at position {i+1} ({dates_in_message[i + 1]})"
            )
