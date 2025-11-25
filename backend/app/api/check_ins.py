from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.metrics import track_check_in_responded, track_task_rescheduled
from app.models import User, CheckIn, Task, Project
from app.models.check_in import CheckInStatus
from app.models.rescheduling_history import ReschedulingHistory
from app.services.conversation_manager import ConversationManager
from app.services.llm_service import llm_service
from pydantic import BaseModel, Field

router = APIRouter()


# Schemas
class CheckInResponseRequest(BaseModel):
    """Request body for responding to a check-in."""
    response: str = Field(..., min_length=1, description="User's response to the check-in")


class CheckInResponse(BaseModel):
    """Response from the check-in response endpoint."""
    id: UUID
    status: str
    user_response: str
    assistant_reply: str
    blocker_detected: bool
    reschedule_initiated: bool
    
    class Config:
        from_attributes = True


class RescheduleRequest(BaseModel):
    """Request body for initiating rescheduling."""
    reason: str = Field(..., min_length=1, description="Reason for rescheduling")
    proposed_date: datetime | None = Field(None, description="User's proposed new date (optional)")


class RescheduleResponse(BaseModel):
    """Response from the rescheduling endpoint."""
    id: UUID
    task_id: UUID
    proposed_date: datetime
    reasoning: str
    requires_confirmation: bool = True
    
    class Config:
        from_attributes = True


class RescheduleConfirmRequest(BaseModel):
    """Request body for confirming a reschedule."""
    confirmed: bool = Field(..., description="Whether user confirms the reschedule")
    final_date: datetime | None = Field(None, description="User's final date if different from proposal")


class CheckInHistoryResponse(BaseModel):
    """Response for check-in history."""
    id: UUID
    check_in_type: str
    status: str
    scheduled_for: datetime
    sent_at: datetime | None
    responded_at: datetime | None
    message_sent: str | None
    user_response: str | None
    assistant_reply: str | None
    conversation_context: list | None
    blocker_detected: bool
    reschedule_initiated: bool
    
    class Config:
        from_attributes = True


@router.post("/{check_in_id}/respond", response_model=CheckInResponse)
async def respond_to_check_in(
    check_in_id: UUID,
    response_data: CheckInResponseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Process user response to a check-in.
    
    This endpoint:
    1. Retrieves the check-in and validates ownership
    2. Stores the user's response
    3. Processes the response through ConversationManager
    4. Generates a coaching response via LLM
    5. Detects blockers and reschedule intents
    
    Requirements: 4.1, 4.2
    """
    # Get the check-in and verify ownership
    check_in = db.query(CheckIn).join(Project).filter(
        CheckIn.id == check_in_id,
        Project.user_id == current_user.id
    ).first()
    
    if not check_in:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check-in not found"
        )
    
    # Get the associated task and project
    task = check_in.task
    project = check_in.project
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in must be associated with a task"
        )
    
    # Initialize conversation manager
    conv_manager = ConversationManager(db)
    
    # Store the user's response
    conv_manager.store_conversation_turn(
        check_in=check_in,
        role="user",
        content=response_data.response
    )
    
    # Update check-in status and timing
    check_in.status = CheckInStatus.RESPONDED
    check_in.responded_at = datetime.utcnow()
    
    # Calculate response time if check-in was sent
    response_time_minutes = None
    if check_in.sent_at:
        response_time = (check_in.responded_at - check_in.sent_at).total_seconds() / 60
        check_in.response_time_minutes = int(response_time)
        response_time_minutes = check_in.response_time_minutes
    
    # Track metrics: check-in responded
    track_check_in_responded(
        user_id=str(current_user.id),
        project_id=str(project.id),
        response_time_minutes=response_time_minutes
    )
    
    # Get conversation history
    conversation_history = conv_manager.get_conversation_context(check_in)
    
    # Detect minimal response (10 or fewer characters)
    # Requirements: 12.1, 12.2
    is_minimal_response = len(response_data.response.strip()) <= 10
    
    # Detect blocker patterns (skip for minimal responses)
    blocker_type = None
    if not is_minimal_response:
        blocker_type = conv_manager.detect_blocker_pattern(task, conversation_history)
        if blocker_type:
            check_in.blocker_detected = True
            task.blocker_type = blocker_type
            task.blocker_diagnosed_at = datetime.utcnow()
    
    # Detect reschedule intent (skip for minimal responses)
    reschedule_intent = False
    if not is_minimal_response:
        reschedule_intent = conv_manager.extract_reschedule_intent(response_data.response)
        if reschedule_intent:
            check_in.reschedule_initiated = True
    
    # Generate coaching response via LLM
    coaching_response = await llm_service.generate_coaching_response(
        user=current_user,
        project=project,
        task=task,
        user_response=response_data.response,
        conversation_history=conversation_history,
        is_minimal_response=is_minimal_response
    )
    
    # Store the assistant's reply
    conv_manager.store_conversation_turn(
        check_in=check_in,
        role="assistant",
        content=coaching_response
    )
    
    db.commit()
    db.refresh(check_in)
    
    return CheckInResponse(
        id=check_in.id,
        status=check_in.status.value,
        user_response=response_data.response,
        assistant_reply=coaching_response,
        blocker_detected=check_in.blocker_detected,
        reschedule_initiated=check_in.reschedule_initiated
    )



@router.post("/{check_in_id}/reschedule", response_model=RescheduleResponse)
async def initiate_reschedule(
    check_in_id: UUID,
    reschedule_data: RescheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initiate conversational rescheduling flow.
    
    This endpoint:
    1. Validates the check-in and task
    2. Analyzes the reason for rescheduling
    3. Proposes a new deadline via LLM
    4. Returns the proposal for user confirmation
    5. Does NOT automatically update the timeline
    
    Requirements: 5.1, 5.2, 5.3, 5.4
    """
    # Get the check-in and verify ownership
    check_in = db.query(CheckIn).join(Project).filter(
        CheckIn.id == check_in_id,
        Project.user_id == current_user.id
    ).first()
    
    if not check_in:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check-in not found"
        )
    
    # Get the associated task
    task = check_in.task
    if not task:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in must be associated with a task"
        )
    
    # Mark reschedule as initiated
    check_in.reschedule_initiated = True
    
    # Initialize conversation manager
    conv_manager = ConversationManager(db)
    
    # Store the reschedule request in conversation
    conv_manager.store_conversation_turn(
        check_in=check_in,
        role="user",
        content=f"I need to reschedule. Reason: {reschedule_data.reason}"
    )
    
    # Get conversation history
    conversation_history = conv_manager.get_conversation_context(check_in)
    
    # Detect or use existing blocker information
    blocker_type = task.blocker_type or conv_manager.detect_blocker_pattern(task, conversation_history)
    
    blocker_info = {
        "blocker_type": blocker_type,
        "reason": reschedule_data.reason
    }
    
    # If blocker not already diagnosed, diagnose it
    if not task.blocker_type and blocker_type:
        task.blocker_type = blocker_type
        task.blocker_description = reschedule_data.reason
        task.blocker_diagnosed_at = datetime.utcnow()
    
    # Use LLM to propose a new deadline
    proposal = await llm_service.propose_reschedule(
        user=current_user,
        task=task,
        blocker_info=blocker_info,
        conversation_history=conversation_history
    )
    
    # Store the proposal in conversation
    proposal_message = f"Based on your situation, I propose moving the deadline to {proposal['proposed_date']}. {proposal['reasoning']}"
    conv_manager.store_conversation_turn(
        check_in=check_in,
        role="assistant",
        content=proposal_message
    )
    
    db.commit()
    
    # Parse the proposed date
    from dateutil import parser as date_parser
    proposed_datetime = date_parser.parse(proposal['proposed_date'])
    
    return RescheduleResponse(
        id=check_in.id,
        task_id=task.id,
        proposed_date=proposed_datetime,
        reasoning=proposal['reasoning'],
        requires_confirmation=True
    )


@router.post("/{check_in_id}/reschedule/confirm")
async def confirm_reschedule(
    check_in_id: UUID,
    confirm_data: RescheduleConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Confirm and apply a rescheduling proposal.
    
    This endpoint requires explicit user confirmation before updating the timeline.
    It also creates a ReschedulingHistory record to track the change.
    Uses optimistic locking to prevent concurrent rescheduling conflicts.
    
    Requirements: 5.4, 5.5
    """
    # Get the check-in and verify ownership
    check_in = db.query(CheckIn).join(Project).filter(
        CheckIn.id == check_in_id,
        Project.user_id == current_user.id
    ).first()
    
    if not check_in:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check-in not found"
        )
    
    # Get the associated task with FOR UPDATE lock to prevent concurrent modifications
    # This provides database-level locking for concurrent rescheduling protection
    # Requirements: 5.4
    task = db.query(Task).filter(Task.id == check_in.task_id).with_for_update().first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in must be associated with a task"
        )
    
    if not confirm_data.confirmed:
        # User rejected the reschedule
        conv_manager = ConversationManager(db)
        conv_manager.store_conversation_turn(
            check_in=check_in,
            role="user",
            content="I don't want to reschedule to that date."
        )
        db.commit()
        
        return {
            "message": "Reschedule cancelled",
            "task_id": task.id,
            "due_date": task.due_date
        }
    
    # User confirmed - apply the reschedule
    old_due_date = task.due_date
    new_due_date = confirm_data.final_date or old_due_date
    
    if not new_due_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New due date must be provided"
        )
    
    # Store the current version for optimistic locking check
    current_version = task.version
    
    # Create rescheduling history record
    history = ReschedulingHistory(
        task_id=task.id,
        old_due_date=old_due_date,
        new_due_date=new_due_date,
        reason=task.blocker_description or "User requested reschedule",
        blocker_type=task.blocker_type,
        initiated_by="user"
    )
    db.add(history)
    
    # Update the task with optimistic locking
    # Increment version to detect concurrent modifications
    task.due_date = new_due_date
    task.reschedule_count += 1
    task.version = current_version + 1
    
    # Store confirmation in conversation
    conv_manager = ConversationManager(db)
    conv_manager.store_conversation_turn(
        check_in=check_in,
        role="user",
        content=f"Confirmed. New deadline: {new_due_date.isoformat()}"
    )
    
    try:
        db.commit()
        db.refresh(task)
        
        # Track metrics: task rescheduled
        track_task_rescheduled(
            user_id=str(current_user.id),
            project_id=str(task.project_id),
            task_id=str(task.id),
            blocker_type=task.blocker_type
        )
    except Exception as e:
        db.rollback()
        # Check if this was a concurrent modification conflict
        if "version" in str(e).lower() or "concurrent" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task was modified by another request. Please refresh and try again."
            )
        raise
    
    return {
        "message": "Task rescheduled successfully",
        "task_id": task.id,
        "old_due_date": old_due_date,
        "new_due_date": new_due_date,
        "reschedule_count": task.reschedule_count
    }


@router.get("/tasks/{task_id}/check-ins", response_model=List[CheckInHistoryResponse])
async def get_task_check_ins(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all check-ins for a task with conversation history.
    
    Returns the complete check-in history for a task, including all
    conversation turns and metadata.
    
    Requirements: 4.1, 5.1
    """
    # Verify task ownership
    task = db.query(Task).join(Project).filter(
        Task.id == task_id,
        Project.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Get all check-ins for this task, ordered by scheduled time
    check_ins = db.query(CheckIn).filter(
        CheckIn.task_id == task_id
    ).order_by(CheckIn.scheduled_for.desc()).all()
    
    return [
        CheckInHistoryResponse(
            id=ci.id,
            check_in_type=ci.check_in_type.value,
            status=ci.status.value,
            scheduled_for=ci.scheduled_for,
            sent_at=ci.sent_at,
            responded_at=ci.responded_at,
            message_sent=ci.message_sent,
            user_response=ci.user_response,
            assistant_reply=ci.assistant_reply,
            conversation_context=ci.conversation_context,
            blocker_detected=ci.blocker_detected,
            reschedule_initiated=ci.reschedule_initiated
        )
        for ci in check_ins
    ]
