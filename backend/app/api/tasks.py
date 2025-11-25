from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.metrics import track_task_completed
from app.models import User, Task, Project, TaskStatus
from app.schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskCompleteRequest,
    TaskRescheduleRequest
)

router = APIRouter()


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new task."""
    
    # Verify project ownership
    project = db.query(Project).filter(
        Project.id == task_data.project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    task = Task(
        project_id=task_data.project_id,
        title=task_data.title,
        description=task_data.description,
        order=task_data.order,
        estimated_duration_hours=task_data.estimated_duration_hours,
        due_date=task_data.due_date,
        original_due_date=task_data.due_date
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return task


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific task."""
    
    task = db.query(Task).join(Project).filter(
        Task.id == task_id,
        Project.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a task with optimistic locking protection.
    
    Requirements: 5.4 - Concurrent rescheduling protection
    """
    
    # Use FOR UPDATE lock to prevent concurrent modifications
    task = db.query(Task).join(Project).filter(
        Task.id == task_id,
        Project.user_id == current_user.id
    ).with_for_update().first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Store current version for optimistic locking
    current_version = task.version
    
    update_data = task_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(task, field, value)
    
    # Increment version for optimistic locking
    task.version = current_version + 1
    
    try:
        db.commit()
        db.refresh(task)
    except Exception as e:
        db.rollback()
        if "version" in str(e).lower() or "concurrent" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task was modified by another request. Please refresh and try again."
            )
        raise
    
    return task


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: UUID,
    complete_data: TaskCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a task as completed."""
    
    task = db.query(Task).join(Project).filter(
        Task.id == task_id,
        Project.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.utcnow()
    
    # Determine if task was completed on time
    on_time = True
    if task.due_date:
        on_time = task.completed_at <= task.due_date
    
    db.commit()
    db.refresh(task)
    
    # Track metrics: task completed
    track_task_completed(
        user_id=str(current_user.id),
        project_id=str(task.project_id),
        task_id=str(task.id),
        on_time=on_time
    )
    
    return task


@router.post("/{task_id}/reschedule", response_model=TaskResponse)
async def reschedule_task(
    task_id: UUID,
    reschedule_data: TaskRescheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reschedule a task with a reason."""
    
    task = db.query(Task).join(Project).filter(
        Task.id == task_id,
        Project.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Update task
    task.due_date = reschedule_data.new_due_date
    task.reschedule_count += 1
    
    # TODO: Log the reason in a conversation/check-in record
    
    db.commit()
    db.refresh(task)
    
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a task."""
    
    task = db.query(Task).join(Project).filter(
        Task.id == task_id,
        Project.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    db.delete(task)
    db.commit()
    
    return None
