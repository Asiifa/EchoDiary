"""DiaryEntry database model."""
import json
import uuid
from datetime import datetime, date, timezone
from typing import List, Optional
from sqlalchemy import Column, String, Text, Float, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DiaryEntry(Base):
    """Represents a single daily voice diary entry."""
    __tablename__ = "diary_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entry_date = Column(Date, nullable=False, index=True)
    diary_day_id = Column(String(36), ForeignKey("diary_days.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Audio details
    audio_file_path = Column(String(500), nullable=True)
    duration_seconds = Column(Float, default=0.0, nullable=False)

    # Transcripts
    original_transcript = Column(Text, nullable=False, default="")
    edited_transcript = Column(Text, nullable=True)

    # Three-line summary
    summary_line_1 = Column(Text, nullable=True)
    summary_line_2 = Column(Text, nullable=True)
    summary_line_3 = Column(Text, nullable=True)

    # Mood analysis
    primary_mood = Column(String(50), nullable=True, default="Neutral")
    secondary_mood = Column(String(50), nullable=True)
    mood_confidence = Column(Float, default=0.0)
    mood_evidence = Column(Text, nullable=True)

    # Metadata lists (stored as JSON text)
    topics_json = Column(Text, default="[]")
    highlights_json = Column(Text, default="[]")

    is_deleted = Column(Boolean, default=False, index=True)

    # Relationships
    tasks = relationship("Task", back_populates="diary_entry", cascade="all, delete-orphan")
    diary_day = relationship("DiaryDay", back_populates="recordings")

    @property
    def effective_transcript(self) -> str:
        """Return the edited transcript if present and non-empty, otherwise original."""
        if self.edited_transcript and self.edited_transcript.strip():
            return self.edited_transcript
        return self.original_transcript or ""

    @property
    def summary_lines(self) -> List[str]:
        """Return the three summary lines as a clean list."""
        lines = []
        for line in (self.summary_line_1, self.summary_line_2, self.summary_line_3):
            if line and line.strip():
                lines.append(line.strip())
        return lines

    @property
    def topics(self) -> List[str]:
        """Deserialize topics from JSON."""
        if not self.topics_json:
            return []
        try:
            data = json.loads(self.topics_json)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @topics.setter
    def topics(self, value: List[str]) -> None:
        self.topics_json = json.dumps(value or [])

    @property
    def highlights(self) -> List[str]:
        """Deserialize highlights from JSON."""
        if not self.highlights_json:
            return []
        try:
            data = json.loads(self.highlights_json)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @highlights.setter
    def highlights(self, value: List[str]) -> None:
        self.highlights_json = json.dumps(value or [])

    def to_dict(self) -> dict:
        """Convert entry to dictionary for export and UI presentation."""
        return {
            "id": self.id,
            "entry_date": self.entry_date.isoformat() if self.entry_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "audio_file_path": self.audio_file_path,
            "duration_seconds": self.duration_seconds,
            "original_transcript": self.original_transcript,
            "edited_transcript": self.edited_transcript,
            "effective_transcript": self.effective_transcript,
            "summary": self.summary_lines,
            "primary_mood": self.primary_mood,
            "secondary_mood": self.secondary_mood,
            "mood_confidence": self.mood_confidence,
            "mood_evidence": self.mood_evidence,
            "topics": self.topics,
            "highlights": self.highlights,
            "tasks": [t.to_dict() for t in self.tasks] if self.tasks else [],
        }
