"""Date-level diary record containing combined analysis for its recordings."""
import json
import uuid
from datetime import date, datetime, timezone
from typing import List

from sqlalchemy import Column, Date, DateTime, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DiaryDay(Base):
    """A calendar day that groups multiple individual voice recordings."""

    __tablename__ = "diary_days"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entry_date = Column(Date, nullable=False, unique=True, index=True)
    combined_summary_line_1 = Column(Text, nullable=True)
    combined_summary_line_2 = Column(Text, nullable=True)
    combined_summary_line_3 = Column(Text, nullable=True)
    recurring_topics_json = Column(Text, nullable=False, default="[]")
    new_developments_json = Column(Text, nullable=False, default="[]")
    completed_items_json = Column(Text, nullable=False, default="[]")
    outstanding_items_json = Column(Text, nullable=False, default="[]")
    analysis_task_ids_json = Column(Text, nullable=False, default="[]")
    analysis_updated_at = Column(DateTime, nullable=True)

    recordings = relationship("DiaryEntry", back_populates="diary_day")
    tasks = relationship("Task", back_populates="diary_day")

    @property
    def combined_summary_lines(self) -> List[str]:
        return [
            line.strip()
            for line in (
                self.combined_summary_line_1,
                self.combined_summary_line_2,
                self.combined_summary_line_3,
            )
            if line and line.strip()
        ]

    def get_list(self, field_name: str) -> List[str]:
        value = getattr(self, f"{field_name}_json")
        try:
            data = json.loads(value or "[]")
        except (TypeError, ValueError):
            return []
        return [str(item) for item in data if str(item).strip()] if isinstance(data, list) else []

    def set_list(self, field_name: str, values: List[str]) -> None:
        setattr(self, f"{field_name}_json", json.dumps(values or []))

    @property
    def analysis_task_ids(self) -> List[str]:
        return self.get_list("analysis_task_ids")

    @analysis_task_ids.setter
    def analysis_task_ids(self, values: List[str]) -> None:
        self.set_list("analysis_task_ids", values)
