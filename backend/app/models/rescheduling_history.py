from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class ReschedulingHistory(Base):
    __tablename__ = "rescheduling_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    
    # Rescheduling details
    old_due_date = Column(DateTime, nullable=False)
    new_due_date = Column(DateTime, nullable=False)
    reason = Column(Text, nullable=False)
    blocker_type = Column(String, nullable=True)  # time, clarity, emotional, external, scope
    initiated_by = Column(String, nullable=False)  # user or assistant
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    task = relationship("Task", backref="rescheduling_history")
