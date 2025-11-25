from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class CheckInType(str, enum.Enum):
    SCHEDULED = "scheduled"  # Proactive check-in
    USER_INITIATED = "user_initiated"
    BLOCKER_FOLLOWUP = "blocker_followup"
    MILESTONE = "milestone"


class CheckInStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    RESPONDED = "responded"
    MISSED = "missed"


class CheckIn(Base):
    __tablename__ = "check_ins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    
    # Check-in details
    check_in_type = Column(SQLEnum(CheckInType), nullable=False)
    status = Column(SQLEnum(CheckInStatus), default=CheckInStatus.PENDING)
    
    # Scheduling
    scheduled_for = Column(DateTime, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    responded_at = Column(DateTime, nullable=True)
    
    # Message content
    message_sent = Column(Text, nullable=True)
    user_response = Column(Text, nullable=True)
    assistant_reply = Column(Text, nullable=True)
    
    # Conversation context (stored as JSON)
    conversation_context = Column(JSONB, nullable=True)
    
    # Response tracking
    blocker_detected = Column(Boolean, default=False)
    reschedule_initiated = Column(Boolean, default=False)
    response_time_minutes = Column(Integer, nullable=True)
    sentiment = Column(String, nullable=True)  # positive, neutral, negative, blocked
    
    # Metadata
    platform = Column(String, default="discord")  # discord, web, sms, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="check_ins")
    task = relationship("Task", back_populates="check_ins")
