from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class OnboardingState(str, enum.Enum):
    """States in the onboarding flow."""
    WELCOME = "welcome"
    COLLECT_PROJECT_NAME = "collect_project_name"
    COLLECT_GOAL = "collect_goal"
    COLLECT_DEADLINE = "collect_deadline"
    CONFIRM_DEADLINE = "confirm_deadline"
    COLLECT_CHECKIN_FREQUENCY = "collect_checkin_frequency"
    COLLECT_TONE = "collect_tone"
    CONFIRM_DETAILS = "confirm_details"
    SHOW_SUMMARY = "show_summary"
    CREATING_PROJECT = "creating_project"
    COMPLETED = "completed"
    PAUSED = "paused"
    FAILED = "failed"


class OnboardingSession(Base):
    """Tracks a user's progress through the Discord DM onboarding flow."""
    __tablename__ = "onboarding_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    discord_id = Column(String, nullable=False, index=True)
    
    # State tracking
    current_state = Column(SQLEnum(OnboardingState), nullable=False, default=OnboardingState.WELCOME)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_activity_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Collected data
    project_name = Column(String, nullable=True)
    project_goal = Column(Text, nullable=True)
    deadline = Column(DateTime, nullable=True)
    checkin_frequency = Column(String, nullable=True)
    preferred_tone = Column(String, nullable=True)
    
    # Conversation history - stored as list of dicts with timestamp, role, message
    conversation_history = Column(JSON, nullable=False, default=list)
    
    # Metadata
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="onboarding_sessions")
