"""
Suggestion Engine for proactive project plan improvements.

This service analyzes project plans and generates suggestions for
improvements such as better milestone distribution, breaking down
large milestones, and deadline pressure warnings.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
import hashlib
import json

from app.models.project import Project
from app.models.milestone import Milestone, MilestoneStatus
from app.models.suggestion_tracking import SuggestionTracking
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class SuggestionType:
    """Types of suggestions that can be generated."""
    UNEVEN_DISTRIBUTION = "uneven_distribution"
    LARGE_MILESTONE = "large_milestone"
    DEADLINE_PRESSURE = "deadline_pressure"


class Suggestion:
    """Represents a suggestion for project plan improvement."""
    
    def __init__(
        self,
        suggestion_type: str,
        message: str,
        reasoning: str,
        project_id: UUID,
        milestone_ids: Optional[List[UUID]] = None
    ):
        """
        Initialize a suggestion.
        
        Args:
            suggestion_type: Type of suggestion (from SuggestionType)
            message: User-facing suggestion message
            reasoning: Explanation of why this suggestion is being made
            project_id: UUID of the project this suggestion is for
            milestone_ids: Optional list of milestone IDs related to this suggestion
        """
        self.suggestion_type = suggestion_type
        self.message = message
        self.reasoning = reasoning
        self.project_id = project_id
        self.milestone_ids = milestone_ids or []
        self.created_at = datetime.utcnow()
    
    def get_hash(self) -> str:
        """
        Generate a hash for this suggestion for deduplication.
        
        Returns:
            Hash string based on suggestion type and key content
        """
        # Create a hash based on type and milestone IDs to identify similar suggestions
        content = f"{self.suggestion_type}:{sorted([str(m) for m in self.milestone_ids])}"
        return hashlib.md5(content.encode()).hexdigest()


class SuggestionEngine:
    """
    Service for generating proactive suggestions about project plans.
    
    Analyzes project plans to detect issues like uneven milestone distribution,
    overly large milestones, and deadline pressure.
    """
    
    # Configuration constants
    MIN_DAYS_BETWEEN_MILESTONES = 3
    MAX_DAYS_BETWEEN_MILESTONES = 21  # 3 weeks
    LARGE_MILESTONE_THRESHOLD_DAYS = 14  # 2 weeks
    DEADLINE_PRESSURE_THRESHOLD_DAYS = 7  # 1 week
    UNEVEN_DISTRIBUTION_RATIO = 2.5  # If one gap is 2.5x another, it's uneven
    
    def __init__(self, db: Session):
        """
        Initialize the suggestion engine.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def generate_suggestions(
        self,
        project: Project,
        milestones: List[Milestone]
    ) -> List[Suggestion]:
        """
        Generate all applicable suggestions for a project.
        
        Args:
            project: The project to analyze
            milestones: List of milestones for the project
            
        Returns:
            List of Suggestion objects
            
        Validates: Requirements 9.1, 9.2, 9.3, 9.4
        """
        suggestions = []
        
        # Only analyze incomplete milestones
        incomplete_milestones = [
            m for m in milestones
            if m.status != MilestoneStatus.COMPLETED
        ]
        
        if not incomplete_milestones:
            logger.info(
                "No incomplete milestones to analyze",
                extra={
                    'extra_fields': {
                        'event': 'no_incomplete_milestones',
                        'project_id': str(project.id)
                    }
                }
            )
            return suggestions
        
        # Check for uneven distribution
        uneven_suggestion = self._detect_uneven_distribution(
            project, incomplete_milestones
        )
        if uneven_suggestion:
            suggestions.append(uneven_suggestion)
        
        # Check for large milestones
        large_milestone_suggestions = self._detect_large_milestones(
            project, incomplete_milestones
        )
        suggestions.extend(large_milestone_suggestions)
        
        # Check for deadline pressure
        deadline_suggestion = self._detect_deadline_pressure(
            project, incomplete_milestones
        )
        if deadline_suggestion:
            suggestions.append(deadline_suggestion)
        
        logger.info(
            "Generated suggestions",
            extra={
                'extra_fields': {
                    'event': 'suggestions_generated',
                    'project_id': str(project.id),
                    'suggestion_count': len(suggestions)
                }
            }
        )
        
        return suggestions
    
    def _detect_uneven_distribution(
        self,
        project: Project,
        milestones: List[Milestone]
    ) -> Optional[Suggestion]:
        """
        Detect if milestones are unevenly distributed across the timeline.
        
        Args:
            project: The project to analyze
            milestones: List of incomplete milestones
            
        Returns:
            Suggestion if uneven distribution detected, None otherwise
            
        Validates: Requirements 9.1
        """
        if len(milestones) < 2:
            return None
        
        # Sort milestones by target date
        sorted_milestones = sorted(milestones, key=lambda m: m.target_date)
        
        # Calculate gaps between consecutive milestones
        gaps = []
        for i in range(len(sorted_milestones) - 1):
            gap_days = (
                sorted_milestones[i + 1].target_date - sorted_milestones[i].target_date
            ).days
            gaps.append(gap_days)
        
        if not gaps:
            return None
        
        # Check if any gap is significantly larger than others
        min_gap = min(gaps)
        max_gap = max(gaps)
        
        # Avoid division by zero
        if min_gap == 0:
            min_gap = 1
        
        # If the largest gap is more than UNEVEN_DISTRIBUTION_RATIO times the smallest
        if max_gap / min_gap >= self.UNEVEN_DISTRIBUTION_RATIO:
            message = (
                f"Your milestones are unevenly spaced. The largest gap is {max_gap} days "
                f"while the smallest is {min_gap} days. Consider redistributing them "
                f"more evenly for better progress tracking."
            )
            reasoning = (
                f"Detected uneven milestone distribution with max gap of {max_gap} days "
                f"and min gap of {min_gap} days (ratio: {max_gap/min_gap:.1f}x)"
            )
            
            return Suggestion(
                suggestion_type=SuggestionType.UNEVEN_DISTRIBUTION,
                message=message,
                reasoning=reasoning,
                project_id=project.id,
                milestone_ids=[m.id for m in sorted_milestones]
            )
        
        return None
    
    def _detect_large_milestones(
        self,
        project: Project,
        milestones: List[Milestone]
    ) -> List[Suggestion]:
        """
        Detect milestones that span too many days.
        
        Args:
            project: The project to analyze
            milestones: List of incomplete milestones
            
        Returns:
            List of suggestions for large milestones
            
        Validates: Requirements 9.2
        """
        suggestions = []
        
        if len(milestones) < 2:
            return suggestions
        
        # Sort milestones by target date
        sorted_milestones = sorted(milestones, key=lambda m: m.target_date)
        
        # Check each milestone's span (time until next milestone or deadline)
        for i, milestone in enumerate(sorted_milestones):
            # Determine the end date for this milestone
            if i < len(sorted_milestones) - 1:
                # Next milestone's date
                end_date = sorted_milestones[i + 1].target_date
            elif project.target_completion_date:
                # Project deadline
                end_date = project.target_completion_date
            else:
                # No clear end date, skip
                continue
            
            # Calculate span in days
            span_days = (end_date - milestone.target_date).days
            
            if span_days > self.LARGE_MILESTONE_THRESHOLD_DAYS:
                message = (
                    f"The milestone '{milestone.title}' spans {span_days} days. "
                    f"Consider breaking it into smaller milestones for better "
                    f"progress tracking and motivation."
                )
                reasoning = (
                    f"Milestone '{milestone.title}' has a span of {span_days} days, "
                    f"which exceeds the threshold of {self.LARGE_MILESTONE_THRESHOLD_DAYS} days"
                )
                
                suggestions.append(Suggestion(
                    suggestion_type=SuggestionType.LARGE_MILESTONE,
                    message=message,
                    reasoning=reasoning,
                    project_id=project.id,
                    milestone_ids=[milestone.id]
                ))
        
        return suggestions
    
    def _detect_deadline_pressure(
        self,
        project: Project,
        milestones: List[Milestone]
    ) -> Optional[Suggestion]:
        """
        Detect if there are many incomplete milestones close to the deadline.
        
        Args:
            project: The project to analyze
            milestones: List of incomplete milestones
            
        Returns:
            Suggestion if deadline pressure detected, None otherwise
            
        Validates: Requirements 9.3
        """
        if not project.target_completion_date:
            return None
        
        now = datetime.utcnow()
        days_until_deadline = (project.target_completion_date - now).days
        
        # Only trigger if deadline is approaching
        if days_until_deadline > self.DEADLINE_PRESSURE_THRESHOLD_DAYS:
            return None
        
        # Count incomplete milestones
        incomplete_count = len(milestones)
        
        # If there are multiple incomplete milestones close to deadline
        if incomplete_count >= 2:
            message = (
                f"Your project deadline is in {days_until_deadline} days, but you have "
                f"{incomplete_count} incomplete milestones. Consider prioritizing the most "
                f"critical milestones or extending your deadline."
            )
            reasoning = (
                f"Deadline pressure detected: {days_until_deadline} days until deadline "
                f"with {incomplete_count} incomplete milestones"
            )
            
            return Suggestion(
                suggestion_type=SuggestionType.DEADLINE_PRESSURE,
                message=message,
                reasoning=reasoning,
                project_id=project.id,
                milestone_ids=[m.id for m in milestones]
            )
        
        return None
    
    def filter_declined_suggestions(
        self,
        suggestions: List[Suggestion],
        user_id: UUID
    ) -> List[Suggestion]:
        """
        Filter out suggestions that the user has previously declined.
        
        Args:
            suggestions: List of suggestions to filter
            user_id: UUID of the user
            
        Returns:
            Filtered list of suggestions (excluding declined ones)
            
        Validates: Requirements 9.5
        """
        if not suggestions:
            return suggestions
        
        # Get all declined suggestions for this user
        declined_hashes = set()
        declined_records = (
            self.db.query(SuggestionTracking)
            .filter(
                SuggestionTracking.user_id == user_id,
                SuggestionTracking.user_response == 'declined'
            )
            .all()
        )
        
        for record in declined_records:
            declined_hashes.add(record.suggestion_hash)
        
        # Filter out suggestions with matching hashes
        filtered = []
        for suggestion in suggestions:
            suggestion_hash = suggestion.get_hash()
            if suggestion_hash not in declined_hashes:
                filtered.append(suggestion)
            else:
                logger.info(
                    "Filtered out declined suggestion",
                    extra={
                        'extra_fields': {
                            'event': 'suggestion_filtered',
                            'user_id': str(user_id),
                            'suggestion_type': suggestion.suggestion_type,
                            'suggestion_hash': suggestion_hash
                        }
                    }
                )
        
        return filtered
    
    def track_suggestion_shown(
        self,
        suggestion: Suggestion,
        user_id: UUID
    ) -> SuggestionTracking:
        """
        Track that a suggestion was shown to the user.
        
        Args:
            suggestion: The suggestion that was shown
            user_id: UUID of the user
            
        Returns:
            The created SuggestionTracking record
            
        Validates: Requirements 9.5
        """
        tracking = SuggestionTracking(
            project_id=suggestion.project_id,
            user_id=user_id,
            suggestion_type=suggestion.suggestion_type,
            suggestion_hash=suggestion.get_hash(),
            message=suggestion.message,
            reasoning=suggestion.reasoning,
            shown_at=datetime.utcnow()
        )
        
        self.db.add(tracking)
        self.db.commit()
        self.db.refresh(tracking)
        
        logger.info(
            "Tracked suggestion shown",
            extra={
                'extra_fields': {
                    'event': 'suggestion_tracked',
                    'user_id': str(user_id),
                    'project_id': str(suggestion.project_id),
                    'suggestion_type': suggestion.suggestion_type,
                    'tracking_id': str(tracking.id)
                }
            }
        )
        
        return tracking
    
    def record_user_response(
        self,
        tracking_id: UUID,
        response: str
    ) -> Optional[SuggestionTracking]:
        """
        Record the user's response to a suggestion.
        
        Args:
            tracking_id: UUID of the tracking record
            response: User's response ('accepted' or 'declined')
            
        Returns:
            Updated SuggestionTracking record, or None if not found
            
        Validates: Requirements 9.5
        """
        tracking = (
            self.db.query(SuggestionTracking)
            .filter(SuggestionTracking.id == tracking_id)
            .first()
        )
        
        if not tracking:
            logger.warning(
                "Tracking record not found",
                extra={
                    'extra_fields': {
                        'event': 'tracking_not_found',
                        'tracking_id': str(tracking_id)
                    }
                }
            )
            return None
        
        tracking.user_response = response
        tracking.responded_at = datetime.utcnow()
        tracking.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(tracking)
        
        logger.info(
            "Recorded user response to suggestion",
            extra={
                'extra_fields': {
                    'event': 'suggestion_response_recorded',
                    'tracking_id': str(tracking_id),
                    'response': response
                }
            }
        )
        
        return tracking
