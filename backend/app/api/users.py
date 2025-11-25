from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.timezone_utils import validate_timezone, get_safe_timezone
from app.models import User
from app.models.availability_window import AvailabilityWindow
from app.models.project import Project
from app.models.task import Task
from app.models.check_in import CheckIn
from app.models.rescheduling_history import ReschedulingHistory
from app.schemas.user import (
    UserResponse,
    UserUpdate,
    QuietHoursUpdate,
    ToneUpdate,
    SystemPromptUpdate
)
from app.schemas.availability import (
    AvailabilityWindowResponse,
    AvailabilityWindowsUpdate
)

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user profile.
    
    Validates timezone against IANA database (Requirements: 8.5).
    """
    
    update_data = user_update.model_dump(exclude_unset=True)
    
    # Validate timezone if provided
    if "timezone" in update_data:
        timezone_str = update_data["timezone"]
        is_valid, error_msg = validate_timezone(timezone_str)
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_timezone",
                    "message": error_msg,
                    "field": "timezone"
                }
            )
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.delete("/me/data", response_model=UserResponse)
async def schedule_data_deletion(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Schedule deletion of user data within 30 days."""
    
    # Schedule deletion 30 days from now
    deletion_date = datetime.utcnow() + timedelta(days=30)
    current_user.deletion_scheduled_at = deletion_date
    
    # Pause messaging immediately
    current_user.messaging_paused = True
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.get("/me/export")
async def export_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export all user data in portable JSON format."""
    
    # Get all projects with their tasks and check-ins
    projects = db.query(Project).filter(Project.user_id == current_user.id).all()
    
    export_data = {
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "preferred_tone": current_user.preferred_tone,
            "custom_system_prompt": current_user.custom_system_prompt,
            "timezone": current_user.timezone,
            "quiet_hours_start": current_user.quiet_hours_start,
            "quiet_hours_end": current_user.quiet_hours_end,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        },
        "availability_windows": [
            {
                "day_of_week": window.day_of_week,
                "start_time": window.start_time,
                "end_time": window.end_time,
            }
            for window in current_user.availability_windows
        ],
        "projects": []
    }
    
    # Export each project with its tasks and check-ins
    for project in projects:
        project_data = {
            "id": str(project.id),
            "title": project.title,
            "description": project.description,
            "goal": project.goal,
            "success_criteria": project.success_criteria,
            "status": project.status.value if project.status else None,
            "estimated_duration_weeks": project.estimated_duration_weeks,
            "target_completion_date": project.target_completion_date.isoformat() if project.target_completion_date else None,
            "actual_completion_date": project.actual_completion_date.isoformat() if project.actual_completion_date else None,
            "project_tone": project.project_tone,
            "project_context": project.project_context,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "tasks": [],
            "check_ins": []
        }
        
        # Export tasks
        for task in project.tasks:
            task_data = {
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "order": task.order,
                "estimated_duration_hours": task.estimated_duration_hours,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "original_due_date": task.original_due_date.isoformat() if task.original_due_date else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "status": task.status.value if task.status else None,
                "blocker_type": task.blocker_type,
                "blocker_description": task.blocker_description,
                "blocker_diagnosed_at": task.blocker_diagnosed_at.isoformat() if task.blocker_diagnosed_at else None,
                "reschedule_count": task.reschedule_count,
                "created_at": task.created_at.isoformat() if task.created_at else None,
            }
            
            # Get rescheduling history for this task
            rescheduling_history = db.query(ReschedulingHistory).filter(
                ReschedulingHistory.task_id == task.id
            ).all()
            
            task_data["rescheduling_history"] = [
                {
                    "old_due_date": history.old_due_date.isoformat() if history.old_due_date else None,
                    "new_due_date": history.new_due_date.isoformat() if history.new_due_date else None,
                    "reason": history.reason,
                    "blocker_type": history.blocker_type,
                    "initiated_by": history.initiated_by,
                    "created_at": history.created_at.isoformat() if history.created_at else None,
                }
                for history in rescheduling_history
            ]
            
            project_data["tasks"].append(task_data)
        
        # Export check-ins (conversation history)
        for check_in in project.check_ins:
            check_in_data = {
                "id": str(check_in.id),
                "task_id": str(check_in.task_id) if check_in.task_id else None,
                "check_in_type": check_in.check_in_type.value if check_in.check_in_type else None,
                "status": check_in.status.value if check_in.status else None,
                "scheduled_for": check_in.scheduled_for.isoformat() if check_in.scheduled_for else None,
                "sent_at": check_in.sent_at.isoformat() if check_in.sent_at else None,
                "responded_at": check_in.responded_at.isoformat() if check_in.responded_at else None,
                "message_sent": check_in.message_sent,
                "user_response": check_in.user_response,
                "assistant_reply": check_in.assistant_reply,
                "conversation_context": check_in.conversation_context,
                "blocker_detected": check_in.blocker_detected,
                "reschedule_initiated": check_in.reschedule_initiated,
                "response_time_minutes": check_in.response_time_minutes,
                "sentiment": check_in.sentiment,
                "platform": check_in.platform,
                "created_at": check_in.created_at.isoformat() if check_in.created_at else None,
            }
            project_data["check_ins"].append(check_in_data)
        
        export_data["projects"].append(project_data)
    
    return export_data


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete current user account and all associated data."""
    
    db.delete(current_user)
    db.commit()
    
    return None


@router.get("/me/availability", response_model=List[AvailabilityWindowResponse])
async def get_availability_windows(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's availability windows."""
    return current_user.availability_windows


@router.put("/me/availability", response_model=List[AvailabilityWindowResponse])
async def update_availability_windows(
    availability_update: AvailabilityWindowsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's availability windows. Replaces all existing windows."""
    
    # Delete existing availability windows
    db.query(AvailabilityWindow).filter(
        AvailabilityWindow.user_id == current_user.id
    ).delete()
    
    # Create new availability windows
    new_windows = []
    for window_data in availability_update.windows:
        window = AvailabilityWindow(
            user_id=current_user.id,
            day_of_week=window_data.day_of_week,
            start_time=window_data.start_time,
            end_time=window_data.end_time
        )
        db.add(window)
        new_windows.append(window)
    
    db.commit()
    
    # Refresh all windows to get their IDs and timestamps
    for window in new_windows:
        db.refresh(window)
    
    return new_windows


@router.put("/me/quiet-hours", response_model=UserResponse)
async def update_quiet_hours(
    quiet_hours: QuietHoursUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's quiet hours."""
    
    if quiet_hours.quiet_hours_start is not None:
        current_user.quiet_hours_start = quiet_hours.quiet_hours_start
    
    if quiet_hours.quiet_hours_end is not None:
        current_user.quiet_hours_end = quiet_hours.quiet_hours_end
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.put("/me/tone", response_model=UserResponse)
async def update_tone(
    tone_update: ToneUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's preferred tone."""
    
    current_user.preferred_tone = tone_update.preferred_tone
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.put("/me/system-prompt", response_model=UserResponse)
async def update_system_prompt(
    prompt_update: SystemPromptUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's custom system prompt."""
    
    current_user.custom_system_prompt = prompt_update.custom_system_prompt
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.post("/me/pause-messaging", response_model=UserResponse)
async def pause_messaging(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Pause proactive messaging for the current user."""
    
    current_user.messaging_paused = True
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.post("/me/resume-messaging", response_model=UserResponse)
async def resume_messaging(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resume proactive messaging for the current user."""
    
    current_user.messaging_paused = False
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.get("/timezones/common")
async def get_common_timezones():
    """Get a list of common timezones for user selection."""
    from app.core.timezone_utils import get_common_timezones
    return {"timezones": get_common_timezones()}


@router.get("/timezones/all")
async def get_all_timezones():
    """Get all available IANA timezones."""
    from app.core.timezone_utils import get_all_timezones
    return {"timezones": get_all_timezones()}


@router.get("/by-discord/{discord_user_id}")
async def get_user_by_discord_id(
    discord_user_id: str,
    db: Session = Depends(get_db)
):
    """
    Get user by Discord ID.
    
    Args:
        discord_user_id: Discord user ID
        db: Database session
        
    Returns:
        User information
        
    Raises:
        HTTPException: If user not found
    """
    user = db.query(User).filter(User.discord_user_id == discord_user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "discord_user_id": user.discord_user_id,
        "timezone": user.timezone
    }
