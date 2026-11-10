"""Persistence helpers for date-level diary analysis."""
import re
from difflib import SequenceMatcher
from datetime import date, datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app.models.diary_day import DiaryDay
from app.models.task import Task
from app.schemas.analysis_schema import CombinedDailyAnalysisOutput


def _normalized_task(description: str) -> str:
    return re.sub(r"\W+", " ", description.casefold()).strip()


class DiaryDayService:
    """Create date groups and update combined analysis without replacing recordings."""

    @staticmethod
    def get_or_create(session: Session, entry_date: date) -> DiaryDay:
        day = session.query(DiaryDay).filter(DiaryDay.entry_date == entry_date).first()
        if day is None:
            day = DiaryDay(entry_date=entry_date)
            session.add(day)
            session.flush()
        return day

    @staticmethod
    def update_analysis(
        session: Session,
        day: DiaryDay,
        analysis: CombinedDailyAnalysisOutput,
    ) -> None:
        day.combined_summary_line_1 = analysis.summary[0]
        day.combined_summary_line_2 = analysis.summary[1]
        day.combined_summary_line_3 = analysis.summary[2]
        day.set_list("recurring_topics", analysis.recurring_topics)
        day.set_list("new_developments", analysis.new_developments)
        day.set_list("completed_items", analysis.completed_items)
        day.set_list("outstanding_items", analysis.outstanding_items)

        day_tasks = (
            session.query(Task)
            .filter(Task.diary_day_id == day.id)
            .order_by(Task.created_at.asc())
            .all()
        )
        task_ids: List[str] = []
        matched_task_ids = set()
        for candidate in analysis.tasks[:3]:
            normalized = _normalized_task(candidate.description)
            if not normalized:
                continue
            existing = next(
                (
                    task
                    for task in day_tasks
                    if (
                        _normalized_task(task.description) == normalized
                        or SequenceMatcher(
                            None, _normalized_task(task.description), normalized
                        ).ratio() >= 0.88
                    )
                ),
                None,
            )
            if existing is not None and existing.id in matched_task_ids:
                continue
            if existing is None:
                from app.utils.date_utils import parse_date

                existing = Task(
                    diary_day_id=day.id,
                    description=candidate.description.strip(),
                    due_date=parse_date(candidate.due_date) if candidate.due_date else None,
                    priority=candidate.priority,
                    status="Pending",
                )
                session.add(existing)
                session.flush()
                day_tasks.append(existing)
            matched_task_ids.add(existing.id)
            task_ids.append(existing.id)

        day.analysis_task_ids = task_ids
        day.analysis_updated_at = DiaryDayService._now()
        session.flush()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).replace(tzinfo=None)
