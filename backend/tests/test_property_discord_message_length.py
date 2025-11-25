"""
Property-based test for Discord message length compliance.

Feature: discord-project-plan-management, Property 7: Discord message length compliance
Validates: Requirements 8.2, 8.5
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.project import Project, ProjectStatus
from app.models.milestone import Milestone, MilestoneStatus
from app.services.discord_project_plan_formatter import DiscordProjectPlanFormatter


# Strategy for generating projects
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


# Strategy for generating milestones
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


# Strategy for generating a list of milestones
@st.composite
def milestones_list_strategy(draw, project):
    """Generate a list of milestones for a project."""
    # Generate between 0 and 50 milestones
    count = draw(st.integers(min_value=0, max_value=50))
    
    if count == 0:
        return []
    
    now = datetime.now(timezone.utc)
    max_date = project.target_completion_date or (now + timedelta(days=365))
    
    milestones = []
    for _ in range(count):
        milestone = draw(milestone_strategy(project.id, now, max_date))
        milestones.append(milestone)
    
    # Sort by target date
    milestones.sort(key=lambda m: m.target_date)
    
    return milestones


@st.composite
def project_with_milestones_strategy(draw):
    """Generate a project with milestones."""
    project = draw(project_strategy())
    milestones = draw(milestones_list_strategy(project))
    return project, milestones


@settings(max_examples=100, deadline=None)
@given(
    data=st.data(),
    include_completed=st.booleans()
)
def test_discord_message_length_compliance(data, include_completed):
    """
    Property 7: Discord message length compliance
    
    For any formatted project plan output, each individual message 
    should not exceed Discord's 2000 character limit.
    
    Validates: Requirements 8.2, 8.5
    """
    # Generate project and milestones
    project, milestones = data.draw(project_with_milestones_strategy())
    
    # Create formatter
    formatter = DiscordProjectPlanFormatter()
    
    # Format the project plan
    messages = formatter.format_project_plan(project, milestones, include_completed)
    
    # Property: Each message should be under Discord's limit
    for i, message in enumerate(messages):
        assert len(message) <= DiscordProjectPlanFormatter.DISCORD_MAX_LENGTH, (
            f"Message {i} exceeds Discord's character limit: "
            f"{len(message)} > {DiscordProjectPlanFormatter.DISCORD_MAX_LENGTH}"
        )
    
    # Property: Messages should not be empty
    for i, message in enumerate(messages):
        assert len(message.strip()) > 0, f"Message {i} is empty"


@settings(max_examples=100, deadline=None)
@given(
    data=st.data()
)
def test_timeline_summary_length_compliance(data):
    """
    Property: Timeline summary should comply with Discord's length limit.
    
    Validates: Requirements 8.2, 8.5
    """
    # Generate project and milestones
    project, milestones = data.draw(project_with_milestones_strategy())
    
    # Create formatter
    formatter = DiscordProjectPlanFormatter()
    
    # Format timeline summary
    summary = formatter.format_timeline_summary(project, milestones)
    
    # Property: Summary should be under Discord's limit
    assert len(summary) <= DiscordProjectPlanFormatter.DISCORD_MAX_LENGTH, (
        f"Timeline summary exceeds Discord's character limit: "
        f"{len(summary)} > {DiscordProjectPlanFormatter.DISCORD_MAX_LENGTH}"
    )


@settings(max_examples=100, deadline=None)
@given(
    data=st.data()
)
def test_single_milestone_length_compliance(data):
    """
    Property: Single milestone formatting should be reasonable length.
    
    Validates: Requirements 8.1, 8.4
    """
    # Generate a project
    project = data.draw(project_strategy())
    
    # Generate a single milestone
    now = datetime.now(timezone.utc)
    max_date = project.target_completion_date or (now + timedelta(days=365))
    milestone = data.draw(milestone_strategy(project.id, now, max_date))
    
    # Create formatter
    formatter = DiscordProjectPlanFormatter()
    
    # Format the milestone
    formatted = formatter.format_milestone(milestone, include_status_emoji=True, number=1)
    
    # Property: Formatted milestone should be reasonable length
    # (not necessarily under 2000, but should be reasonable for a single milestone)
    assert len(formatted) < 5000, (
        f"Single milestone formatting is unreasonably long: {len(formatted)}"
    )
