"""
Milestone Generator Service for creating initial project milestones.

This service generates milestones for a project based on its goal and deadline,
distributing them evenly across the timeline and using LLM to generate titles.
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.milestone import Milestone, MilestoneStatus
from app.services.llm_service import LLMService
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class MilestoneGenerator:
    """
    Service for generating initial project milestones.
    
    Generates 3-5 milestones based on project duration, distributes them
    evenly across the timeline, and uses LLM to generate meaningful titles.
    
    Validates: Requirements 1.4
    """
    
    def __init__(self, db: Session, llm_service: LLMService):
        """
        Initialize the milestone generator.
        
        Args:
            db: Database session
            llm_service: LLM service for generating milestone titles
        """
        self.db = db
        self.llm_service = llm_service
    
    def calculate_milestone_count(self, project: Project) -> int:
        """
        Calculate the number of milestones based on project duration.
        
        Rules:
        - Projects < 2 weeks: 3 milestones
        - Projects 2-6 weeks: 4 milestones
        - Projects > 6 weeks: 5 milestones
        
        Args:
            project: The project to calculate milestones for
            
        Returns:
            Number of milestones to create (3-5)
        """
        if not project.target_completion_date:
            # Default to 4 milestones if no deadline set
            return 4
        
        # Calculate weeks until deadline
        now = datetime.utcnow()
        time_until_deadline = project.target_completion_date - now
        weeks = time_until_deadline.days / 7
        
        if weeks < 2:
            return 3
        elif weeks <= 6:
            return 4
        else:
            return 5
    
    def distribute_milestones(
        self,
        project: Project,
        milestone_count: int
    ) -> List[datetime]:
        """
        Distribute milestones evenly across the project timeline.
        
        The first milestone is placed 1-2 weeks out to create immediate action.
        Remaining milestones are distributed evenly until the deadline.
        
        Args:
            project: The project to distribute milestones for
            milestone_count: Number of milestones to create
            
        Returns:
            List of target dates for milestones
        """
        if not project.target_completion_date:
            # If no deadline, space milestones 2 weeks apart
            now = datetime.utcnow()
            return [
                now + timedelta(weeks=2 * (i + 1))
                for i in range(milestone_count)
            ]
        
        now = datetime.utcnow()
        deadline = project.target_completion_date
        
        # Calculate total duration
        total_duration = deadline - now
        
        # First milestone: 1-2 weeks out (or 1/4 of duration if shorter)
        first_milestone_offset = min(
            timedelta(weeks=1.5),
            total_duration / 4
        )
        
        # Distribute remaining milestones evenly
        milestone_dates = []
        
        # First milestone
        milestone_dates.append(now + first_milestone_offset)
        
        # Remaining milestones distributed evenly from first to deadline
        if milestone_count > 1:
            remaining_duration = deadline - milestone_dates[0]
            interval = remaining_duration / (milestone_count - 1)
            
            for i in range(1, milestone_count):
                milestone_dates.append(milestone_dates[0] + (interval * i))
        
        # Round dates to end of day for clarity
        milestone_dates = [
            date.replace(hour=23, minute=59, second=59, microsecond=0)
            for date in milestone_dates
        ]
        
        return milestone_dates
    
    async def generate_milestone_titles(
        self,
        project: Project,
        milestone_count: int
    ) -> List[str]:
        """
        Use LLM to generate milestone titles based on project goal.
        
        Args:
            project: The project to generate titles for
            milestone_count: Number of milestone titles to generate
            
        Returns:
            List of milestone titles
        """
        logger.info(
            "Generating milestone titles",
            extra={
                'extra_fields': {
                    'event': 'generate_milestone_titles',
                    'project_id': str(project.id),
                    'milestone_count': milestone_count
                }
            }
        )
        
        # Build project context
        project_context_section = ""
        if project.project_context:
            project_context_section = f"\nProject-specific context: {project.project_context}\n"
        
        prompt = f"""Generate {milestone_count} milestone titles for this project.

Project: {project.title}
Goal: {project.goal}
Description: {project.description}
{f"Success criteria: {project.success_criteria}" if project.success_criteria else ""}{project_context_section}

Create {milestone_count} milestone titles that:
1. Break down the project into logical phases
2. Are action-oriented and specific
3. Progress from early setup/planning to final completion
4. Are concise (3-8 words each)
5. Represent significant checkpoints in the project

Return the titles as a JSON array:
["Milestone 1 title", "Milestone 2 title", ...]

Return ONLY the JSON array, no other text."""

        try:
            # Log LLM request (PII-redacted)
            logger.info(
                "Calling LLM for milestone title generation",
                extra={
                    'extra_fields': {
                        'event': 'llm_milestone_generation_request',
                        'project_id': str(project.id),
                        'milestone_count': milestone_count,
                        'prompt_length': len(prompt)
                    }
                }
            )
            
            response = await self.llm_service.client.messages.create(
                model=self.llm_service.model,
                max_tokens=500,
                system="You are a project planning assistant helping break down projects into milestones.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Log LLM response (PII-redacted)
            response_text = response.content[0].text.strip()
            logger.info(
                "LLM milestone generation response received",
                extra={
                    'extra_fields': {
                        'event': 'llm_milestone_generation_response',
                        'project_id': str(project.id),
                        'response_length': len(response_text)
                    }
                }
            )
            
            # Parse the JSON response
            import json
            titles_json = response_text
            
            # Remove markdown code blocks if present
            if titles_json.startswith("```"):
                titles_json = titles_json.split("\n", 1)[1]
                titles_json = titles_json.rsplit("\n", 1)[0]
            
            titles = json.loads(titles_json)
            
            logger.info(
                "Milestone titles generated",
                extra={
                    'extra_fields': {
                        'event': 'milestone_titles_generated',
                        'project_id': str(project.id),
                        'titles_count': len(titles),
                        'titles': titles  # Log the actual titles for debugging
                    }
                }
            )
            
            return titles
            
        except Exception as e:
            logger.error(
                "Failed to generate milestone titles with LLM",
                extra={
                    'extra_fields': {
                        'event': 'milestone_title_generation_failed',
                        'project_id': str(project.id),
                        'error': str(e),
                        'error_type': type(e).__name__
                    }
                },
                exc_info=True
            )
            
            # Fallback to generic titles
            return [
                f"Milestone {i + 1}" for i in range(milestone_count)
            ]
    
    async def generate_milestones(
        self,
        project: Project
    ) -> List[Milestone]:
        """
        Generate initial milestones for a project.
        
        This is the main entry point that orchestrates:
        1. Calculating milestone count
        2. Distributing milestone dates
        3. Generating milestone titles
        4. Creating milestone records
        
        Args:
            project: The project to generate milestones for
            
        Returns:
            List of created Milestone objects
            
        Validates: Requirements 1.4
        """
        logger.info(
            "Generating milestones for project",
            extra={
                'extra_fields': {
                    'event': 'generate_milestones_start',
                    'project_id': str(project.id),
                    'project_title': project.title
                }
            }
        )
        
        # Step 1: Calculate milestone count
        milestone_count = self.calculate_milestone_count(project)
        
        # Step 2: Distribute milestone dates
        milestone_dates = self.distribute_milestones(project, milestone_count)
        
        # Step 3: Generate milestone titles
        milestone_titles = await self.generate_milestone_titles(project, milestone_count)
        
        # Ensure we have the right number of titles
        if len(milestone_titles) != milestone_count:
            logger.warning(
                "Milestone title count mismatch",
                extra={
                    'extra_fields': {
                        'event': 'milestone_title_count_mismatch',
                        'expected': milestone_count,
                        'received': len(milestone_titles)
                    }
                }
            )
            # Pad or truncate as needed
            if len(milestone_titles) < milestone_count:
                milestone_titles.extend([
                    f"Milestone {i + 1}"
                    for i in range(len(milestone_titles), milestone_count)
                ])
            else:
                milestone_titles = milestone_titles[:milestone_count]
        
        # Step 4: Create milestone records
        milestones = []
        for i, (title, target_date) in enumerate(zip(milestone_titles, milestone_dates)):
            milestone = Milestone(
                project_id=project.id,
                title=title,
                target_date=target_date,
                status=MilestoneStatus.PENDING,
                order=i
            )
            self.db.add(milestone)
            milestones.append(milestone)
        
        self.db.commit()
        
        # Refresh to get IDs
        for milestone in milestones:
            self.db.refresh(milestone)
        
        logger.info(
            "Milestones generated successfully",
            extra={
                'extra_fields': {
                    'event': 'generate_milestones_complete',
                    'project_id': str(project.id),
                    'milestone_count': len(milestones)
                }
            }
        )
        
        return milestones
