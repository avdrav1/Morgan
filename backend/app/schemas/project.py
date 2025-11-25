from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class ProjectBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str
    goal: str


class ProjectCreate(BaseModel):
    """Create a project with free-form description.
    
    Supports both structured input (title, description, goal) and
    free-form input (just description) for conversational clarification.
    """
    # Free-form input - user can provide just this
    description: str = Field(..., min_length=1)
    
    # Optional structured fields - can be filled during clarification
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    goal: Optional[str] = None
    success_criteria: Optional[str] = None
    estimated_duration_weeks: Optional[str] = None
    target_completion_date: Optional[datetime] = None
    project_tone: Optional[str] = Field(None, pattern="^(coach|manager|buddy|drill_sergeant)$")
    project_context: Optional[str] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    goal: Optional[str] = None
    success_criteria: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|paused|completed|archived)$")
    target_completion_date: Optional[datetime] = None
    project_tone: Optional[str] = Field(None, pattern="^(coach|manager|buddy|drill_sergeant)$")
    project_context: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: UUID
    user_id: UUID
    status: str
    success_criteria: Optional[str]
    estimated_duration_weeks: Optional[str]
    target_completion_date: Optional[datetime]
    actual_completion_date: Optional[datetime]
    project_tone: Optional[str]
    project_context: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectWithTasksResponse(ProjectResponse):
    tasks: List["TaskResponse"] = []


class ClarificationQuestion(BaseModel):
    """A clarification question from the LLM."""
    question: str
    field: str  # Which field this question is clarifying (e.g., 'goal', 'scope', 'deadline')


class ProjectClarificationResponse(BaseModel):
    """Response when project needs clarification."""
    project_id: UUID
    status: str = "needs_clarification"
    clarification_questions: List[ClarificationQuestion]
    current_understanding: Dict[str, Optional[str]]  # What we know so far


class ProjectClarificationUpdate(BaseModel):
    """User's answers to clarification questions."""
    answers: Dict[str, str]  # field -> answer mapping


class TimelineProposal(BaseModel):
    """Proposed timeline with tasks."""
    project_id: UUID
    tasks: List[Dict[str, Any]]
    estimated_completion_date: Optional[datetime]
    total_estimated_hours: int


class TimelineApproval(BaseModel):
    """User approval/modification of timeline."""
    approved: bool
    modifications: Optional[List[Dict[str, Any]]] = None  # Modified task data


# Import after to avoid circular dependency
from app.schemas.task import TaskResponse
from typing import Dict, Any
ProjectWithTasksResponse.model_rebuild()
