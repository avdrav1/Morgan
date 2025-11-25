"""
Timeline Adjuster Service for adjusting milestone dates when deadlines change.

This service handles proportional adjustment of milestone dates when a project
deadline is updated, ensuring minimum spacing and realistic timelines.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.milestone import Milestone, MilestoneStatus
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class TimelineAdjuster:
    """
    Service for adjusting project timelines when deadlines change.
    
    Handles proportional date adjustment with minimum spacing validation
    and provides warnings for compressed timelines.
    
    Validates: Requirements 4.1, 4.2, 4.5
    """
    
    # Minimum spacing between milestones (3 days)
    MIN_MILESTONE_SPACING = timedelta(days=3)
    
    def __init__(self, db: Session):
        """
        Initialize the timeline adjuster.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def calculate_adjusted_dates(
        self,
        milestones: List[Milestone],
        old_deadline: datetime,
        new_deadline: datetime
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Calculate new milestone dates based on deadline change.
        
        Uses proportional adjustment: each milestone moves by the same
        proportion as the deadline change.
        
        Args:
            milestones: List of milestones to adjust (only incomplete ones)
            old_deadline: Previous project deadline
            new_deadline: New project deadline
            
        Returns:
            Tuple of (adjusted_milestones, warnings)
            - adjusted_milestones: List of dicts with milestone_id and new_date
            - warnings: List of warning messages about timeline issues
        """
        now = datetime.utcnow()
        warnings = []
        adjusted_milestones = []
        
        # Filter to only incomplete milestones
        incomplete_milestones = [
            m for m in milestones
            if m.status != MilestoneStatus.COMPLETED
        ]
        
        if not incomplete_milestones:
            return [], []
        
        # Calculate the ratio of timeline change
        old_duration = (old_deadline - now).total_seconds()
        new_duration = (new_deadline - now).total_seconds()
        
        if old_duration <= 0:
            # Old deadline was in the past, distribute evenly
            logger.warning(
                "Old deadline was in the past, using even distribution",
                extra={
                    'extra_fields': {
                        'event': 'old_deadline_past',
                        'old_deadline': old_deadline.isoformat(),
                        'new_deadline': new_deadline.isoformat()
                    }
                }
            )
            
            # Distribute milestones evenly from now to new deadline
            interval = new_duration / len(incomplete_milestones)
            for i, milestone in enumerate(incomplete_milestones):
                new_date = now + timedelta(seconds=interval * (i + 1))
                adjusted_milestones.append({
                    'milestone_id': milestone.id,
                    'milestone_title': milestone.title,
                    'old_date': milestone.target_date,
                    'new_date': new_date
                })
        else:
            # Calculate proportional adjustment
            ratio = new_duration / old_duration
            
            for milestone in incomplete_milestones:
                # Calculate how far this milestone was from now
                old_offset = (milestone.target_date - now).total_seconds()
                
                # Apply the same ratio
                new_offset = old_offset * ratio
                new_date = now + timedelta(seconds=new_offset)
                
                # Round to end of day for clarity, but don't exceed deadline
                new_date = new_date.replace(
                    hour=23, minute=59, second=59, microsecond=0
                )
                
                # Ensure we don't exceed the deadline
                if new_date > new_deadline:
                    new_date = new_deadline
                
                adjusted_milestones.append({
                    'milestone_id': milestone.id,
                    'milestone_title': milestone.title,
                    'old_date': milestone.target_date,
                    'new_date': new_date
                })
        
        # Validate minimum spacing
        adjusted_milestones.sort(key=lambda x: x['new_date'])
        
        spacing_violations = []
        for i in range(len(adjusted_milestones) - 1):
            current = adjusted_milestones[i]
            next_milestone = adjusted_milestones[i + 1]
            
            spacing = next_milestone['new_date'] - current['new_date']
            if spacing < self.MIN_MILESTONE_SPACING:
                spacing_violations.append({
                    'milestone1': current['milestone_title'],
                    'milestone2': next_milestone['milestone_title'],
                    'spacing_days': spacing.days
                })
        
        # Generate warnings
        if spacing_violations:
            warnings.append(
                f"⚠️ Warning: {len(spacing_violations)} milestone pair(s) have less than "
                f"3 days spacing. This timeline may be too compressed."
            )
        
        # Check if timeline is significantly shortened
        if new_duration < old_duration * 0.7:  # More than 30% reduction
            warnings.append(
                "⚠️ Warning: The new deadline is significantly shorter than the original. "
                "Consider reviewing if all milestones are still achievable."
            )
        
        return adjusted_milestones, warnings
    
    async def update_deadline(
        self,
        project_id: UUID,
        new_deadline: datetime,
        adjust_milestones: bool = True
    ) -> Dict[str, Any]:
        """
        Update project deadline and optionally adjust milestone dates.
        
        This is the main entry point for deadline updates. It:
        1. Updates the project deadline
        2. Calculates adjusted milestone dates if requested
        3. Returns proposed changes for user confirmation
        
        The actual milestone updates should only happen after user confirmation.
        
        Args:
            project_id: UUID of the project
            new_deadline: New deadline for the project
            adjust_milestones: Whether to adjust milestone dates
            
        Returns:
            Dict containing:
            - project: Updated project
            - old_deadline: Previous deadline
            - new_deadline: New deadline
            - adjusted_milestones: List of proposed milestone changes (if adjust_milestones=True)
            - warnings: List of warning messages
            - requires_confirmation: Whether user confirmation is needed
            
        Validates: Requirements 4.1, 4.2, 4.5
        """
        logger.info(
            "Updating project deadline",
            extra={
                'extra_fields': {
                    'event': 'update_deadline_start',
                    'project_id': str(project_id),
                    'new_deadline': new_deadline.isoformat(),
                    'adjust_milestones': adjust_milestones
                }
            }
        )
        
        # Get the project
        project = self.db.query(Project).filter(Project.id == project_id).first()
        
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        old_deadline = project.target_completion_date
        
        # Log before state
        logger.info(
            "Project deadline before update",
            extra={
                'extra_fields': {
                    'event': 'deadline_before_update',
                    'project_id': str(project_id),
                    'old_deadline': old_deadline.isoformat() if old_deadline else None
                }
            }
        )
        
        # Update project deadline
        project.target_completion_date = new_deadline
        project.updated_at = datetime.utcnow()
        
        # Log after state
        logger.info(
            "Project deadline after update",
            extra={
                'extra_fields': {
                    'event': 'deadline_after_update',
                    'project_id': str(project_id),
                    'new_deadline': new_deadline.isoformat(),
                    'change_days': (new_deadline - old_deadline).days if old_deadline else None
                }
            }
        )
        
        result = {
            'project': project,
            'old_deadline': old_deadline,
            'new_deadline': new_deadline,
            'adjusted_milestones': [],
            'warnings': [],
            'requires_confirmation': False
        }
        
        if adjust_milestones and old_deadline:
            # Get incomplete milestones
            milestones = (
                self.db.query(Milestone)
                .filter(
                    Milestone.project_id == project_id,
                    Milestone.status != MilestoneStatus.COMPLETED
                )
                .order_by(Milestone.target_date.asc())
                .all()
            )
            
            if milestones:
                # Calculate adjusted dates
                adjusted_milestones, warnings = self.calculate_adjusted_dates(
                    milestones,
                    old_deadline,
                    new_deadline
                )
                
                result['adjusted_milestones'] = adjusted_milestones
                result['warnings'] = warnings
                result['requires_confirmation'] = True
        
        # Commit the project deadline change
        # (milestone changes will be applied separately after confirmation)
        self.db.commit()
        self.db.refresh(project)
        
        logger.info(
            "Project deadline updated",
            extra={
                'extra_fields': {
                    'event': 'update_deadline_complete',
                    'project_id': str(project_id),
                    'milestones_to_adjust': len(result['adjusted_milestones']),
                    'warnings_count': len(result['warnings'])
                }
            }
        )
        
        return result
    
    async def apply_milestone_adjustments(
        self,
        adjusted_milestones: List[Dict[str, Any]]
    ) -> List[Milestone]:
        """
        Apply the milestone date adjustments after user confirmation.
        
        This should only be called after the user has confirmed the changes.
        
        Args:
            adjusted_milestones: List of milestone adjustments from calculate_adjusted_dates
            
        Returns:
            List of updated Milestone objects
        """
        logger.info(
            "Applying milestone adjustments",
            extra={
                'extra_fields': {
                    'event': 'apply_milestone_adjustments',
                    'milestone_count': len(adjusted_milestones)
                }
            }
        )
        
        updated_milestones = []
        
        for adjustment in adjusted_milestones:
            milestone = self.db.query(Milestone).filter(
                Milestone.id == adjustment['milestone_id']
            ).first()
            
            if milestone:
                milestone.target_date = adjustment['new_date']
                milestone.updated_at = datetime.utcnow()
                updated_milestones.append(milestone)
        
        self.db.commit()
        
        # Refresh all milestones
        for milestone in updated_milestones:
            self.db.refresh(milestone)
        
        logger.info(
            "Milestone adjustments applied",
            extra={
                'extra_fields': {
                    'event': 'milestone_adjustments_applied',
                    'updated_count': len(updated_milestones)
                }
            }
        )
        
        return updated_milestones
