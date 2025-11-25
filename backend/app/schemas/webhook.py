"""
Webhook schemas for external integrations.
"""

from pydantic import BaseModel, Field, validator
from uuid import UUID
from typing import Optional


class OnboardingWebhookPayload(BaseModel):
    """
    Payload for the onboarding webhook.
    
    Sent when a new user completes OAuth and needs to start onboarding.
    """
    user_id: UUID = Field(..., description="UUID of the user")
    discord_id: str = Field(..., description="Discord user ID")
    email: Optional[str] = Field(None, description="User's email address")
    
    @validator('discord_id')
    def validate_discord_id(cls, v):
        """Validate that discord_id is not empty."""
        if not v or not v.strip():
            raise ValueError("discord_id cannot be empty")
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "discord_id": "123456789012345678",
                "email": "user@example.com"
            }
        }
