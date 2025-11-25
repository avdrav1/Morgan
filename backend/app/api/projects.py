from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Union
from uuid import UUID

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import User, Project, Task
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectWithTasksResponse,
    ProjectClarificationResponse,
    ProjectClarificationUpdate,
    ClarificationQuestion,
    TimelineProposal,
    TimelineApproval
)
from app.services.llm_service import llm_service
from datetime import datetime, timedelta

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new project with free-form description.
    
    Accepts free-form project descriptions and initiates clarification flow.
    Returns either a ProjectResponse (if enough info provided) or 
    ProjectClarificationResponse (if clarification needed).
    """
    
    # Check if we have enough structured information to create the project directly
    has_title = project_data.title is not None
    has_goal = project_data.goal is not None
    
    if has_title and has_goal:
        # Sufficient information - create project directly
        project = Project(
            user_id=current_user.id,
            title=project_data.title,
            description=project_data.description,
            goal=project_data.goal,
            success_criteria=project_data.success_criteria,
            estimated_duration_weeks=project_data.estimated_duration_weeks,
            target_completion_date=project_data.target_completion_date,
            project_tone=project_data.project_tone,
            project_context=project_data.project_context
        )
        
        db.add(project)
        db.commit()
        db.refresh(project)
        
        return ProjectResponse.model_validate(project)
    
    else:
        # Need clarification - create a draft project and generate questions
        # Use description as both title and goal temporarily
        project = Project(
            user_id=current_user.id,
            title=project_data.title or "Draft Project",
            description=project_data.description,
            goal=project_data.goal or project_data.description,
            success_criteria=project_data.success_criteria,
            estimated_duration_weeks=project_data.estimated_duration_weeks,
            target_completion_date=project_data.target_completion_date,
            project_tone=project_data.project_tone,
            project_context=project_data.project_context,
            status="active"  # Will be updated after clarification
        )
        
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # Generate clarification questions using LLM
        existing_info = {
            "description": project_data.description,
            "title": project_data.title,
            "goal": project_data.goal,
            "success_criteria": project_data.success_criteria
        }
        
        questions_data = await llm_service.generate_clarification_questions(
            current_user,
            project_data.description,
            existing_info
        )
        
        clarification_questions = [
            ClarificationQuestion(**q) for q in questions_data
        ]
        
        current_understanding = {
            "description": project_data.description,
            "title": project_data.title,
            "goal": project_data.goal,
            "success_criteria": project_data.success_criteria
        }
        
        return ProjectClarificationResponse(
            project_id=project.id,
            status="needs_clarification",
            clarification_questions=clarification_questions,
            current_understanding=current_understanding
        )


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all projects for current user."""
    
    projects = db.query(Project).filter(Project.user_id == current_user.id).all()
    return projects


@router.get("/{project_id}", response_model=ProjectWithTasksResponse)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific project with its tasks."""
    
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project


@router.post("/{project_id}/clarify", response_model=ProjectResponse)
async def clarify_project(
    project_id: UUID,
    clarification: ProjectClarificationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Process clarification answers and finalize project details."""
    
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Process answers through LLM to extract structured information
    structured_info = await llm_service.process_clarification_answers(
        current_user,
        project.description,
        clarification.answers
    )
    
    # Update project with clarified information
    project.title = structured_info.get("title", project.title)
    project.goal = structured_info.get("goal", project.goal)
    project.description = structured_info.get("description", project.description)
    project.success_criteria = structured_info.get("success_criteria", project.success_criteria)
    project.estimated_duration_weeks = structured_info.get("estimated_duration_weeks", project.estimated_duration_weeks)
    
    db.commit()
    db.refresh(project)
    
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_update: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a project."""
    
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    update_data = project_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(project, field, value)
    
    db.commit()
    db.refresh(project)
    
    return project


@router.put("/{project_id}/timeline", response_model=ProjectWithTasksResponse)
async def approve_timeline(
    project_id: UUID,
    timeline_approval: TimelineApproval,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Approve and optionally modify the proposed timeline.
    
    This endpoint:
    1. Accepts user approval of the proposed timeline
    2. Allows user to modify task details before confirmation
    3. Creates all tasks in the database once approved
    4. Updates the project's target completion date
    """
    
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if not timeline_approval.approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Timeline must be approved to create tasks"
        )
    
    # Use modifications if provided, otherwise this should be called after decompose
    # In a real implementation, the frontend would store the proposed timeline
    # and send it back with modifications
    if not timeline_approval.modifications:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Timeline modifications must be provided"
        )
    
    # Create tasks from the approved/modified timeline
    created_tasks = []
    latest_due_date = None
    
    for task_data in timeline_approval.modifications:
        due_date = None
        if task_data.get("due_date"):
            due_date = datetime.fromisoformat(task_data["due_date"].replace('Z', '+00:00'))
            if not latest_due_date or due_date > latest_due_date:
                latest_due_date = due_date
        
        task = Task(
            project_id=project.id,
            title=task_data["title"],
            description=task_data.get("description"),
            order=task_data["order"],
            estimated_duration_hours=task_data.get("estimated_duration_hours"),
            due_date=due_date,
            original_due_date=due_date
        )
        
        db.add(task)
        created_tasks.append(task)
    
    # Update project's target completion date based on latest task
    if latest_due_date:
        project.target_completion_date = latest_due_date
    
    db.commit()
    
    # Refresh to get all relationships
    db.refresh(project)
    
    return project


@router.post("/{project_id}/pause", response_model=ProjectResponse)
async def pause_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Pause a project.
    
    Paused projects will not trigger proactive check-ins.
    """
    
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    project.status = "paused"
    db.commit()
    db.refresh(project)
    
    return project


@router.post("/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Archive a project.
    
    Archived projects are hidden from active view and will not trigger check-ins.
    """
    
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    project.status = "archived"
    db.commit()
    db.refresh(project)
    
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a project."""
    
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    db.delete(project)
    db.commit()
    
    return None


@router.post("/{project_id}/decompose", response_model=TimelineProposal)
async def decompose_project_into_tasks(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Use LLM to decompose project into tasks and propose a timeline.
    
    This endpoint:
    1. Calls the LLM service to break down the project into 5-20 tasks
    2. Calculates realistic due dates for each task
    3. Returns a proposed timeline for user approval
    
    Note: Tasks are NOT created in the database until the timeline is approved.
    """
    
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Generate tasks using LLM (5-20 tasks based on complexity)
    tasks_data = await llm_service.decompose_project(current_user, project)
    
    # Calculate total estimated hours
    total_hours = sum(task.get("estimated_duration_hours", 0) for task in tasks_data)
    
    # Calculate proposed completion date if not already set
    estimated_completion_date = project.target_completion_date
    if not estimated_completion_date and total_hours > 0:
        # Assume 4 hours of productive work per day
        days_needed = total_hours / 4
        estimated_completion_date = datetime.utcnow() + timedelta(days=days_needed)
    
    # Calculate due dates for each task
    tasks_with_dates = []
    for i, task_data in enumerate(tasks_data):
        if estimated_completion_date:
            # Distribute tasks evenly across the timeline
            days_per_task = (estimated_completion_date - datetime.utcnow()).days / len(tasks_data)
            due_date = datetime.utcnow() + timedelta(days=days_per_task * (i + 1))
        else:
            due_date = None
        
        tasks_with_dates.append({
            "title": task_data["title"],
            "description": task_data.get("description"),
            "order": task_data["order"],
            "estimated_duration_hours": task_data.get("estimated_duration_hours"),
            "due_date": due_date.isoformat() if due_date else None
        })
    
    # Return proposed timeline (not yet saved to database)
    return TimelineProposal(
        project_id=project.id,
        tasks=tasks_with_dates,
        estimated_completion_date=estimated_completion_date,
        total_estimated_hours=total_hours
    )
