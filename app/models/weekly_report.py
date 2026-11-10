"""WeeklyReport database model."""
import json
import uuid
from datetime import datetime, date, timezone
from typing import List, Dict, Any
from sqlalchemy import Column, String, Text, Integer, Boolean, Date, DateTime
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WeeklyReport(Base):
    """Represents a generated weekly digest spanning a 7-day period."""
    __tablename__ = "weekly_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    overview = Column(Text, nullable=False)
    highlights_json = Column(Text, default="[]")
    accomplishments_json = Column(Text, default="[]")
    main_topics_json = Column(Text, default="[]")
    mood_distribution_json = Column(Text, default="{}")
    mood_trends_json = Column(Text, default="[]")
    recurring_themes_json = Column(Text, default="[]")
    suggested_priorities_json = Column(Text, default="[]")

    pending_tasks_count = Column(Integer, default=0)
    completed_tasks_count = Column(Integer, default=0)
    is_partial_week = Column(Boolean, default=False)
    entries_count = Column(Integer, default=0)

    @property
    def highlights(self) -> List[str]:
        return json.loads(self.highlights_json or "[]")

    @property
    def accomplishments(self) -> List[str]:
        return json.loads(self.accomplishments_json or "[]")

    @property
    def main_topics(self) -> List[str]:
        return json.loads(self.main_topics_json or "[]")

    @property
    def mood_distribution(self) -> Dict[str, int]:
        return json.loads(self.mood_distribution_json or "{}")

    @property
    def mood_trends(self) -> List[Dict[str, Any]]:
        return json.loads(self.mood_trends_json or "[]")

    @property
    def recurring_themes(self) -> List[str]:
        return json.loads(self.recurring_themes_json or "[]")

    @property
    def suggested_priorities(self) -> List[str]:
        return json.loads(self.suggested_priorities_json or "[]")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "overview": self.overview,
            "highlights": self.highlights,
            "accomplishments": self.accomplishments,
            "main_topics": self.main_topics,
            "mood_distribution": self.mood_distribution,
            "mood_trends": self.mood_trends,
            "recurring_themes": self.recurring_themes,
            "suggested_priorities": self.suggested_priorities,
            "pending_tasks_count": self.pending_tasks_count,
            "completed_tasks_count": self.completed_tasks_count,
            "is_partial_week": self.is_partial_week,
            "entries_count": self.entries_count,
        }
