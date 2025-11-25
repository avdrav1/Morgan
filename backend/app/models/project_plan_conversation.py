from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class ProjectPlanConversation(Base):
    """Tracks conversation state for project plan management."""
    __tablename__ = "project_plan_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    
    # Conversation state
    last_intent = Column(String, nullable=True)
    pending_confirmation = Column(JSON, nullable=True)  # JSON field for pending changes
    conversation_history = Column(JSON, nullable=False, default=list)  # Recent messages for context
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User")
    project = relationship("Project")
