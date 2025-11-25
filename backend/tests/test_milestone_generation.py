"""
Unit tests for milestone generation service.

Tests milestone count calculation, distribution algorithm, and LLM integration.
Validates: Requirements 1.4
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import event

from app.core.database import Base
from app.models import User, Project, ProjectStatus, Milestone, MilestoneStatus
from app.services.milestone_generator import MilestoneGenerator
from app.services.llm_service import LLMService
from tests.conftest import SQLiteUUID, SQLiteJSONB
from sqlalchemy.dialects.postgresql import UUID, JSONB


def create_test_session():
    """Create a fresh test database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Replace UUID and JSONB columns with SQLite-compatible types
    @event.listens_for(Base.metadata, "before_create")
    def receive_before_create(target, connection, **kw):
        """Replace PostgreSQL-specific types with SQLite-compatible types."""
        for table in target.tables.values():
            for column in table.columns:
                if isinstance(column.type, UUID):
                    column.type = SQLiteUUID()
                elif isinstance(column.type, JSONB):
                    column.type = SQLiteJSONB()
    
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return TestingSessionLocal()


class TestMilestoneCountCalculation:
    """Test milestone count calculation for various project durations."""
    
    def test_short_project_gets_3_milestones(self):
        """Projects < 2 weeks should get 3 milestones."""
        db_session = create_test_session()
        
        try:
            # Create user and project
            user = User(
                email="test@example.com",
                hashed_password="hashed",
                full_name="Test User"
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            
            # Project with 10 days deadline
            project = Project(
                user_id=user.id,
                title="Short Project",
                description="A short project",
                goal="Complete quickly",
                status=ProjectStatus.ACTIVE,
                target_completion_date=datetime.utcnow() + timedelta(days=10)
            )
            db_session.add(project)
            db_session.commit()
            db_session.refresh(project)
            
            # Create generator
            llm_service = Mock(spec=LLMService)
            generator = MilestoneGenerator(db_session, llm_service)
            
            # Calculate milestone count
            count = generator.calculate_milestone_count(project)
            
            assert count == 3, f"Short project should have 3 milestones, got {count}"
        
        finally:
            db_session.close()
    
    def test_medium_project_gets_4_milestones(self):
        """Projects 2-6 weeks should get 4 milestones."""
        db_session = create_test_session()
        
        try:
            # Create user and project
            user = User(
                email="test@example.com",
                hashed_password="hashed",
                full_name="Test User"
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            
            # Project with 4 weeks deadline
            project = Project(
                user_id=user.id,
                title="Medium Project",
                description="A medium project",
                goal="Complete in a month",
                status=ProjectStatus.ACTIVE,
                target_completion_date=datetime.utcnow() + timedelta(weeks=4)
            )
            db_session.add(project)
            db_session.commit()
            db_session.refresh(project)
            
            # Create generator
            llm_service = Mock(spec=LLMService)
            generator = MilestoneGenerator(db_session, llm_service)
            
            # Calculate milestone count
            count = generator.calculate_milestone_count(project)
            
            assert count == 4, f"Medium project should have 4 milestones, got {count}"
        
        finally:
            db_session.close()
    
    def test_long_project_gets_5_milestones(self):
        """Projects > 6 weeks should get 5 milestones."""
        db_session = create_test_session()
        
        try:
            # Create user and project
            user = User(
                email="test@example.com",
                hashed_password="hashed",
                full_name="Test User"
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            
            # Project with 10 weeks deadline
            project = Project(
                user_id=user.id,
                title="Long Project",
                description="A long project",
                goal="Complete over time",
                status=ProjectStatus.ACTIVE,
                target_completion_date=datetime.utcnow() + timedelta(weeks=10)
            )
            db_session.add(project)
            db_session.commit()
            db_session.refresh(project)
            
            # Create generator
            llm_service = Mock(spec=LLMService)
            generator = MilestoneGenerator(db_session, llm_service)
            
            # Calculate milestone count
            count = generator.calculate_milestone_count(project)
            
            assert count == 5, f"Long project should have 5 milestones, got {count}"
        
        finally:
            db_session.close()
    
    def test_no_deadline_defaults_to_4_milestones(self):
        """Projects without deadline should default to 4 milestones."""
        db_session = create_test_session()
        
        try:
            # Create user and project
            user = User(
                email="test@example.com",
                hashed_password="hashed",
                full_name="Test User"
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            
            # Project without deadline
            project = Project(
                user_id=user.id,
                title="No Deadline Project",
                description="A project without deadline",
                goal="Complete eventually",
                status=ProjectStatus.ACTIVE,
                target_completion_date=None
            )
            db_session.add(project)
            db_session.commit()
            db_session.refresh(project)
            
            # Create generator
            llm_service = Mock(spec=LLMService)
            generator = MilestoneGenerator(db_session, llm_service)
            
            # Calculate milestone count
            count = generator.calculate_milestone_count(project)
            
            assert count == 4, f"Project without deadline should default to 4 milestones, got {count}"
        
        finally:
            db_session.close()


class TestMilestoneDistribution:
    """Test milestone distribution algorithm."""
    
    def test_milestones_distributed_evenly(self):
        """Milestones should be distributed evenly across timeline."""
        db_session = create_test_session()
        
        try:
            # Create user and project
            user = User(
                email="test@example.com",
                hashed_password="hashed",
                full_name="Test User"
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            
            # Project with 30 days deadline
            deadline = datetime.utcnow() + timedelta(days=30)
            project = Project(
                user_id=user.id,
                title="Test Project",
                description="Test distribution",
                goal="Test goal",
                status=ProjectStatus.ACTIVE,
                target_completion_date=deadline
            )
            db_session.add(project)
            db_session.commit()
            db_session.refresh(project)
            
            # Create generator
            llm_service = Mock(spec=LLMService)
            generator = MilestoneGenerator(db_session, llm_service)
            
            # Distribute 4 milestones
            milestone_dates = generator.distribute_milestones(project, 4)
            
            assert len(milestone_dates) == 4, "Should have 4 milestone dates"
            
            # Check chronological order
            for i in range(len(milestone_dates) - 1):
                assert milestone_dates[i] < milestone_dates[i + 1], \
                    "Milestones should be in chronological order"
            
            # First milestone should be within 1-2 weeks
            now = datetime.utcnow()
            first_milestone_days = (milestone_dates[0] - now).days
            assert 7 <= first_milestone_days <= 14, \
                f"First milestone should be 7-14 days out, got {first_milestone_days}"
            
            # Last milestone should be near the deadline
            last_milestone_days = (milestone_dates[-1] - deadline).days
            assert abs(last_milestone_days) <= 1, \
                f"Last milestone should be near deadline, off by {last_milestone_days} days"
        
        finally:
            db_session.close()
    
    def test_no_deadline_spaces_milestones_2_weeks_apart(self):
        """Without deadline, milestones should be 2 weeks apart."""
        db_session = create_test_session()
        
        try:
            # Create user and project
            user = User(
                email="test@example.com",
                hashed_password="hashed",
                full_name="Test User"
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            
            # Project without deadline
            project = Project(
                user_id=user.id,
                title="Test Project",
                description="Test distribution",
                goal="Test goal",
                status=ProjectStatus.ACTIVE,
                target_completion_date=None
            )
            db_session.add(project)
            db_session.commit()
            db_session.refresh(project)
            
            # Create generator
            llm_service = Mock(spec=LLMService)
            generator = MilestoneGenerator(db_session, llm_service)
            
            # Distribute 3 milestones
            milestone_dates = generator.distribute_milestones(project, 3)
            
            assert len(milestone_dates) == 3, "Should have 3 milestone dates"
            
            # Check spacing is approximately 2 weeks
            now = datetime.utcnow()
            for i, date in enumerate(milestone_dates):
                expected_weeks = 2 * (i + 1)
                actual_weeks = (date - now).days / 7
                assert abs(actual_weeks - expected_weeks) < 0.5, \
                    f"Milestone {i} should be ~{expected_weeks} weeks out, got {actual_weeks}"
        
        finally:
            db_session.close()


class TestLLMIntegration:
    """Test LLM integration for milestone title generation."""
    
    @pytest.mark.asyncio
    async def test_generate_milestone_titles_success(self):
        """Test successful milestone title generation with LLM."""
        db_session = create_test_session()
        
        try:
            # Create user and project
            user = User(
                email="test@example.com",
                hashed_password="hashed",
                full_name="Test User"
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            
            project = Project(
                user_id=user.id,
                title="Build a Website",
                description="Create a portfolio website",
                goal="Launch a professional portfolio",
                status=ProjectStatus.ACTIVE,
                target_completion_date=datetime.utcnow() + timedelta(weeks=4)
            )
            db_session.add(project)
            db_session.commit()
            db_session.refresh(project)
            
            # Mock LLM service
            llm_service = Mock(spec=LLMService)
            mock_response = Mock()
            mock_response.content = [Mock(text='["Design wireframes", "Build frontend", "Deploy to production"]')]
            llm_service.client = Mock()
            llm_service.client.messages = Mock()
            llm_service.client.messages.create = AsyncMock(return_value=mock_response)
            llm_service.model = "claude-3-5-sonnet-20241022"
            
            # Create generator
            generator = MilestoneGenerator(db_session, llm_service)
            
            # Generate titles
            titles = await generator.generate_milestone_titles(project, 3)
            
            assert len(titles) == 3, "Should generate 3 titles"
            assert titles[0] == "Design wireframes"
            assert titles[1] == "Build frontend"
            assert titles[2] == "Deploy to production"
        
        finally:
            db_session.close()
    
    @pytest.mark.asyncio
    async def test_generate_milestone_titles_fallback(self):
        """Test fallback to generic titles when LLM fails."""
        db_session = create_test_session()
        
        try:
            # Create user and project
            user = User(
                email="test@example.com",
                hashed_password="hashed",
                full_name="Test User"
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            
            project = Project(
                user_id=user.id,
                title="Test Project",
                description="Test description",
                goal="Test goal",
                status=ProjectStatus.ACTIVE,
                target_completion_date=datetime.utcnow() + timedelta(weeks=4)
            )
            db_session.add(project)
            db_session.commit()
            db_session.refresh(project)
            
            # Mock LLM service to raise exception
            llm_service = Mock(spec=LLMService)
            llm_service.client = Mock()
            llm_service.client.messages = Mock()
            llm_service.client.messages.create = AsyncMock(side_effect=Exception("API Error"))
            llm_service.model = "claude-3-5-sonnet-20241022"
            
            # Create generator
            generator = MilestoneGenerator(db_session, llm_service)
            
            # Generate titles (should fallback)
            titles = await generator.generate_milestone_titles(project, 4)
            
            assert len(titles) == 4, "Should generate 4 fallback titles"
            assert titles[0] == "Milestone 1"
            assert titles[1] == "Milestone 2"
            assert titles[2] == "Milestone 3"
            assert titles[3] == "Milestone 4"
        
        finally:
            db_session.close()


class TestEndToEndMilestoneGeneration:
    """Test complete milestone generation flow."""
    
    @pytest.mark.asyncio
    async def test_generate_milestones_complete_flow(self):
        """Test complete milestone generation from start to finish."""
        db_session = create_test_session()
        
        try:
            # Create user and project
            user = User(
                email="test@example.com",
                hashed_password="hashed",
                full_name="Test User"
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            
            project = Project(
                user_id=user.id,
                title="Build Mobile App",
                description="Create a mobile app",
                goal="Launch on app stores",
                status=ProjectStatus.ACTIVE,
                target_completion_date=datetime.utcnow() + timedelta(weeks=8)
            )
            db_session.add(project)
            db_session.commit()
            db_session.refresh(project)
            
            # Mock LLM service
            llm_service = Mock(spec=LLMService)
            mock_response = Mock()
            mock_response.content = [Mock(text='["Plan features", "Design UI", "Develop MVP", "Test and refine", "Launch"]')]
            llm_service.client = Mock()
            llm_service.client.messages = Mock()
            llm_service.client.messages.create = AsyncMock(return_value=mock_response)
            llm_service.model = "claude-3-5-sonnet-20241022"
            
            # Create generator
            generator = MilestoneGenerator(db_session, llm_service)
            
            # Generate milestones
            milestones = await generator.generate_milestones(project)
            
            # Verify milestones were created
            assert len(milestones) == 5, "Should create 5 milestones for 8-week project"
            
            # Verify all milestones have required fields
            for i, milestone in enumerate(milestones):
                assert milestone.id is not None, f"Milestone {i} should have an ID"
                assert milestone.project_id == project.id, f"Milestone {i} should belong to project"
                assert milestone.title is not None, f"Milestone {i} should have a title"
                assert milestone.target_date is not None, f"Milestone {i} should have a target date"
                assert milestone.status == MilestoneStatus.PENDING, f"Milestone {i} should be PENDING"
                assert milestone.order == i, f"Milestone {i} should have order {i}"
            
            # Verify chronological order
            for i in range(len(milestones) - 1):
                assert milestones[i].target_date < milestones[i + 1].target_date, \
                    "Milestones should be in chronological order"
            
            # Verify milestones are in database
            db_milestones = db_session.query(Milestone).filter(
                Milestone.project_id == project.id
            ).all()
            
            assert len(db_milestones) == 5, "All milestones should be in database"
        
        finally:
            db_session.close()
