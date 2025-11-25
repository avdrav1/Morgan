"""
Tests for multi-project selection logic.

Validates: Requirements 7.1, 7.2, 7.3
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.project_plan_service import ProjectPlanService
from app.models.project import Project
from app.models.user import User


class TestMultiProjectSelection:
    """Test multi-project selection functionality."""
    
    def test_get_all_projects_returns_all_user_projects(self, db_session):
        """
        Test that get_all_projects returns all projects for a user.
        
        Validates: Requirements 7.1
        """
        # Create user
        user = User(
            email=f"test_{uuid4()}@example.com",
            full_name="Test User"
        )
        db_session.add(user)
        db_session.commit()
        
        # Create multiple projects
        project1 = Project(
            user_id=user.id,
            title="Project Alpha",
            description="Description for Project Alpha",
            goal="Build something",
            target_completion_date=datetime.utcnow() + timedelta(days=30)
        )
        project2 = Project(
            user_id=user.id,
            title="Project Beta",
            description="Description for Project Beta",
            goal="Build something else",
            target_completion_date=datetime.utcnow() + timedelta(days=60)
        )
        project3 = Project(
            user_id=user.id,
            title="Project Gamma",
            description="Description for Project Gamma",
            goal="Build yet another thing",
            target_completion_date=datetime.utcnow() + timedelta(days=90)
        )
        
        db_session.add_all([project1, project2, project3])
        db_session.commit()
        
        # Get all projects
        service = ProjectPlanService(db_session)
        projects = service.get_all_projects(user.id)
        
        # Verify all projects returned
        assert len(projects) == 3
        project_titles = {p.title for p in projects}
        assert "Project Alpha" in project_titles
        assert "Project Beta" in project_titles
        assert "Project Gamma" in project_titles
    
    def test_get_all_projects_ordered_by_recent_activity(self, db_session):
        """
        Test that get_all_projects returns projects ordered by most recent activity.
        
        Validates: Requirements 7.3
        """
        # Create user
        user = User(
            email=f"test_{uuid4()}@example.com",
            full_name="Test User"
        )
        db_session.add(user)
        db_session.commit()
        
        # Create projects with different update times
        now = datetime.utcnow()
        
        project1 = Project(
            user_id=user.id,
            title="Oldest Project",
            description="Description for Oldest Project",
            goal="Build something",
            target_completion_date=now + timedelta(days=30),
            updated_at=now - timedelta(days=10)
        )
        project2 = Project(
            user_id=user.id,
            title="Middle Project",
            description="Description for Middle Project",
            goal="Build something else",
            target_completion_date=now + timedelta(days=60),
            updated_at=now - timedelta(days=5)
        )
        project3 = Project(
            user_id=user.id,
            title="Newest Project",
            description="Description for Newest Project",
            goal="Build yet another thing",
            target_completion_date=now + timedelta(days=90),
            updated_at=now
        )
        
        db_session.add_all([project1, project2, project3])
        db_session.commit()
        
        # Get all projects
        service = ProjectPlanService(db_session)
        projects = service.get_all_projects(user.id)
        
        # Verify order (most recent first)
        assert len(projects) == 3
        assert projects[0].title == "Newest Project"
        assert projects[1].title == "Middle Project"
        assert projects[2].title == "Oldest Project"
    
    def test_find_project_by_name_exact_match(self, db_session):
        """
        Test finding a project by exact name match (case-insensitive).
        
        Validates: Requirements 7.2
        """
        # Create user
        user = User(
            email=f"test_{uuid4()}@example.com",
            full_name="Test User"
        )
        db_session.add(user)
        db_session.commit()
        
        # Create projects
        project1 = Project(
            user_id=user.id,
            title="Website Redesign",
            description="Redesign the company website",
            goal="Redesign the website",
            target_completion_date=datetime.utcnow() + timedelta(days=30)
        )
        project2 = Project(
            user_id=user.id,
            title="Mobile App",
            description="Build a mobile application",
            goal="Build mobile app",
            target_completion_date=datetime.utcnow() + timedelta(days=60)
        )
        
        db_session.add_all([project1, project2])
        db_session.commit()
        
        # Find by exact name (case-insensitive)
        service = ProjectPlanService(db_session)
        
        found = service.find_project_by_name(user.id, "website redesign")
        assert found is not None
        assert found.title == "Website Redesign"
        
        found = service.find_project_by_name(user.id, "MOBILE APP")
        assert found is not None
        assert found.title == "Mobile App"
    
    def test_find_project_by_name_partial_match(self, db_session):
        """
        Test finding a project by partial name match.
        
        Validates: Requirements 7.2
        """
        # Create user
        user = User(
            email=f"test_{uuid4()}@example.com",
            full_name="Test User"
        )
        db_session.add(user)
        db_session.commit()
        
        # Create projects
        project1 = Project(
            user_id=user.id,
            title="Website Redesign Project",
            description="Redesign the company website",
            goal="Redesign the website",
            target_completion_date=datetime.utcnow() + timedelta(days=30)
        )
        project2 = Project(
            user_id=user.id,
            title="Mobile App Development",
            description="Develop a mobile application",
            goal="Build mobile app",
            target_completion_date=datetime.utcnow() + timedelta(days=60)
        )
        
        db_session.add_all([project1, project2])
        db_session.commit()
        
        # Find by partial name
        service = ProjectPlanService(db_session)
        
        found = service.find_project_by_name(user.id, "website")
        assert found is not None
        assert found.title == "Website Redesign Project"
        
        found = service.find_project_by_name(user.id, "mobile")
        assert found is not None
        assert found.title == "Mobile App Development"
    
    def test_find_project_by_name_not_found(self, db_session):
        """
        Test that find_project_by_name returns None when no match found.
        
        Validates: Requirements 7.2
        """
        # Create user
        user = User(
            email=f"test_{uuid4()}@example.com",
            full_name="Test User"
        )
        db_session.add(user)
        db_session.commit()
        
        # Create project
        project = Project(
            user_id=user.id,
            title="Website Redesign",
            description="Redesign the company website",
            goal="Redesign the website",
            target_completion_date=datetime.utcnow() + timedelta(days=30)
        )
        
        db_session.add(project)
        db_session.commit()
        
        # Try to find non-existent project
        service = ProjectPlanService(db_session)
        found = service.find_project_by_name(user.id, "nonexistent")
        
        assert found is None
    
    def test_get_project_plan_with_no_project_id_returns_most_recent(self, db_session):
        """
        Test that get_project_plan without project_id returns most recent project.
        
        This validates the "current project" behavior.
        
        Validates: Requirements 7.3
        """
        # Create user
        user = User(
            email=f"test_{uuid4()}@example.com",
            full_name="Test User"
        )
        db_session.add(user)
        db_session.commit()
        
        # Create projects with different update times
        now = datetime.utcnow()
        
        project1 = Project(
            user_id=user.id,
            title="Old Project",
            description="An older project",
            goal="Build something",
            target_completion_date=now + timedelta(days=30),
            updated_at=now - timedelta(days=10)
        )
        project2 = Project(
            user_id=user.id,
            title="Current Project",
            description="The current active project",
            goal="Build something else",
            target_completion_date=now + timedelta(days=60),
            updated_at=now
        )
        
        db_session.add_all([project1, project2])
        db_session.commit()
        
        # Get project plan without specifying project_id
        service = ProjectPlanService(db_session)
        
        import asyncio
        project_plan = asyncio.run(service.get_project_plan(user.id))
        
        # Should return the most recently updated project
        assert project_plan is not None
        assert project_plan['project'].title == "Current Project"
    
    def test_get_project_plan_with_specific_project_id(self, db_session):
        """
        Test that get_project_plan with project_id returns that specific project.
        
        Validates: Requirements 7.2
        """
        # Create user
        user = User(
            email=f"test_{uuid4()}@example.com",
            full_name="Test User"
        )
        db_session.add(user)
        db_session.commit()
        
        # Create projects
        project1 = Project(
            user_id=user.id,
            title="Project Alpha",
            description="Description for Project Alpha",
            goal="Build something",
            target_completion_date=datetime.utcnow() + timedelta(days=30)
        )
        project2 = Project(
            user_id=user.id,
            title="Project Beta",
            description="Description for Project Beta",
            goal="Build something else",
            target_completion_date=datetime.utcnow() + timedelta(days=60)
        )
        
        db_session.add_all([project1, project2])
        db_session.commit()
        
        # Get specific project
        service = ProjectPlanService(db_session)
        
        import asyncio
        project_plan = asyncio.run(service.get_project_plan(user.id, project1.id))
        
        # Should return the specified project
        assert project_plan is not None
        assert project_plan['project'].id == project1.id
        assert project_plan['project'].title == "Project Alpha"
