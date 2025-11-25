"""
Project Plan Service for managing project plans and milestones.

This service provides operations for retrieving, creating, updating,
and managing project plans and their associated milestones.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_

from app.models.project import Project
from app.models.milestone import Milestone, MilestoneStatus
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class ProjectPlanService:
    """
    Service for project plan operations.
    
    Handles retrieval, creation, and modification of project plans
    and milestones.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the project plan service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def get_all_projects(
        self,
        user_id: UUID
    ) -> List[Project]:
        """
        Get all projects for a user.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            List of Project objects
            
        Validates: Requirements 7.1
        """
        projects = (
            self.db.query(Project)
            .filter(Project.user_id == user_id)
            .order_by(Project.updated_at.desc())
            .all()
        )
        
        logger.info(
            "Retrieved all projects",
            extra={
                'extra_fields': {
                    'event': 'get_all_projects',
                    'user_id': str(user_id),
                    'project_count': len(projects)
                }
            }
        )
        
        return projects
    
    def find_project_by_name(
        self,
        user_id: UUID,
        project_name: str
    ) -> Optional[Project]:
        """
        Find a project by name (case-insensitive partial match).
        
        Args:
            user_id: UUID of the user
            project_name: Name or partial name of the project
            
        Returns:
            Project object if found, None otherwise
            
        Validates: Requirements 7.2
        """
        projects = self.get_all_projects(user_id)
        
        # Try exact match first (case-insensitive)
        for project in projects:
            if project.title.lower() == project_name.lower():
                return project
        
        # Try partial match
        for project in projects:
            if project_name.lower() in project.title.lower():
                return project
        
        return None
    
    async def get_project_plan(
        self,
        user_id: UUID,
        project_id: Optional[UUID] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the project plan for a user.
        
        If project_id is provided, returns that specific project.
        If project_id is None, returns the most recently active project.
        
        Args:
            user_id: UUID of the user
            project_id: Optional UUID of the specific project
            
        Returns:
            Dictionary containing project and milestones, or None if not found
            
        Validates: Requirements 1.1, 1.2, 1.3, 7.3
        """
        logger.info(
            "Retrieving project plan",
            extra={
                'extra_fields': {
                    'event': 'get_project_plan',
                    'user_id': str(user_id),
                    'project_id': str(project_id) if project_id else None
                }
            }
        )
        
        # Query for the project
        query = self.db.query(Project).filter(Project.user_id == user_id)
        
        if project_id:
            query = query.filter(Project.id == project_id)
        else:
            # Get most recently updated project (current/active project)
            query = query.order_by(Project.updated_at.desc())
        
        project = query.first()
        
        if not project:
            logger.warning(
                "No project found",
                extra={
                    'extra_fields': {
                        'event': 'project_not_found',
                        'user_id': str(user_id),
                        'project_id': str(project_id) if project_id else None
                    }
                }
            )
            return None
        
        # Get milestones for the project, ordered chronologically
        milestones = (
            self.db.query(Milestone)
            .filter(Milestone.project_id == project.id)
            .order_by(Milestone.target_date.asc())
            .all()
        )
        
        logger.info(
            "Project plan retrieved",
            extra={
                'extra_fields': {
                    'event': 'project_plan_retrieved',
                    'user_id': str(user_id),
                    'project_id': str(project.id),
                    'milestone_count': len(milestones)
                }
            }
        )
        
        return {
            'project': project,
            'milestones': milestones
        }
    
    async def add_milestone(
        self,
        project_id: UUID,
        title: str,
        target_date: datetime,
        description: Optional[str] = None,
        order: Optional[int] = None
    ) -> Milestone:
        """
        Add a new milestone to a project.
        
        Args:
            project_id: UUID of the project
            title: Title of the milestone
            target_date: Target date for the milestone
            description: Optional description
            order: Optional order in timeline (auto-calculated if not provided)
            
        Returns:
            The created Milestone
            
        Validates: Requirements 3.3
        """
        logger.info(
            "Adding milestone",
            extra={
                'extra_fields': {
                    'event': 'add_milestone',
                    'project_id': str(project_id),
                    'title': title,
                    'target_date': target_date.isoformat()
                }
            }
        )
        
        # If order not provided, calculate it
        if order is None:
            max_order = (
                self.db.query(Milestone.order)
                .filter(Milestone.project_id == project_id)
                .order_by(Milestone.order.desc())
                .first()
            )
            order = (max_order[0] + 1) if max_order else 0
        
        # Create the milestone
        milestone = Milestone(
            project_id=project_id,
            title=title,
            description=description,
            target_date=target_date,
            status=MilestoneStatus.PENDING,
            order=order
        )
        
        self.db.add(milestone)
        self.db.commit()
        self.db.refresh(milestone)
        
        logger.info(
            "Milestone added",
            extra={
                'extra_fields': {
                    'event': 'milestone_added',
                    'project_id': str(project_id),
                    'milestone_id': str(milestone.id),
                    'title': title
                }
            }
        )
        
        return milestone
    
    async def update_milestone(
        self,
        milestone_id: UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        target_date: Optional[datetime] = None,
        status: Optional[MilestoneStatus] = None
    ) -> Optional[Milestone]:
        """
        Update an existing milestone.
        
        Args:
            milestone_id: UUID of the milestone
            title: Optional new title
            description: Optional new description
            target_date: Optional new target date
            status: Optional new status
            
        Returns:
            The updated Milestone, or None if not found
            
        Validates: Requirements 3.2
        """
        logger.info(
            "Updating milestone",
            extra={
                'extra_fields': {
                    'event': 'update_milestone',
                    'milestone_id': str(milestone_id)
                }
            }
        )
        
        milestone = self.db.query(Milestone).filter(Milestone.id == milestone_id).first()
        
        if not milestone:
            logger.warning(
                "Milestone not found",
                extra={
                    'extra_fields': {
                        'event': 'milestone_not_found',
                        'milestone_id': str(milestone_id)
                    }
                }
            )
            return None
        
        # Capture before state for logging
        before_state = {
            'title': milestone.title,
            'description': milestone.description,
            'target_date': milestone.target_date.isoformat() if milestone.target_date else None,
            'status': milestone.status.value if milestone.status else None
        }
        
        # Update fields if provided
        if title is not None:
            milestone.title = title
        if description is not None:
            milestone.description = description
        if target_date is not None:
            milestone.target_date = target_date
        if status is not None:
            milestone.status = status
        
        milestone.updated_at = datetime.utcnow()
        
        # Capture after state for logging
        after_state = {
            'title': milestone.title,
            'description': milestone.description,
            'target_date': milestone.target_date.isoformat() if milestone.target_date else None,
            'status': milestone.status.value if milestone.status else None
        }
        
        self.db.commit()
        self.db.refresh(milestone)
        
        logger.info(
            "Milestone updated",
            extra={
                'extra_fields': {
                    'event': 'milestone_updated',
                    'milestone_id': str(milestone_id),
                    'before_state': before_state,
                    'after_state': after_state,
                    'changes': {
                        k: {'from': before_state[k], 'to': after_state[k]}
                        for k in before_state
                        if before_state[k] != after_state[k]
                    }
                }
            }
        )
        
        return milestone
    
    async def mark_milestone_complete(
        self,
        milestone_id: UUID
    ) -> Optional[Milestone]:
        """
        Mark a milestone as complete.
        
        Args:
            milestone_id: UUID of the milestone
            
        Returns:
            The updated Milestone, or None if not found
            
        Validates: Requirements 5.1, 5.2
        """
        logger.info(
            "Marking milestone complete",
            extra={
                'extra_fields': {
                    'event': 'mark_milestone_complete',
                    'milestone_id': str(milestone_id)
                }
            }
        )
        
        milestone = self.db.query(Milestone).filter(Milestone.id == milestone_id).first()
        
        if not milestone:
            logger.warning(
                "Milestone not found",
                extra={
                    'extra_fields': {
                        'event': 'milestone_not_found',
                        'milestone_id': str(milestone_id)
                    }
                }
            )
            return None
        
        # Mark as complete
        milestone.status = MilestoneStatus.COMPLETED
        milestone.completed_at = datetime.utcnow()
        milestone.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(milestone)
        
        logger.info(
            "Milestone marked complete",
            extra={
                'extra_fields': {
                    'event': 'milestone_completed',
                    'milestone_id': str(milestone_id),
                    'completed_at': milestone.completed_at.isoformat()
                }
            }
        )
        
        return milestone
