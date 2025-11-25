"""
Scheduler Service for intelligent check-in scheduling.

This service handles:
- Availability-aware scheduling
- Quiet hours enforcement
- Adaptive frequency based on user responsiveness
- Ghosting detection and response
- Timezone-aware calculations
"""

from datetime import datetime, timedelta, time
from typing import List, Optional, Tuple, Dict, Any
from zoneinfo import ZoneInfo

from app.models.user import User
from app.models.project import Project
from app.models.task import Task
from app.models.check_in import CheckIn
from app.models.availability_window import AvailabilityWindow
from app.core.timezone_utils import get_safe_timezone
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class SchedulerService:
    """Service for scheduling check-ins with user availability and preferences."""
    
    def calculate_check_in_time(
        self,
        task: Task,
        user: User,
        availability_windows: List[AvailabilityWindow]
    ) -> Optional[datetime]:
        """
        Calculate optimal check-in time for a task based on deadline and availability.
        
        Args:
            task: The task to schedule a check-in for
            user: The user who owns the task
            availability_windows: User's availability windows
            
        Returns:
            datetime: The scheduled check-in time in UTC
        """
        logger.info(
            "Calculating check-in time",
            extra={
                'extra_fields': {
                    'operation': 'calculate_check_in_time',
                    'task_id': str(task.id),
                    'user_id': str(user.id),
                    'due_date': task.due_date.isoformat() if task.due_date else None,
                    'availability_windows_count': len(availability_windows),
                }
            }
        )
        
        if not task.due_date:
            # If no due date, schedule for next available slot
            preferred_time = datetime.utcnow() + timedelta(hours=1)
        else:
            # Schedule check-in 1 day before due date as a default
            preferred_time = task.due_date - timedelta(days=1)
            
            # If that's in the past or too close to due date, schedule sooner
            now = datetime.utcnow()
            if preferred_time < now:
                # If we're past the 1-day-before mark, schedule ASAP but before due date
                time_until_due = (task.due_date - now).total_seconds() / 3600  # hours
                if time_until_due > 1:
                    # Schedule 1 hour from now if there's time
                    preferred_time = now + timedelta(hours=1)
                else:
                    # Very close to due date, schedule immediately
                    preferred_time = now
        
        # Find next available slot that respects availability windows
        next_slot = self.find_next_available_slot(user, preferred_time, availability_windows)
        
        # Handle case where no valid slot could be found
        if next_slot is None:
            logger.warning(
                "No available slot found for check-in",
                extra={
                    'extra_fields': {
                        'operation': 'calculate_check_in_time',
                        'task_id': str(task.id),
                        'user_id': str(user.id),
                        'preferred_time': preferred_time.isoformat(),
                    }
                }
            )
            # Return None to signal that scheduling is impossible with current constraints
            # Caller should handle this appropriately (skip message, notify user, etc.)
            return None
        
        # Ensure the slot is before the due date (if there is one)
        if task.due_date and next_slot >= task.due_date:
            logger.warning(
                "Next available slot is after due date",
                extra={
                    'extra_fields': {
                        'operation': 'calculate_check_in_time',
                        'task_id': str(task.id),
                        'next_slot': next_slot.isoformat(),
                        'due_date': task.due_date.isoformat(),
                    }
                }
            )
            # If the next available slot is after the due date, we cannot schedule
            # a check-in that meets all constraints
            return None
        
        logger.info(
            "Check-in time calculated",
            extra={
                'extra_fields': {
                    'operation': 'calculate_check_in_time',
                    'task_id': str(task.id),
                    'scheduled_time': next_slot.isoformat(),
                }
            }
        )
        
        return next_slot
    
    def find_next_available_slot(
        self,
        user: User,
        preferred_time: datetime,
        availability_windows: List[AvailabilityWindow]
    ) -> Optional[datetime]:
        """
        Find the next available time slot that respects user availability and quiet hours.
        
        Args:
            user: The user to schedule for
            preferred_time: The preferred time (in UTC)
            availability_windows: User's availability windows
            
        Returns:
            datetime: The next available time in UTC
        """
        # Convert preferred time to user's timezone
        # Use safe timezone to default to UTC if invalid (Requirements: 8.5)
        safe_tz = get_safe_timezone(user.timezone)
        user_tz = ZoneInfo(safe_tz)
        current_time = preferred_time.replace(tzinfo=ZoneInfo('UTC')).astimezone(user_tz)
        
        # If no availability windows defined, just check quiet hours
        if not availability_windows:
            # Keep checking forward until we find a time outside quiet hours
            max_attempts = 7 * 24  # Check up to 7 days ahead
            for _ in range(max_attempts):
                if not self.is_within_quiet_hours(user, current_time):
                    return current_time.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
                current_time += timedelta(hours=1)
            
            # If we can't find a slot within 7 days, the quiet hours configuration
            # is problematic (e.g., covers almost the entire day). Return None to
            # signal that no valid slot could be found.
            return None
        
        # Find next slot that matches availability windows and is outside quiet hours
        max_days_ahead = 14  # Look up to 2 weeks ahead
        
        for day_offset in range(max_days_ahead):
            check_date = current_time.date() + timedelta(days=day_offset)
            day_of_week = check_date.weekday()  # 0=Monday, 6=Sunday
            
            # Get availability windows for this day of week
            day_windows = [w for w in availability_windows if w.day_of_week == day_of_week]
            
            if not day_windows:
                continue
            
            # Check each availability window
            for window in day_windows:
                # Parse window times
                start_hour, start_minute = map(int, window.start_time.split(':'))
                end_hour, end_minute = map(int, window.end_time.split(':'))
                
                window_start = datetime.combine(check_date, time(start_hour, start_minute))
                window_start = window_start.replace(tzinfo=user_tz)
                window_end = datetime.combine(check_date, time(end_hour, end_minute))
                window_end = window_end.replace(tzinfo=user_tz)
                
                # If this is the first day and we're past the window start, adjust
                if day_offset == 0 and window_start < current_time:
                    # If we're also past the window end, skip this window
                    if current_time >= window_end:
                        continue
                    # Otherwise, start from current time
                    window_start = current_time
                
                # Try hourly slots within the window
                slot_time = window_start
                while slot_time < window_end:
                    if slot_time >= current_time and not self.is_within_quiet_hours(user, slot_time):
                        return slot_time.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
                    slot_time += timedelta(hours=1)
        
        # If no slot found within the search window, return None
        # This indicates that no valid slot could be found given the constraints
        return None
    
    def is_within_quiet_hours(
        self,
        user: User,
        check_time: datetime
    ) -> bool:
        """
        Check if a given time falls within user's quiet hours.
        
        Handles quiet hours that span midnight (e.g., 22:00 to 08:00).
        
        Args:
            user: The user with quiet hours settings
            check_time: The time to check (should be timezone-aware in user's timezone)
            
        Returns:
            bool: True if time is within quiet hours, False otherwise
        """
        if not user.quiet_hours_start or not user.quiet_hours_end:
            return False
        
        # Parse quiet hours
        start_hour, start_minute = map(int, user.quiet_hours_start.split(':'))
        end_hour, end_minute = map(int, user.quiet_hours_end.split(':'))
        
        quiet_start = time(start_hour, start_minute)
        quiet_end = time(end_hour, end_minute)
        
        # Get the time component from check_time
        check_time_only = check_time.time()
        
        # Handle quiet hours that span midnight
        if quiet_start > quiet_end:
            # Quiet hours span midnight (e.g., 22:00 to 08:00)
            # Time is in quiet hours if it's >= start OR <= end
            return check_time_only >= quiet_start or check_time_only <= quiet_end
        else:
            # Normal quiet hours (e.g., 01:00 to 06:00)
            # Time is in quiet hours if it's >= start AND <= end
            return quiet_start <= check_time_only <= quiet_end
    
    def should_adapt_frequency(
        self,
        user: User,
        project: Project,
        recent_check_ins: List[CheckIn]
    ) -> Tuple[bool, str]:
        """
        Determine if check-in frequency should be adapted based on user responsiveness.
        
        Analyzes the last 10 check-ins to calculate response rate and recommends
        frequency adjustments.
        
        Args:
            user: The user to analyze
            project: The project to analyze
            recent_check_ins: Recent check-ins (should be last 10 or fewer)
            
        Returns:
            Tuple of (should_adapt, reason) where:
                - should_adapt: "increase", "decrease", or "maintain"
                - reason: Explanation for the decision
        """
        if not recent_check_ins:
            return ("maintain", "No check-in history available")
        
        # Calculate response rate from recent check-ins
        total_check_ins = len(recent_check_ins)
        responded_check_ins = sum(
            1 for check_in in recent_check_ins 
            if check_in.status.value == "responded"
        )
        
        response_rate = responded_check_ins / total_check_ins if total_check_ins > 0 else 0
        
        # Apply thresholds from requirements
        # Requirement 3.4: Low responsiveness (< 30%) -> reduce frequency
        # Requirement 3.5: High responsiveness (> 70%) -> maintain or increase frequency
        
        if response_rate < 0.30:
            return (
                "decrease",
                f"Low response rate ({response_rate:.1%}). Reducing frequency to avoid overwhelming user."
            )
        elif response_rate > 0.70:
            return (
                "increase",
                f"High response rate ({response_rate:.1%}). User is engaged, maintaining or increasing frequency."
            )
        else:
            return (
                "maintain",
                f"Moderate response rate ({response_rate:.1%}). Maintaining current frequency."
            )
    
    def calculate_ghosting_response(
        self,
        user: User,
        project: Project,
        missed_count: int
    ) -> Dict[str, Any]:
        """
        Calculate appropriate response for user ghosting based on missed check-ins.
        
        Handles 2, 4, and 7 missed check-in thresholds as per requirements.
        
        Args:
            user: The user who has missed check-ins
            project: The project with missed check-ins
            missed_count: Number of consecutive missed check-ins
            
        Returns:
            Dict with response_type and message_template
        """
        if missed_count >= 7:
            # Requirement 9.3: 7 missed -> offer to archive
            return {
                "response_type": "archive_offer",
                "message_template": "empathetic_archive_offer",
                "ghosting_stage": 3,
                "action": "offer_archive"
            }
        elif missed_count >= 4:
            # Requirement 9.2: 4 missed -> ask about pausing or adjusting
            return {
                "response_type": "pause_inquiry",
                "message_template": "empathetic_pause_inquiry",
                "ghosting_stage": 2,
                "action": "ask_pause_or_adjust"
            }
        elif missed_count >= 2:
            # Requirement 9.1: 2 missed -> empathetic acknowledgment
            return {
                "response_type": "empathetic_acknowledgment",
                "message_template": "empathetic_difficulty_acknowledgment",
                "ghosting_stage": 1,
                "action": "acknowledge_difficulty"
            }
        else:
            # No ghosting response needed
            return {
                "response_type": "none",
                "message_template": None,
                "ghosting_stage": 0,
                "action": "continue_normal"
            }
