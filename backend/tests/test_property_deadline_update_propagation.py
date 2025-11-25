"""
Property-based tests for deadline update propagation.

Feature: discord-project-plan-management, Property 4: Deadline update propagation
Validates: Requirements 4.1, 4.2, 4.5
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import event

from app.core.database import Base
from app.models import User, Project, ProjectStatus, Milestone, MilestoneStatus
from app.services.timeline_adjuster import TimelineAdjuster
from tests.conftest import SQLiteUUID, SQLiteJSONB
from sqlalchemy.dialects.postgresql import UUID, JSONB


@st.composite
def user_data(draw):
    """Generate valid user data."""
    return {
        "email": draw(st.emails()),
        "hashed_password": draw(st.text(min_size=10, max_size=100)),
        "full_name": draw(st.text(min_size=1, max_size=100)),
    }


@st.composite
def project_with_deadline(draw):
    """Generate valid project data with a deadline."""
    # Generate a deadline between 7 and 90 days from now
    days_ahead = draw(st.integers(min_value=7, max_value=90))
    deadline = datetime.utcnow() + timedelta(days=days_ahead)
    
    return {
        "title": draw(st.text(min_size=1, max_size=100)),
        "description": draw(st.text(min_size=1, max_size=500)),
        "goal": draw(st.text(min_size=1, max_size=500)),
        "status": ProjectStatus.ACTIVE,
        "target_completion_date": deadline,
    }


@st.composite
def milestone_data(draw, project_start: datetime, project_deadline: datetime):
    """Generate valid milestone data within project timeline."""
    # Generate a target date between project start and deadline
    total_seconds = (project_deadline - project_start).total_seconds()
    offset_seconds = draw(st.integers(min_value=0, max_value=int(total_seconds)))
    target_date = project_start + timedelta(seconds=offset_seconds)
    
    return {
        "title": draw(st.text(min_size=1, max_size=200)),
        "description": draw(st.text(min_size=0, max_size=500)),
        "target_date": target_date,
        "status": MilestoneStatus.PENDING,
        "order": draw(st.integers(min_value=0, max_value=100)),
    }


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


@settings(max_examples=100, deadline=None)
@given(
    user=user_data(),
    project=project_with_deadline(),
    milestone_count=st.integers(min_value=2, max_value=10),
    deadline_change_days=st.integers(min_value=-30, max_value=60)
)
@pytest.mark.asyncio
async def test_deadline_update_propagation(user, project, milestone_count, deadline_change_days):
    """
    Property 4: Deadline update propagation
    
    For any project deadline change, if the user confirms milestone adjustment,
    then all milestone dates should be recalculated to fit within the new timeline.
    
    This test verifies that:
    1. When a deadline is updated, milestone adjustments are calculated
    2. All incomplete milestones are adjusted proportionally
    3. Completed milestones are not adjusted
    4. The adjusted dates fit within the new timeline
    5. Milestones maintain chronological order
    6. Minimum spacing warnings are generated when appropriate
    
    Validates: Requirements 4.1, 4.2, 4.5
    """
    # Skip if deadline change would result in past deadline
    assume(deadline_change_days >= -20)
    
    # Create a fresh session for this test run
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(**user)
        db_session.add(db_user)
        db_session.commit()
        db_session.refresh(db_user)
        
        # Create project
        db_project = Project(user_id=db_user.id, **project)
        db_session.add(db_project)
        db_session.commit()
        db_session.refresh(db_project)
        
        old_deadline = db_project.target_completion_date
        now = datetime.utcnow()
        
        # Create milestones distributed across the timeline
        milestones = []
        project_duration = (old_deadline - now).total_seconds()
        
        for i in range(milestone_count):
            # Distribute milestones evenly
            offset = (project_duration / (milestone_count + 1)) * (i + 1)
            target_date = now + timedelta(seconds=offset)
            
            milestone = Milestone(
                project_id=db_project.id,
                title=f"Milestone {i + 1}",
                description=f"Description for milestone {i + 1}",
                target_date=target_date,
                status=MilestoneStatus.PENDING,
                order=i
            )
            db_session.add(milestone)
            milestones.append(milestone)
        
        db_session.commit()
        
        # Refresh all milestones
        for milestone in milestones:
            db_session.refresh(milestone)
        
        # Mark some milestones as completed (randomly)
        completed_count = milestone_count // 3  # Complete about 1/3 of milestones
        for i in range(completed_count):
            milestones[i].status = MilestoneStatus.COMPLETED
            milestones[i].completed_at = datetime.utcnow()
        
        db_session.commit()
        
        # Calculate new deadline
        new_deadline = old_deadline + timedelta(days=deadline_change_days)
        
        # Skip if new deadline is in the past
        assume(new_deadline > now)
        
        # Create timeline adjuster and update deadline
        adjuster = TimelineAdjuster(db_session)
        result = await adjuster.update_deadline(
            project_id=db_project.id,
            new_deadline=new_deadline,
            adjust_milestones=True
        )
        
        # Property verification 1: Project deadline is updated
        assert result['project'].target_completion_date == new_deadline, \
            "Project deadline should be updated to new deadline"
        
        # Property verification 2: Adjusted milestones are calculated
        adjusted_milestones = result['adjusted_milestones']
        incomplete_count = milestone_count - completed_count
        
        assert len(adjusted_milestones) == incomplete_count, \
            f"Should have {incomplete_count} adjusted milestones (only incomplete ones), got {len(adjusted_milestones)}"
        
        # Property verification 3: All adjusted dates are within new timeline
        # Allow for dates to be slightly after deadline due to end-of-day rounding
        for adjustment in adjusted_milestones:
            new_date = adjustment['new_date']
            # Allow up to 24 hours after deadline for end-of-day rounding
            max_allowed = new_deadline + timedelta(days=1)
            assert now <= new_date <= max_allowed, \
                f"Adjusted milestone date {new_date} should be between now and new deadline {new_deadline} (with 1 day buffer for rounding)"
        
        # Property verification 4: Milestones maintain chronological order
        sorted_adjustments = sorted(adjusted_milestones, key=lambda x: x['new_date'])
        assert sorted_adjustments == adjusted_milestones, \
            "Adjusted milestones should maintain chronological order"
        
        # Property verification 5: Apply adjustments and verify persistence
        updated_milestones = await adjuster.apply_milestone_adjustments(adjusted_milestones)
        
        assert len(updated_milestones) == len(adjusted_milestones), \
            "All milestone adjustments should be applied"
        
        # Verify each milestone was updated correctly
        for adjustment in adjusted_milestones:
            milestone = db_session.query(Milestone).filter(
                Milestone.id == adjustment['milestone_id']
            ).first()
            
            assert milestone is not None, \
                f"Milestone {adjustment['milestone_id']} should exist"
            
            assert milestone.target_date == adjustment['new_date'], \
                f"Milestone target_date should be updated to {adjustment['new_date']}"
        
        # Property verification 6: Completed milestones are not adjusted
        for i in range(completed_count):
            completed_milestone = db_session.query(Milestone).filter(
                Milestone.id == milestones[i].id
            ).first()
            
            assert completed_milestone.status == MilestoneStatus.COMPLETED, \
                "Completed milestones should remain completed"
            
            # Check that this milestone was not in the adjusted list
            adjusted_ids = [adj['milestone_id'] for adj in adjusted_milestones]
            assert completed_milestone.id not in adjusted_ids, \
                "Completed milestones should not be in the adjusted list"
        
        # Property verification 7: Warnings are generated for compressed timelines
        # Check if the new timeline is significantly shorter (>30% reduction)
        old_duration = (old_deadline - now).total_seconds()
        new_duration = (new_deadline - now).total_seconds()
        
        if new_duration < old_duration * 0.7:  # More than 30% reduction
            # Should have warnings about compressed timeline
            assert len(result['warnings']) > 0, \
                f"Should have warnings when deadline is significantly shortened (old: {old_duration}s, new: {new_duration}s)"
        
        # Property verification 8: All milestones still belong to the project
        all_milestones = db_session.query(Milestone).filter(
            Milestone.project_id == db_project.id
        ).all()
        
        assert len(all_milestones) == milestone_count, \
            f"Should still have {milestone_count} milestones after adjustment"
    
    finally:
        db_session.close()


@settings(max_examples=100, deadline=None)
@given(
    user=user_data(),
    project=project_with_deadline(),
    milestone_count=st.integers(min_value=3, max_value=8)
)
@pytest.mark.asyncio
async def test_minimum_spacing_validation(user, project, milestone_count):
    """
    Test that minimum spacing validation works correctly.
    
    When milestones are too close together (< 3 days), warnings should be generated.
    """
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(**user)
        db_session.add(db_user)
        db_session.commit()
        db_session.refresh(db_user)
        
        # Create project with short timeline
        db_project = Project(user_id=db_user.id, **project)
        # Force a very short timeline (milestone_count days)
        db_project.target_completion_date = datetime.utcnow() + timedelta(days=milestone_count)
        db_session.add(db_project)
        db_session.commit()
        db_session.refresh(db_project)
        
        old_deadline = db_project.target_completion_date
        now = datetime.utcnow()
        
        # Create milestones very close together
        milestones = []
        for i in range(milestone_count):
            target_date = now + timedelta(days=i + 1)
            
            milestone = Milestone(
                project_id=db_project.id,
                title=f"Milestone {i + 1}",
                target_date=target_date,
                status=MilestoneStatus.PENDING,
                order=i
            )
            db_session.add(milestone)
            milestones.append(milestone)
        
        db_session.commit()
        
        # Shorten the deadline even more
        new_deadline = now + timedelta(days=milestone_count // 2)
        
        # Skip if new deadline is too close
        assume(new_deadline > now + timedelta(days=1))
        
        # Update deadline
        adjuster = TimelineAdjuster(db_session)
        result = await adjuster.update_deadline(
            project_id=db_project.id,
            new_deadline=new_deadline,
            adjust_milestones=True
        )
        
        # Should have warnings about spacing
        assert len(result['warnings']) > 0, \
            "Should have warnings when milestones are compressed with insufficient spacing"
        
        # Check that at least one warning mentions spacing
        spacing_warning_found = any(
            'spacing' in warning.lower() or 'compressed' in warning.lower()
            for warning in result['warnings']
        )
        
        assert spacing_warning_found, \
            "Should have a warning about spacing or compressed timeline"
    
    finally:
        db_session.close()
