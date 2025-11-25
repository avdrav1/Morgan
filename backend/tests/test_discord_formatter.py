"""
Unit tests for Discord Project Plan Formatter.

Tests Discord markdown formatting, emoji status indicators, and message splitting.
Validates: Requirements 8.1, 8.2, 8.4
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.project import Project, ProjectStatus
from app.models.milestone import Milestone, MilestoneStatus
from app.services.discord_project_plan_formatter import DiscordProjectPlanFormatter


@pytest.fixture
def sample_project():
    """Create a sample project for testing."""
    return Project(
        id=uuid4(),
        user_id=uuid4(),
        title="Build a Mobile App",
        description="Create an iOS and Android app",
        goal="Launch a mobile app for task management",
        status=ProjectStatus.ACTIVE,
        target_completion_date=datetime.now(timezone.utc) + timedelta(days=90),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_milestones(sample_project):
    """Create sample milestones for testing."""
    now = datetime.now(timezone.utc)
    
    return [
        Milestone(
            id=uuid4(),
            project_id=sample_project.id,
            title="Design UI mockups",
            description="Create wireframes and mockups",
            target_date=now + timedelta(days=7),
            status=MilestoneStatus.COMPLETED,
            order=0,
            completed_at=now - timedelta(days=1),
            created_at=now,
            updated_at=now
        ),
        Milestone(
            id=uuid4(),
            project_id=sample_project.id,
            title="Implement authentication",
            description="Set up user login and registration",
            target_date=now + timedelta(days=21),
            status=MilestoneStatus.IN_PROGRESS,
            order=1,
            completed_at=None,
            created_at=now,
            updated_at=now
        ),
        Milestone(
            id=uuid4(),
            project_id=sample_project.id,
            title="Build core features",
            description=None,
            target_date=now + timedelta(days=45),
            status=MilestoneStatus.PENDING,
            order=2,
            completed_at=None,
            created_at=now,
            updated_at=now
        ),
    ]


def test_format_milestone_with_status_emojis(sample_project, sample_milestones):
    """
    Test that milestones are formatted with correct status emojis.
    
    Validates: Requirements 8.1, 8.4
    """
    formatter = DiscordProjectPlanFormatter()
    
    # Test completed milestone
    completed = sample_milestones[0]
    formatted = formatter.format_milestone(completed, include_status_emoji=True, number=1)
    assert "✅" in formatted, "Completed milestone should have ✅ emoji"
    assert "**Design UI mockups**" in formatted, "Should include bold title"
    
    # Test in-progress milestone
    in_progress = sample_milestones[1]
    formatted = formatter.format_milestone(in_progress, include_status_emoji=True, number=2)
    assert "🔄" in formatted, "In-progress milestone should have 🔄 emoji"
    assert "**Implement authentication**" in formatted, "Should include bold title"
    
    # Test pending milestone
    pending = sample_milestones[2]
    formatted = formatter.format_milestone(pending, include_status_emoji=True, number=3)
    assert "⏳" in formatted, "Pending milestone should have ⏳ emoji"
    assert "**Build core features**" in formatted, "Should include bold title"


def test_format_milestone_without_emoji(sample_milestones):
    """
    Test that milestones can be formatted without status emojis.
    
    Validates: Requirements 8.1
    """
    formatter = DiscordProjectPlanFormatter()
    milestone = sample_milestones[0]
    
    formatted = formatter.format_milestone(milestone, include_status_emoji=False)
    
    assert "✅" not in formatted, "Should not include emoji when disabled"
    assert "🔄" not in formatted, "Should not include emoji when disabled"
    assert "⏳" not in formatted, "Should not include emoji when disabled"
    assert "**Design UI mockups**" in formatted, "Should still include title"


def test_format_milestone_with_description(sample_milestones):
    """
    Test that milestone descriptions are included and formatted.
    
    Validates: Requirements 8.1
    """
    formatter = DiscordProjectPlanFormatter()
    milestone = sample_milestones[0]  # Has description
    
    formatted = formatter.format_milestone(milestone, include_status_emoji=True, number=1)
    
    assert "Create wireframes and mockups" in formatted, "Should include description"
    assert "_Create wireframes and mockups_" in formatted, "Description should be italicized"


def test_format_milestone_without_description(sample_milestones):
    """
    Test that milestones without descriptions are formatted correctly.
    
    Validates: Requirements 8.1
    """
    formatter = DiscordProjectPlanFormatter()
    milestone = sample_milestones[2]  # No description
    
    formatted = formatter.format_milestone(milestone, include_status_emoji=True, number=3)
    
    assert "**Build core features**" in formatted, "Should include title"
    # Should not have extra blank lines or formatting issues


def test_format_project_plan_markdown(sample_project, sample_milestones):
    """
    Test that project plan uses Discord markdown formatting.
    
    Validates: Requirements 8.1
    """
    formatter = DiscordProjectPlanFormatter()
    
    messages = formatter.format_project_plan(sample_project, sample_milestones, include_completed=True)
    
    full_message = "\n".join(messages)
    
    # Check for bold project title
    assert "**Build a Mobile App**" in full_message, "Project title should be bold"
    
    # Check for italic goal
    assert "_Launch a mobile app for task management_" in full_message, "Goal should be italic"
    
    # Check for code-formatted dates
    assert "`" in full_message, "Dates should be in code blocks"
    
    # Check for milestones section header
    assert "**Milestones:**" in full_message, "Should have milestones header"


def test_format_project_plan_filters_completed(sample_project, sample_milestones):
    """
    Test that completed milestones can be filtered out.
    
    Validates: Requirements 8.1
    """
    formatter = DiscordProjectPlanFormatter()
    
    # Include completed
    messages_with = formatter.format_project_plan(sample_project, sample_milestones, include_completed=True)
    full_with = "\n".join(messages_with)
    
    # Exclude completed
    messages_without = formatter.format_project_plan(sample_project, sample_milestones, include_completed=False)
    full_without = "\n".join(messages_without)
    
    # Completed milestone should be in first but not second
    assert "Design UI mockups" in full_with, "Should include completed when requested"
    assert "Design UI mockups" not in full_without, "Should exclude completed when requested"
    
    # Other milestones should be in both
    assert "Implement authentication" in full_with
    assert "Implement authentication" in full_without


def test_message_splitting_at_natural_boundaries(sample_project):
    """
    Test that long messages are split at natural boundaries.
    
    Validates: Requirements 8.2
    """
    formatter = DiscordProjectPlanFormatter()
    
    # Create many milestones to trigger splitting
    now = datetime.now(timezone.utc)
    many_milestones = []
    
    for i in range(50):
        milestone = Milestone(
            id=uuid4(),
            project_id=sample_project.id,
            title=f"Milestone {i}: " + "A" * 100,  # Long title
            description="B" * 200,  # Long description
            target_date=now + timedelta(days=i * 2),
            status=MilestoneStatus.PENDING,
            order=i,
            completed_at=None,
            created_at=now,
            updated_at=now
        )
        many_milestones.append(milestone)
    
    messages = formatter.format_project_plan(sample_project, many_milestones, include_completed=True)
    
    # Should be split into multiple messages
    assert len(messages) > 1, "Long content should be split into multiple messages"
    
    # Each message should be under the limit
    for i, message in enumerate(messages):
        assert len(message) <= DiscordProjectPlanFormatter.DISCORD_MAX_LENGTH, (
            f"Message {i} exceeds Discord's character limit"
        )


def test_format_timeline_summary(sample_project, sample_milestones):
    """
    Test that timeline summary is formatted correctly.
    
    Validates: Requirements 8.1
    """
    formatter = DiscordProjectPlanFormatter()
    
    summary = formatter.format_timeline_summary(sample_project, sample_milestones)
    
    # Check for key components
    assert "**Timeline Summary**" in summary, "Should have header"
    assert "Progress:" in summary, "Should show progress"
    assert "Deadline:" in summary, "Should show deadline"
    assert "Status:" in summary, "Should show status breakdown"
    
    # Check for emojis
    assert "✅" in summary, "Should have completed emoji"
    assert "🔄" in summary, "Should have in-progress emoji"
    assert "⏳" in summary, "Should have pending emoji"
    
    # Check for counts
    assert "1/3" in summary or "33%" in summary, "Should show progress fraction or percentage"


def test_format_timeline_summary_with_no_milestones(sample_project):
    """
    Test timeline summary with no milestones.
    
    Validates: Requirements 8.1
    """
    formatter = DiscordProjectPlanFormatter()
    
    summary = formatter.format_timeline_summary(sample_project, [])
    
    assert "0/0" in summary or "0%" in summary, "Should handle empty milestone list"
    assert "**Timeline Summary**" in summary, "Should still have header"


def test_relative_dates_in_formatted_output(sample_milestones):
    """
    Test that formatted milestones include relative dates.
    
    Validates: Requirements 8.3
    """
    formatter = DiscordProjectPlanFormatter()
    
    milestone = sample_milestones[1]  # 21 days in future
    formatted = formatter.format_milestone(milestone, include_status_emoji=True, number=1)
    
    # Should have both absolute and relative date
    assert "(" in formatted and ")" in formatted, "Should have relative date in parentheses"
    assert "in" in formatted or "days" in formatted, "Should indicate future date"


def test_empty_milestone_list(sample_project):
    """
    Test formatting with no milestones.
    
    Validates: Requirements 8.1
    """
    formatter = DiscordProjectPlanFormatter()
    
    messages = formatter.format_project_plan(sample_project, [], include_completed=False)
    
    full_message = "\n".join(messages)
    
    assert "**Build a Mobile App**" in full_message, "Should still show project info"
    assert "*No upcoming milestones.*" in full_message, "Should indicate no milestones"
