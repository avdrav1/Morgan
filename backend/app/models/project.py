from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Project details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    goal = Column(Text, nullable=False)
    success_criteria = Column(Text, nullable=True)
    
    # Status and timeline
    status = Column(SQLEnum(ProjectStatus), default=ProjectStatus.ACTIVE)
    estimated_duration_weeks = Column(String, nullable=True)
    target_completion_date = Column(DateTime, nullable=True)
    actual_completion_date = Column(DateTime, nullable=True)
    
    # Ghosting tracking
    ghosting_stage = Column(Integer, default=0)  # 0=active, 1=2 missed, 2=4 missed, 3=7 missed
    
    # Custom settings for this project
    project_tone = Column(String, nullable=True)  # Override user's default tone
    project_context = Column(Text, nullable=True)  # Additional context for LLM
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="projects")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    check_ins = relationship("CheckIn", back_populates="project", cascade="all, delete-orphan")
    milestones = relationship("Milestone", back_populates="project", cascade="all, delete-orphan")
