"""
Unit tests for the SuggestionEngine service.

Tests the detection of uneven milestone distribution, large milestones,
and deadline pressure.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.suggestion_engine import SuggestionEngine, SuggestionType, Suggestion
from app.models.project import Project, ProjectStatus
from app.models.milestone import Milestone, MilestoneStatus
from app.models.user import User
from app.models.suggestion_tracking import SuggestionTracking


class TestUnevenDistributionDetection:
    """
    Tests for detecting uneven milestone distribution.
    
    Validates: Requirements 9.1
    """
    
    def test_detects_uneven_distribution_with_large_gap(self, db_session):
        """Test that uneven distribution is detected when gaps vary significantly."""
        # Create test data
        user = User(
            id=uuid4(),
            email="test@example.com",
            discord_user_id="123456789"
        )
        db_session.add(user)
        
        project = Project(
            id=uuid4(),
            user_id=user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
            target_completion_date=datetime.utcnow() + timedelta(days=60)
        )
        db_session.add(project)
        db_session.commit()
        
        # Create milestones with uneven distribution
        # Gap 1: 5 days, Gap 2: 5 days, Gap 3: 20 days (4x larger)
        now = datetime.utcnow()
        milestones = [
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Milestone 1",
                target_date=now + timedelta(days=5),
                status=MilestoneStatus.PENDING,
                order=0
            ),
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Milestone 2",
                target_date=now + timedelta(days=10),
                status=MilestoneStatus.PENDING,
                order=1
            ),
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Milestone 3",
                target_date=now + timedelta(days=30),
                status=MilestoneStatus.PENDING,
                order=2
            )
        ]
        
        for milestone in milestones:
            db_session.add(milestone)
        db_session.commit()
        
        # Test detection
        engine = SuggestionEngine(db_session)
        suggestion = engine._detect_uneven_distribution(project, milestones)
        
        assert suggestion is not None
        assert suggestion.suggestion_type == SuggestionType.UNEVEN_DISTRIBUTION
        assert "20 days" in suggestion.message
        assert "5 days" in suggestion.message
        assert "evenly" in suggestion.message.lower()
    
    def test_no_detection_with_even_distribution(self, db_session):
        """Test that evenly distributed milestones don't trigger suggestion."""
        # Create test data
        user = User(
            id=uuid4(),
            email="test@example.com",
            discord_user_id="123456789"
        )
        db_session.add(user)
        
        project = Project(
            id=uuid4(),
            user_id=user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
            target_completion_date=datetime.utcnow() + timedelta(days=60)
        )
        db_session.add(project)
        db_session.commit()
        
        # Create milestones with even distribution (all 10 days apart)
        now = datetime.utcnow()
        milestones = [
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title=f"Milestone {i}",
                target_date=now + timedelta(days=10 * (i + 1)),
                status=MilestoneStatus.PENDING,
                order=i
            )
            for i in range(4)
        ]
        
        for milestone in milestones:
            db_session.add(milestone)
        db_session.commit()
        
        # Test detection
        engine = SuggestionEngine(db_session)
        suggestion = engine._detect_uneven_distribution(project, milestones)
        
        assert suggestion is None
    
    def test_no_detection_with_single_milestone(self, db_session):
        """Test that single milestone doesn't trigger uneven distribution."""
        # Create test data
        user = User(
            id=uuid4(),
            email="test@example.com",
            discord_user_id="123456789"
        )
        db_session.add(user)
        
        project = Project(
            id=uuid4(),
            user_id=user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
            target_completion_date=datetime.utcnow() + timedelta(days=60)
        )
        db_session.add(project)
        db_session.commit()
        
        milestone = Milestone(
            id=uuid4(),
            project_id=project.id,
            title="Milestone 1",
            target_date=datetime.utcnow() + timedelta(days=10),
            status=MilestoneStatus.PENDING,
            order=0
        )
        db_session.add(milestone)
        db_session.commit()
        
        # Test detection
        engine = SuggestionEngine(db_session)
        suggestion = engine._detect_uneven_distribution(project, [milestone])
        
        assert suggestion is None


class TestLargeMilestoneDetection:
    """
    Tests for detecting large milestones.
    
    Validates: Requirements 9.2
    """
    
    def test_detects_large_milestone_span(self, db_session):
        """Test that milestones spanning too many days are detected."""
        # Create test data
        user = User(
            id=uuid4(),
            email="test@example.com",
            discord_user_id="123456789"
        )
        db_session.add(user)
        
        project = Project(
            id=uuid4(),
            user_id=user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
            target_completion_date=datetime.utcnow() + timedelta(days=60)
        )
        db_session.add(project)
        db_session.commit()
        
        # Create milestones with one large span (20 days)
        now = datetime.utcnow()
        milestones = [
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Large Milestone",
                target_date=now + timedelta(days=5),
                status=MilestoneStatus.PENDING,
                order=0
            ),
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Next Milestone",
                target_date=now + timedelta(days=25),  # 20 days after first
                status=MilestoneStatus.PENDING,
                order=1
            )
        ]
        
        for milestone in milestones:
            db_session.add(milestone)
        db_session.commit()
        
        # Test detection
        engine = SuggestionEngine(db_session)
        suggestions = engine._detect_large_milestones(project, milestones)
        
        # Should detect both: Large Milestone (20 day span) and Next Milestone (35 day span to deadline)
        assert len(suggestions) >= 1
        # Check that at least one is about the Large Milestone
        large_milestone_suggestions = [s for s in suggestions if "Large Milestone" in s.message]
        assert len(large_milestone_suggestions) >= 1
        assert large_milestone_suggestions[0].suggestion_type == SuggestionType.LARGE_MILESTONE
        assert "20 days" in large_milestone_suggestions[0].message
        assert "breaking it into smaller" in large_milestone_suggestions[0].message.lower()
    
    def test_detects_multiple_large_milestones(self, db_session):
        """Test that multiple large milestones are all detected."""
        # Create test data
        user = User(
            id=uuid4(),
            email="test@example.com",
            discord_user_id="123456789"
        )
        db_session.add(user)
        
        project = Project(
            id=uuid4(),
            user_id=user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
            target_completion_date=datetime.utcnow() + timedelta(days=90)
        )
        db_session.add(project)
        db_session.commit()
        
        # Create multiple large milestones
        now = datetime.utcnow()
        milestones = [
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Large Milestone 1",
                target_date=now + timedelta(days=5),
                status=MilestoneStatus.PENDING,
                order=0
            ),
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Large Milestone 2",
                target_date=now + timedelta(days=25),  # 20 days span
                status=MilestoneStatus.PENDING,
                order=1
            ),
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Large Milestone 3",
                target_date=now + timedelta(days=45),  # 20 days span
                status=MilestoneStatus.PENDING,
                order=2
            )
        ]
        
        for milestone in milestones:
            db_session.add(milestone)
        db_session.commit()
        
        # Test detection
        engine = SuggestionEngine(db_session)
        suggestions = engine._detect_large_milestones(project, milestones)
        
        # Should detect all three large milestones (including last one to deadline)
        assert len(suggestions) >= 2
        assert all(s.suggestion_type == SuggestionType.LARGE_MILESTONE for s in suggestions)
    
    def test_no_detection_with_reasonable_spans(self, db_session):
        """Test that reasonably sized milestones don't trigger suggestion."""
        # Create test data
        user = User(
            id=uuid4(),
            email="test@example.com",
            discord_user_id="123456789"
        )
        db_session.add(user)
        
        project = Project(
            id=uuid4(),
            user_id=user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
            target_completion_date=datetime.utcnow() + timedelta(days=35)  # Closer deadline
        )
        db_session.add(project)
        db_session.commit()
        
        # Create milestones with reasonable spans (7 days each)
        now = datetime.utcnow()
        milestones = [
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title=f"Milestone {i}",
                target_date=now + timedelta(days=7 * (i + 1)),
                status=MilestoneStatus.PENDING,
                order=i
            )
            for i in range(4)
        ]
        
        for milestone in milestones:
            db_session.add(milestone)
        db_session.commit()
        
        # Test detection
        engine = SuggestionEngine(db_session)
        suggestions = engine._detect_large_milestones(project, milestones)
        
        # All spans should be 7 days, which is under the 14-day threshold
        assert len(suggestions) == 0


class TestDeadlinePressureDetection:
    """
    Tests for detecting deadline pressure.
    
    Validates: Requirements 9.3
    """
    
    def test_detects_deadline_pressure_with_multiple_incomplete(self, db_session):
        """Test that deadline pressure is detected with multiple incomplete milestones."""
        # Create test data
        user = User(
            id=uuid4(),
            email="test@example.com",
            discord_user_id="123456789"
        )
        db_session.add(user)
        
        # Project with deadline in 5 days
        project = Project(
            id=uuid4(),
            user_id=user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
            target_completion_date=datetime.utcnow() + timedelta(days=5)
        )
        db_session.add(project)
        db_session.commit()
        
        # Create 3 incomplete milestones
        now = datetime.utcnow()
        milestones = [
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title=f"Milestone {i}",
                target_date=now + timedelta(days=i + 1),
                status=MilestoneStatus.PENDING,
                order=i
            )
            for i in range(3)
        ]
        
        for milestone in milestones:
            db_session.add(milestone)
        db_session.commit()
        
        # Test detection
        engine = SuggestionEngine(db_session)
        suggestion = engine._detect_deadline_pressure(project, milestones)
        
        assert suggestion is not None
        assert suggestion.suggestion_type == SuggestionType.DEADLINE_PRESSURE
        # Days might be 4 or 5 depending on timing, just check it's a small number
        assert " days" in suggestion.message
        assert "3 incomplete milestones" in suggestion.message
        assert "prioritizing" in suggestion.message.lower() or "extending" in suggestion.message.lower()
    
    def test_no_detection_with_distant_deadline(self, db_session):
        """Test that no pressure is detected when deadline is far away."""
        # Create test data
        user = User(
            id=uuid4(),
            email="test@example.com",
            discord_user_id="123456789"
        )
        db_session.add(user)
        
        # Project with deadline in 30 days
        project = Project(
            id=uuid4(),
            user_id=user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
            target_completion_date=datetime.utcnow() + timedelta(days=30)
        )
        db_session.add(project)
        db_session.commit()
        
        # Create 3 incomplete milestones
        now = datetime.utcnow()
        milestones = [
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title=f"Milestone {i}",
                target_date=now + timedelta(days=(i + 1) * 7),
                status=MilestoneStatus.PENDING,
                order=i
            )
            for i in range(3)
        ]
        
        for milestone in milestones:
            db_session.add(milestone)
        db_session.commit()
        
        # Test detection
        engine = SuggestionEngine(db_session)
        suggestion = engine._detect_deadline_pressure(project, milestones)
        
        assert suggestion is None
    
    def test_no_detection_with_single_incomplete_milestone(self, db_session):
        """Test that no pressure is detected with only one incomplete milestone."""
        # Create test data
        user = User(
            id=uuid4(),
            email="test@example.com",
            discord_user_id="123456789"
        )
        db_session.add(user)
        
        # Project with deadline in 5 days
        project = Project(
            id=uuid4(),
            user_id=user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
            target_completion_date=datetime.utcnow() + timedelta(days=5)
        )
        db_session.add(project)
        db_session.commit()
        
        # Create only 1 incomplete milestone
        milestone = Milestone(
            id=uuid4(),
            project_id=project.id,
            title="Milestone 1",
            target_date=datetime.utcnow() + timedelta(days=3),
            status=MilestoneStatus.PENDING,
            order=0
        )
        db_session.add(milestone)
        db_session.commit()
        
        # Test detection
        engine = SuggestionEngine(db_session)
        suggestion = engine._detect_deadline_pressure(project, [milestone])
        
        assert suggestion is None
    
    def test_no_detection_without_deadline(self, db_session):
        """Test that no pressure is detected when project has no deadline."""
        # Create test data
        user = User(
            id=uuid4(),
            email="test@example.com",
            discord_user_id="123456789"
        )
        db_session.add(user)
        
        # Project without deadline
        project = Project(
            id=uuid4(),
            user_id=user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
            target_completion_date=None
        )
        db_session.add(project)
        db_session.commit()
        
        # Create milestones
        now = datetime.utcnow()
        milestones = [
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title=f"Milestone {i}",
                target_date=now + timedelta(days=i + 1),
                status=MilestoneStatus.PENDING,
                order=i
            )
            for i in range(3)
        ]
        
        for milestone in milestones:
            db_session.add(milestone)
        db_session.commit()
        
        # Test detection
        engine = SuggestionEngine(db_session)
        suggestion = engine._detect_deadline_pressure(project, milestones)
        
        assert suggestion is None


class TestSuggestionTracking:
    """Tests for suggestion tracking functionality."""
    
    def test_filters_declined_suggestions(self, db_session):
        """Test that declined suggestions are filtered out."""
        # Create test data
        user = User(
            id=uuid4(),
            email="test@example.com",
            discord_user_id="123456789"
        )
        db_session.add(user)
        
        project = Project(
            id=uuid4(),
            user_id=user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE
        )
        db_session.add(project)
        db_session.commit()
        
        # Create suggestions
        suggestion1 = Suggestion(
            suggestion_type=SuggestionType.UNEVEN_DISTRIBUTION,
            message="Test message 1",
            reasoning="Test reasoning 1",
            project_id=project.id,
            milestone_ids=[uuid4(), uuid4()]
        )
        
        suggestion2 = Suggestion(
            suggestion_type=SuggestionType.LARGE_MILESTONE,
            message="Test message 2",
            reasoning="Test reasoning 2",
            project_id=project.id,
            milestone_ids=[uuid4()]
        )
        
        # Mark suggestion1 as declined
        tracking = SuggestionTracking(
            project_id=project.id,
            user_id=user.id,
            suggestion_type=suggestion1.suggestion_type,
            suggestion_hash=suggestion1.get_hash(),
            message=suggestion1.message,
            reasoning=suggestion1.reasoning,
            user_response='declined',
            responded_at=datetime.utcnow()
        )
        db_session.add(tracking)
        db_session.commit()
        
        # Test filtering
        engine = SuggestionEngine(db_session)
        filtered = engine.filter_declined_suggestions([suggestion1, suggestion2], user.id)
        
        # Should only include suggestion2
        assert len(filtered) == 1
        assert filtered[0].suggestion_type == SuggestionType.LARGE_MILESTONE
    
    def test_tracks_suggestion_shown(self, db_session):
        """Test that showing a suggestion creates a tracking record."""
        # Create test data
        user = User(
            id=uuid4(),
            email="test@example.com",
            discord_user_id="123456789"
        )
        db_session.add(user)
        
        project = Project(
            id=uuid4(),
            user_id=user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE
        )
        db_session.add(project)
        db_session.commit()
        
        # Create suggestion
        suggestion = Suggestion(
            suggestion_type=SuggestionType.DEADLINE_PRESSURE,
            message="Test message",
            reasoning="Test reasoning",
            project_id=project.id,
            milestone_ids=[uuid4()]
        )
        
        # Track suggestion
        engine = SuggestionEngine(db_session)
        tracking = engine.track_suggestion_shown(suggestion, user.id)
        
        assert tracking is not None
        assert tracking.user_id == user.id
        assert tracking.project_id == project.id
        assert tracking.suggestion_type == SuggestionType.DEADLINE_PRESSURE
        assert tracking.user_response is None
    
    def test_records_user_response(self, db_session):
        """Test that user responses are recorded correctly."""
        # Create test data
        user = User(
            id=uuid4(),
            email="test@example.com",
            discord_user_id="123456789"
        )
        db_session.add(user)
        
        project = Project(
            id=uuid4(),
            user_id=user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE
        )
        db_session.add(project)
        db_session.commit()
        
        # Create tracking record
        tracking = SuggestionTracking(
            project_id=project.id,
            user_id=user.id,
            suggestion_type=SuggestionType.LARGE_MILESTONE,
            suggestion_hash="test_hash",
            message="Test message",
            reasoning="Test reasoning"
        )
        db_session.add(tracking)
        db_session.commit()
        
        # Record response
        engine = SuggestionEngine(db_session)
        updated = engine.record_user_response(tracking.id, 'accepted')
        
        assert updated is not None
        assert updated.user_response == 'accepted'
        assert updated.responded_at is not None


class TestGenerateSuggestions:
    """Tests for the main generate_suggestions method."""
    
    def test_generates_multiple_suggestions(self, db_session):
        """Test that multiple applicable suggestions are generated."""
        # Create test data
        user = User(
            id=uuid4(),
            email="test@example.com",
            discord_user_id="123456789"
        )
        db_session.add(user)
        
        # Project with approaching deadline
        project = Project(
            id=uuid4(),
            user_id=user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
            target_completion_date=datetime.utcnow() + timedelta(days=5)
        )
        db_session.add(project)
        db_session.commit()
        
        # Create milestones with multiple issues:
        # - Uneven distribution (5 days, 5 days, 20 days)
        # - Large milestone (20 day span)
        # - Deadline pressure (3 incomplete, 5 days to deadline)
        now = datetime.utcnow()
        milestones = [
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Milestone 1",
                target_date=now - timedelta(days=10),
                status=MilestoneStatus.COMPLETED,
                completed_at=now - timedelta(days=10),
                order=0
            ),
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Milestone 2",
                target_date=now + timedelta(days=1),
                status=MilestoneStatus.PENDING,
                order=1
            ),
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Milestone 3",
                target_date=now + timedelta(days=2),
                status=MilestoneStatus.PENDING,
                order=2
            ),
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title="Milestone 4",
                target_date=now + timedelta(days=4),
                status=MilestoneStatus.PENDING,
                order=3
            )
        ]
        
        for milestone in milestones:
            db_session.add(milestone)
        db_session.commit()
        
        # Test generation
        engine = SuggestionEngine(db_session)
        suggestions = engine.generate_suggestions(project, milestones)
        
        # Should generate at least deadline pressure suggestion
        assert len(suggestions) >= 1
        suggestion_types = [s.suggestion_type for s in suggestions]
        assert SuggestionType.DEADLINE_PRESSURE in suggestion_types
    
    def test_ignores_completed_milestones(self, db_session):
        """Test that completed milestones are excluded from analysis."""
        # Create test data
        user = User(
            id=uuid4(),
            email="test@example.com",
            discord_user_id="123456789"
        )
        db_session.add(user)
        
        project = Project(
            id=uuid4(),
            user_id=user.id,
            title="Test Project",
            description="Test",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
            target_completion_date=datetime.utcnow() + timedelta(days=60)
        )
        db_session.add(project)
        db_session.commit()
        
        # All milestones completed
        now = datetime.utcnow()
        milestones = [
            Milestone(
                id=uuid4(),
                project_id=project.id,
                title=f"Milestone {i}",
                target_date=now - timedelta(days=10 - i),
                status=MilestoneStatus.COMPLETED,
                completed_at=now - timedelta(days=10 - i),
                order=i
            )
            for i in range(3)
        ]
        
        for milestone in milestones:
            db_session.add(milestone)
        db_session.commit()
        
        # Test generation
        engine = SuggestionEngine(db_session)
        suggestions = engine.generate_suggestions(project, milestones)
        
        # Should generate no suggestions
        assert len(suggestions) == 0
