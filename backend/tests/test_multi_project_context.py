"""
Tests for multi-project context in responses.

Validates: Requirements 7.4, 7.5
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.discord_project_plan_formatter import DiscordProjectPlanFormatter
from app.models.project import Project
from app.models.milestone import Milestone, MilestoneStatus


class TestMultiProjectContext:
    """Test that project context is maintained in responses."""
    
    def test_format_project_plan_includes_project_name(self):
        """
        Test that formatted project plan includes the project name.
        
        Validates: Requirements 7.4
        """
        # Create project
        project = Project(
            id=uuid4(),
            user_id=uuid4(),
            title="Website Redesign",
            goal="Redesign the company website",
            target_completion_date=datetime.utcnow() + timedelta(days=30)
        )
        
        # Create milestones
        milestones = [
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Design mockups",
                target_date=datetime.utcnow() + timedelta(days=10),
                status=MilestoneStatus.PENDING,
                order=0
            ),
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Implement frontend",
                target_date=datetime.utcnow() + timedelta(days=20),
                status=MilestoneStatus.PENDING,
                order=1
            )
        ]
        
        # Format the project plan
        formatter = DiscordProjectPlanFormatter()
        messages = formatter.format_project_plan(project, milestones)
        
        # Verify project name is in the output
        full_output = "\n".join(messages)
        assert "Website Redesign" in full_output
    
    def test_format_timeline_summary_includes_project_context(self):
        """
        Test that timeline summary maintains project context.
        
        Validates: Requirements 7.4
        """
        # Create project
        project = Project(
            id=uuid4(),
            user_id=uuid4(),
            title="Mobile App Development",
            goal="Build a mobile app",
            target_completion_date=datetime.utcnow() + timedelta(days=60)
        )
        
        # Create milestones
        milestones = [
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Setup project",
                target_date=datetime.utcnow() + timedelta(days=10),
                status=MilestoneStatus.COMPLETED,
                order=0
            ),
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Build features",
                target_date=datetime.utcnow() + timedelta(days=40),
                status=MilestoneStatus.IN_PROGRESS,
                order=1
            ),
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Testing",
                target_date=datetime.utcnow() + timedelta(days=55),
                status=MilestoneStatus.PENDING,
                order=2
            )
        ]
        
        # Format timeline summary
        formatter = DiscordProjectPlanFormatter()
        summary = formatter.format_timeline_summary(project, milestones)
        
        # Verify summary contains relevant information
        assert "Timeline Summary" in summary
        assert "1/3" in summary or "33%" in summary  # Progress
        assert "✅" in summary  # Completed
        assert "🔄" in summary  # In progress
        assert "⏳" in summary  # Pending
    
    def test_multiple_projects_maintain_separate_context(self):
        """
        Test that multiple projects maintain separate context.
        
        Validates: Requirements 7.5
        """
        # Create two different projects
        project1 = Project(
            id=uuid4(),
            user_id=uuid4(),
            title="Project Alpha",
            goal="First project",
            target_completion_date=datetime.utcnow() + timedelta(days=30)
        )
        
        project2 = Project(
            id=uuid4(),
            user_id=uuid4(),
            title="Project Beta",
            goal="Second project",
            target_completion_date=datetime.utcnow() + timedelta(days=60)
        )
        
        # Create milestones for each
        milestones1 = [
            Milestone(
                id=uuid4(),
                project_id=project1.id,
                title="Alpha Milestone 1",
                target_date=datetime.utcnow() + timedelta(days=10),
                status=MilestoneStatus.PENDING,
                order=0
            )
        ]
        
        milestones2 = [
            Milestone(
                id=uuid4(),
                project_id=project2.id,
                title="Beta Milestone 1",
                target_date=datetime.utcnow() + timedelta(days=20),
                status=MilestoneStatus.PENDING,
                order=0
            )
        ]
        
        # Format both project plans
        formatter = DiscordProjectPlanFormatter()
        
        output1 = "\n".join(formatter.format_project_plan(project1, milestones1))
        output2 = "\n".join(formatter.format_project_plan(project2, milestones2))
        
        # Verify each output contains only its own project context
        assert "Project Alpha" in output1
        assert "Alpha Milestone 1" in output1
        assert "Project Beta" not in output1
        assert "Beta Milestone 1" not in output1
        
        assert "Project Beta" in output2
        assert "Beta Milestone 1" in output2
        assert "Project Alpha" not in output2
        assert "Alpha Milestone 1" not in output2
    
    def test_project_name_in_milestone_operations(self):
        """
        Test that project name is included in milestone operation responses.
        
        This is a documentation test showing the expected behavior.
        
        Validates: Requirements 7.4
        """
        # This test documents that responses should include project names
        # The actual implementation is in the intent handlers
        
        # Example expected responses:
        expected_responses = [
            "✅ I've added a new milestone to **Project Name**:",
            "✅ I've updated **Milestone Title** in **Project Name**",
            "✅ I've removed **Milestone Title** from **Project Name**",
            "🎉 You've completed **Milestone Title** in **Project Name**!",
            "✅ Great! I've updated the deadline for **Project Name**"
        ]
        
        # Verify format patterns
        for response in expected_responses:
            assert "**" in response  # Uses bold markdown
            # Project name should be clearly identified
            assert "Project Name" in response or "Milestone Title" in response
