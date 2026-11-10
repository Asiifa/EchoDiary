"""Weekly digest calculation and persistence service."""
import json
from datetime import date, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.diary_entry import DiaryEntry
from app.models.task import Task
from app.models.weekly_report import WeeklyReport
from app.services.ollama_service import OllamaService
from app.schemas.weekly_schema import WeeklyDigestOutput
from app.utils.date_utils import format_short_date, format_display_date


class WeeklyDigestService:
    """Manages aggregation of 7-day diary entries, AI synthesis, and report generation."""

    def __init__(self, ollama_service: Optional[OllamaService] = None):
        self.ollama = ollama_service or OllamaService()

    def get_entries_in_range(self, session: Session, start_date: date, end_date: date) -> List[DiaryEntry]:
        """Fetch non-deleted, session-bound diary rows for the specified date range."""
        return (
            session.query(DiaryEntry)
            .filter(
                and_(
                    DiaryEntry.entry_date >= start_date,
                    DiaryEntry.entry_date <= end_date,
                    DiaryEntry.is_deleted == False,
                )
            )
            .order_by(DiaryEntry.entry_date.asc())
            .all()
        )

    def calculate_mood_distribution(self, entries: List[DiaryEntry]) -> Dict[str, int]:
        """Calculate frequency count for each mood category in the entries."""
        counts: Dict[str, int] = {}
        for entry in entries:
            m = entry.primary_mood or "Neutral"
            counts[m] = counts.get(m, 0) + 1
        return counts

    def calculate_mood_timeline(self, entries: List[DiaryEntry]) -> List[Dict[str, Any]]:
        """Calculate day-by-day mood trajectory."""
        timeline = []
        for entry in entries:
            timeline.append({
                "date": entry.entry_date.isoformat(),
                "mood": entry.primary_mood or "Neutral",
                "confidence": entry.mood_confidence,
            })
        return timeline

    def generate_digest(
        self,
        session: Session,
        start_date: date,
        end_date: date,
    ) -> WeeklyReport:
        """
        Synthesize entries from start_date to end_date into a structured WeeklyReport.
        Saves the report using the caller-owned session and returns a session-bound
        ORM object. Convert it to plain data before leaving that session.
        """
        entries = self.get_entries_in_range(session, start_date, end_date)
        entries_count = len(entries)
        is_partial = entries_count < 7

        # Aggregate task statistics for the week
        tasks_in_range = (
            session.query(Task)
            .join(DiaryEntry, Task.diary_entry_id == DiaryEntry.id)
            .filter(
                and_(
                    DiaryEntry.entry_date >= start_date,
                    DiaryEntry.entry_date <= end_date,
                )
            )
            .all()
        )
        pending_tasks = [t for t in tasks_in_range if t.status == "Pending"]
        completed_tasks = [t for t in tasks_in_range if t.status == "Completed"]

        mood_dist = self.calculate_mood_distribution(entries)
        mood_timeline = self.calculate_mood_timeline(entries)

        if entries_count == 0:
            # Handle empty week gracefully without crashing
            report = WeeklyReport(
                start_date=start_date,
                end_date=end_date,
                overview=f"No diary entries were logged between {format_display_date(start_date)} and {format_display_date(end_date)}. Start recording your daily voice diary to see weekly insights here.",
                highlights_json="[]",
                accomplishments_json="[]",
                main_topics_json="[]",
                mood_distribution_json=json.dumps(mood_dist),
                mood_trends_json=json.dumps(mood_timeline),
                recurring_themes_json="[]",
                suggested_priorities_json=json.dumps(["Record your first diary entry for the upcoming week", "Set daily reminder for voice check-in"]),
                pending_tasks_count=0,
                completed_tasks_count=0,
                is_partial_week=True,
                entries_count=0,
            )
            session.add(report)
            session.flush()
            return report

        # Prepare entries payload for Ollama
        entries_payload = [e.to_dict() for e in entries]

        # Call Ollama local model
        ai_output: WeeklyDigestOutput = self.ollama.generate_weekly_digest(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            entries_data=entries_payload,
            pending_tasks_count=len(pending_tasks),
            completed_tasks_count=len(completed_tasks),
        )

        # Check if an existing report exists for this exact range and update or create
        existing = (
            session.query(WeeklyReport)
            .filter(and_(WeeklyReport.start_date == start_date, WeeklyReport.end_date == end_date))
            .first()
        )

        if existing:
            report = existing
            report.overview = ai_output.overview
            report.highlights_json = json.dumps(ai_output.highlights)
            report.accomplishments_json = json.dumps(ai_output.accomplishments)
            report.main_topics_json = json.dumps(ai_output.main_topics)
            report.mood_distribution_json = json.dumps(mood_dist)
            report.mood_trends_json = json.dumps(mood_timeline)
            report.recurring_themes_json = json.dumps(ai_output.recurring_themes)
            report.suggested_priorities_json = json.dumps(ai_output.suggested_priorities)
            report.pending_tasks_count = len(pending_tasks)
            report.completed_tasks_count = len(completed_tasks)
            report.is_partial_week = is_partial
            report.entries_count = entries_count
        else:
            report = WeeklyReport(
                start_date=start_date,
                end_date=end_date,
                overview=ai_output.overview,
                highlights_json=json.dumps(ai_output.highlights),
                accomplishments_json=json.dumps(ai_output.accomplishments),
                main_topics_json=json.dumps(ai_output.main_topics),
                mood_distribution_json=json.dumps(mood_dist),
                mood_trends_json=json.dumps(mood_timeline),
                recurring_themes_json=json.dumps(ai_output.recurring_themes),
                suggested_priorities_json=json.dumps(ai_output.suggested_priorities),
                pending_tasks_count=len(pending_tasks),
                completed_tasks_count=len(completed_tasks),
                is_partial_week=is_partial,
                entries_count=entries_count,
            )
            session.add(report)

        session.flush()
        return report

    @staticmethod
    def get_saved_reports(session: Session) -> List[WeeklyReport]:
        """Fetch session-bound reports ordered by date descending."""
        return session.query(WeeklyReport).order_by(WeeklyReport.start_date.desc()).all()
