from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None


class TaskCreate(TaskBase):
    project_id: UUID
    order: int
    estimated_duration_hours: Optional[int] = None
    due_date: Optional[datetime] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(not_started|in_progress|blocked|completed|cancelled)$")
    due_date: Optional[datetime] = None
    blocker_type: Optional[str] = Field(None, pattern="^(time|clarity|emotional|external|scope)$")
    blocker_description: Optional[str] = None


class TaskResponse(TaskBase):
    id: UUID
    project_id: UUID
    order: int
    estimated_duration_hours: Optional[int]
    due_date: Optional[datetime]
    original_due_date: Optional[datetime]
    completed_at: Optional[datetime]
    status: str
    blocker_type: Optional[str]
    blocker_description: Optional[str]
    reschedule_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskCompleteRequest(BaseModel):
    notes: Optional[str] = None


class TaskRescheduleRequest(BaseModel):
    new_due_date: datetime
    reason: str
