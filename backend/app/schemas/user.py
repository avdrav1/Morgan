from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    preferred_tone: Optional[str] = Field(None, pattern="^(coach|manager|buddy|drill_sergeant)$")
    custom_system_prompt: Optional[str] = None
    timezone: Optional[str] = None
    quiet_hours_start: Optional[str] = Field(None, pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    quiet_hours_end: Optional[str] = Field(None, pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    discord_user_id: Optional[str] = None


class QuietHoursUpdate(BaseModel):
    quiet_hours_start: Optional[str] = Field(None, pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", description="Start of quiet hours in HH:MM format")
    quiet_hours_end: Optional[str] = Field(None, pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", description="End of quiet hours in HH:MM format")


class ToneUpdate(BaseModel):
    preferred_tone: str = Field(..., pattern="^(coach|manager|buddy|drill_sergeant)$", description="Preferred tone for assistant communication")


class SystemPromptUpdate(BaseModel):
    custom_system_prompt: Optional[str] = Field(None, description="Custom system prompt for assistant personality")


class UserResponse(UserBase):
    id: UUID
    preferred_tone: str
    custom_system_prompt: Optional[str]
    timezone: str
    quiet_hours_start: Optional[str]
    quiet_hours_end: Optional[str]
    discord_user_id: Optional[str]
    messaging_paused: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None
