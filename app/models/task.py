"""Task database model for extracted action items."""
import uuid
from datetime import datetime, date, timezone
from typing import Optional
from sqlalchemy import Column, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Task(Base):
    """Represents an actionable task extracted from a diary entry or created manually."""
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    diary_entry_id = Column(String(36), ForeignKey("diary_entries.id", ondelete="CASCADE"), nullable=True, index=True)
    diary_day_id = Column(String(36), ForeignKey("diary_days.id"), nullable=True, index=True)

    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    due_date = Column(Date, nullable=True, index=True)
    priority = Column(String(20), default="Medium", nullable=False)  # Low, Medium, High
    status = Column(String(20), default="Pending", nullable=False, index=True)  # Pending, Completed
    completed_at = Column(DateTime, nullable=True)

    # Relationship back to diary entry
    diary_entry = relationship("DiaryEntry", back_populates="tasks")
    diary_day = relationship("DiaryDay", back_populates="tasks")

    def mark_completed(self) -> None:
        """Mark task as completed."""
        self.status = "Completed"
        self.completed_at = utc_now()

    def reopen(self) -> None:
        """Reopen a completed task."""
        self.status = "Pending"
        self.completed_at = None

    def to_dict(self) -> dict:
        """Convert task to dictionary representation."""
        return {
            "id": self.id,
            "diary_entry_id": self.diary_entry_id,
            "diary_day_id": self.diary_day_id,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "priority": self.priority,
            "status": self.status,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
