"""
Database model for tracking suggestions shown to users.

This model tracks which suggestions have been shown to users and
whether they were accepted or declined, to avoid repeating declined
suggestions.
"""

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class SuggestionTracking(Base):
    """
    Database model for tracking suggestions.
    
    Tracks which suggestions have been shown to users and their responses
    to avoid repeating declined suggestions.
    """
    __tablename__ = "suggestion_tracking"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Suggestion details
    suggestion_type = Column(String, nullable=False)  # Type from SuggestionType
    suggestion_hash = Column(String, nullable=False, index=True)  # Hash of suggestion content for deduplication
    message = Column(String, nullable=False)
    reasoning = Column(String, nullable=False)
    
    # Tracking
    shown_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_response = Column(String, nullable=True)  # 'accepted', 'declined', or None if no response yet
    responded_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    project = relationship("Project")
    user = relationship("User")
