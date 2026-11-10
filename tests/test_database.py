"""Tests for SQLite database operations, relationships, and model persistence."""
import pytest
from datetime import date, datetime
from app.models.diary_entry import DiaryEntry
from app.models.task import Task
from app.models.weekly_report import WeeklyReport


def test_database_creation(test_db_session):
    """Verify tables are created and queryable in SQLite."""
    entries_count = test_db_session.query(DiaryEntry).count()
    tasks_count = test_db_session.query(Task).count()
    reports_count = test_db_session.query(WeeklyReport).count()
    assert entries_count == 0
    assert tasks_count == 0
    assert reports_count == 0


def test_save_and_retrieve_diary_entry(test_db_session):
    """Test saving and querying a full diary entry with tasks."""
    entry = DiaryEntry(
        entry_date=date(2026, 11, 9),
        original_transcript="Studied operating systems and completed homework.",
        edited_transcript="Studied operating systems and completed homework with classmates.",
        summary_line_1="Studied operating systems concepts.",
        summary_line_2="Collaborated on homework assignments.",
        summary_line_3="Reviewed lecture notes for the exam.",
        primary_mood="Calm",
        secondary_mood="Grateful",
        mood_confidence=0.88,
        mood_evidence="Speaker reported calm studying and feeling prepared.",
    )
    entry.topics = ["Operating systems", "Homework", "Exams"]
    entry.highlights = ["Finished assignment early"]

    task = Task(
        description="Review chapter 4 slides",
        due_date=date(2026, 11, 12),
        priority="High",
        status="Pending",
    )
    entry.tasks.append(task)

    test_db_session.add(entry)
    test_db_session.commit()

    retrieved = test_db_session.query(DiaryEntry).filter(DiaryEntry.id == entry.id).first()
    assert retrieved is not None
    assert retrieved.entry_date == date(2026, 11, 9)
    assert retrieved.primary_mood == "Calm"
    assert retrieved.effective_transcript == "Studied operating systems and completed homework with classmates."
    assert len(retrieved.summary_lines) == 3
    assert "Operating systems" in retrieved.topics
    assert len(retrieved.tasks) == 1
    assert retrieved.tasks[0].description == "Review chapter 4 slides"


def test_edit_and_delete_entry(test_db_session):
    """Test editing transcript and verifying cascade deletion of associated tasks."""
    entry = DiaryEntry(
        entry_date=date(2026, 11, 10),
        original_transcript="Draft text",
        primary_mood="Neutral",
    )
    task = Task(description="Follow up with advisor", priority="Medium")
    entry.tasks.append(task)
    test_db_session.add(entry)
    test_db_session.commit()

    # Edit
    entry.edited_transcript = "Updated polished text"
    entry.primary_mood = "Excited"
    test_db_session.commit()

    updated = test_db_session.query(DiaryEntry).filter(DiaryEntry.id == entry.id).first()
    assert updated.effective_transcript == "Updated polished text"
    assert updated.primary_mood == "Excited"

    # Delete entry
    test_db_session.delete(updated)
    test_db_session.commit()

    # Verify entry and task are deleted
    assert test_db_session.query(DiaryEntry).filter(DiaryEntry.id == entry.id).first() is None
    assert test_db_session.query(Task).filter(Task.id == task.id).first() is None

