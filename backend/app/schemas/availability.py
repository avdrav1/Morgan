from pydantic import BaseModel, Field, field_validator
from typing import List
from datetime import datetime
from uuid import UUID


class AvailabilityWindowBase(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    start_time: str = Field(..., pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", description="Start time in HH:MM format")
    end_time: str = Field(..., pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", description="End time in HH:MM format")


class AvailabilityWindowCreate(AvailabilityWindowBase):
    pass


class AvailabilityWindowResponse(AvailabilityWindowBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AvailabilityWindowsUpdate(BaseModel):
    windows: List[AvailabilityWindowCreate] = Field(..., description="List of availability windows to set for the user")
