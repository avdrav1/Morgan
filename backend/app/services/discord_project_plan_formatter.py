"""
Discord Project Plan Formatter Service.

Formats project plan data for Discord display with proper markdown,
emojis, and message splitting to comply with Discord's limits.
"""

from typing import List, Optional
from datetime import datetime, timezone
from app.models.project import Project
from app.models.milestone import Milestone, MilestoneStatus


class DiscordProjectPlanFormatter:
    """
    Formats project plan data for Discord display.
    
    Handles Discord markdown formatting, emoji status indicators,
    relative date calculations, and message splitting for long content.
    
    Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5
    """
    
    # Discord's message character limit
    DISCORD_MAX_LENGTH = 2000
    
    # Status emojis
    STATUS_EMOJIS = {
        MilestoneStatus.PENDING: "⏳",
        MilestoneStatus.IN_PROGRESS: "🔄",
        MilestoneStatus.COMPLETED: "✅"
    }
    
    def format_project_plan(
        self,
        project: Project,
        milestones: List[Milestone],
        include_completed: bool = False
    ) -> List[str]:
        """
        Format a project plan for Discord display.
        
        Returns a list of message strings (may be multiple if content is long).
        
        Args:
            project: The project to format
            milestones: List of milestones for the project
            include_completed: Whether to include completed milestones
            
        Returns:
            List of formatted message strings, each under Discord's limit
            
        Validates: Requirements 8.1, 8.2, 8.5
        """
        # Filter milestones if needed
        if not include_completed:
            milestones = [m for m in milestones if m.status != MilestoneStatus.COMPLETED]
        
        # Sort milestones chronologically by target date
        milestones = sorted(milestones, key=lambda m: m.target_date)
        
        # Build the header
        header = self._format_project_header(project)
        
        # Build milestone list
        milestone_lines = []
        for i, milestone in enumerate(milestones, 1):
            milestone_lines.append(self.format_milestone(milestone, number=i))
        
        # Combine into full message
        if milestone_lines:
            milestones_section = "\n\n**Milestones:**\n" + "\n".join(milestone_lines)
        else:
            milestones_section = "\n\n*No upcoming milestones.*"
        
        full_message = header + milestones_section
        
        # Split if necessary
        return self._split_message(full_message)
    
    def format_milestone(
        self,
        milestone: Milestone,
        include_status_emoji: bool = True,
        number: Optional[int] = None
    ) -> str:
        """
        Format a single milestone for display.
        
        Args:
            milestone: The milestone to format
            include_status_emoji: Whether to include status emoji
            number: Optional number prefix for the milestone
            
        Returns:
            Formatted milestone string
            
        Validates: Requirements 8.1, 8.3, 8.4
        """
        # Get status emoji
        emoji = ""
        if include_status_emoji:
            emoji = self.STATUS_EMOJIS.get(milestone.status, "")
        
        # Format the date with relative time
        date_str = self._format_date_with_relative(milestone.target_date)
        
        # Build the milestone line
        prefix = f"{number}. " if number else ""
        title = f"**{milestone.title}**"
        
        line = f"{prefix}{emoji} {title} - `{date_str}`"
        
        # Add description if present
        if milestone.description:
            line += f"\n   _{milestone.description}_"
        
        return line
    
    def format_timeline_summary(
        self,
        project: Project,
        milestones: List[Milestone]
    ) -> str:
        """
        Format a summary of the project timeline.
        
        Args:
            project: The project
            milestones: List of milestones
            
        Returns:
            Formatted timeline summary string
            
        Validates: Requirements 8.1, 8.3
        """
        # Count milestones by status
        pending = sum(1 for m in milestones if m.status == MilestoneStatus.PENDING)
        in_progress = sum(1 for m in milestones if m.status == MilestoneStatus.IN_PROGRESS)
        completed = sum(1 for m in milestones if m.status == MilestoneStatus.COMPLETED)
        
        # Calculate progress percentage
        total = len(milestones)
        progress_pct = (completed / total * 100) if total > 0 else 0
        
        # Format deadline
        deadline_str = "Not set"
        if project.target_completion_date:
            deadline_str = self._format_date_with_relative(project.target_completion_date)
        
        summary = f"**Timeline Summary**\n"
        summary += f"Progress: {completed}/{total} milestones ({progress_pct:.0f}%)\n"
        summary += f"Deadline: `{deadline_str}`\n"
        summary += f"Status: {completed} ✅ | {in_progress} 🔄 | {pending} ⏳"
        
        return summary
    
    def _format_project_header(self, project: Project) -> str:
        """
        Format the project header section.
        
        Args:
            project: The project
            
        Returns:
            Formatted header string
        """
        header = f"**{project.title}**\n"
        header += f"_{project.goal}_\n"
        
        if project.target_completion_date:
            deadline_str = self._format_date_with_relative(project.target_completion_date)
            header += f"\nDeadline: `{deadline_str}`"
        
        return header
    
    def _format_date_with_relative(self, target_date: datetime) -> str:
        """
        Format a date with both absolute and relative time.
        
        Args:
            target_date: The target date
            
        Returns:
            Formatted date string like "Dec 25, 2024 (in 3 days)"
            
        Validates: Requirements 8.3
        """
        # Get current time in UTC
        now = datetime.now(timezone.utc)
        
        # Ensure target_date is timezone-aware
        if target_date.tzinfo is None:
            target_date = target_date.replace(tzinfo=timezone.utc)
        
        # Calculate difference
        delta = target_date - now
        days = delta.days
        
        # Format absolute date
        absolute = target_date.strftime("%b %d, %Y")
        
        # Format relative time
        if days < 0:
            relative = f"{abs(days)} days ago"
        elif days == 0:
            relative = "today"
        elif days == 1:
            relative = "tomorrow"
        else:
            relative = f"in {days} days"
        
        return f"{absolute} ({relative})"
    
    def _split_message(self, message: str) -> List[str]:
        """
        Split a message into multiple parts if it exceeds Discord's limit.
        
        Attempts to split at natural boundaries (double newlines).
        
        Args:
            message: The message to split
            
        Returns:
            List of message parts, each under the character limit
            
        Validates: Requirements 8.2, 8.5
        """
        # If message fits, return as-is
        if len(message) <= self.DISCORD_MAX_LENGTH:
            return [message]
        
        # Split into parts
        parts = []
        current_part = ""
        
        # Split by double newlines (paragraph boundaries)
        paragraphs = message.split("\n\n")
        
        for paragraph in paragraphs:
            # If adding this paragraph would exceed limit, save current part
            if current_part and len(current_part) + len(paragraph) + 2 > self.DISCORD_MAX_LENGTH:
                parts.append(current_part.strip())
                current_part = ""
            
            # If a single paragraph is too long, split it by single newlines
            if len(paragraph) > self.DISCORD_MAX_LENGTH:
                lines = paragraph.split("\n")
                for line in lines:
                    if current_part and len(current_part) + len(line) + 1 > self.DISCORD_MAX_LENGTH:
                        parts.append(current_part.strip())
                        current_part = ""
                    
                    # If a single line is still too long, truncate it
                    if len(line) > self.DISCORD_MAX_LENGTH:
                        if current_part:
                            parts.append(current_part.strip())
                            current_part = ""
                        parts.append(line[:self.DISCORD_MAX_LENGTH - 20] + "... (truncated)")
                    else:
                        current_part += line + "\n"
            else:
                current_part += paragraph + "\n\n"
        
        # Add remaining content
        if current_part.strip():
            parts.append(current_part.strip())
        
        return parts if parts else [message[:self.DISCORD_MAX_LENGTH]]
