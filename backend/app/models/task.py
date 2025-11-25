from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class TaskStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    
    # Task details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, nullable=False)  # Sequence in the project
    
    # Timeline
    estimated_duration_hours = Column(Integer, nullable=True)
    due_date = Column(DateTime, nullable=True)
    original_due_date = Column(DateTime, nullable=True)  # Track rescheduling
    completed_at = Column(DateTime, nullable=True)
    
    # Status
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.NOT_STARTED)
    
    # Blocker tracking
    blocker_type = Column(String, nullable=True)  # time, clarity, emotional, external, scope
    blocker_description = Column(Text, nullable=True)
    blocker_diagnosed_at = Column(DateTime, nullable=True)
    reschedule_count = Column(Integer, default=0)
    
    # Optimistic locking for concurrent rescheduling protection (Requirements: 5.4)
    version = Column(Integer, default=1, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="tasks")
    check_ins = relationship("CheckIn", back_populates="task", cascade="all, delete-orphan")
