from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # Nullable for OAuth-only users
    full_name = Column(String, nullable=True)
    
    # Discord OAuth fields
    discord_user_id = Column(String, unique=True, nullable=True, index=True)
    discord_username = Column(String, nullable=True)
    discord_discriminator = Column(String, nullable=True)
    discord_avatar = Column(String, nullable=True)
    discord_access_token = Column(Text, nullable=True)  # Encrypted
    discord_refresh_token = Column(Text, nullable=True)  # Encrypted
    discord_token_expires_at = Column(DateTime, nullable=True)
    
    # OAuth metadata
    is_new = Column(Boolean, default=True)  # For onboarding redirect
    oauth_provider = Column(String, nullable=True)  # 'discord', 'email', etc.
    
    # User preferences
    preferred_tone = Column(String, default="coach")  # coach, manager, buddy, drill_sergeant
    custom_system_prompt = Column(Text, nullable=True)
    timezone = Column(String, default="UTC")
    
    # Quiet hours (stored as JSON-compatible string)
    quiet_hours_start = Column(String, nullable=True)  # e.g., "22:00"
    quiet_hours_end = Column(String, nullable=True)    # e.g., "08:00"
    
    # Engagement tracking
    total_check_ins_sent = Column(Integer, default=0)
    total_check_ins_responded = Column(Integer, default=0)
    consecutive_missed_check_ins = Column(Integer, default=0)
    last_active_at = Column(DateTime, nullable=True)
    
    # Messaging control
    messaging_paused = Column(Boolean, default=False)
    
    # Data deletion
    deletion_scheduled_at = Column(DateTime, nullable=True)
    
    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    availability_windows = relationship("AvailabilityWindow", back_populates="user", cascade="all, delete-orphan")
