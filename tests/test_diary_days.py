"""Tests for date-level diary persistence, combined analysis, and migration."""
import json

from sqlalchemy import create_engine, text

from app.database import _migrate_diary_days
from app.models.diary_day import DiaryDay
from app.models.diary_entry import DiaryEntry
from app.models.task import Task
from app.schemas.analysis_schema import CombinedDailyAnalysisOutput
from app.services.diary_day_service import DiaryDayService
from app.services.ollama_service import OllamaService


def _combined_analysis(tasks=None):
    return CombinedDailyAnalysisOutput(
        summary=["Morning progress.", "A new development.", "One item remains."],
        recurring_topics=["Coursework"],
        new_developments=["The group project moved forward."],
        completed_items=["Resolved the query issue."],
        outstanding_items=["Submit the report."],
        tasks=tasks or [],
    )


def test_multiple_recordings_share_a_day_and_update_combined_analysis(
    test_db_session,
):
    from datetime import date, datetime

    entry_date = date(2026, 11, 9)
    day = DiaryDayService.get_or_create(test_db_session, entry_date)
    first = DiaryEntry(
        entry_date=entry_date,
        diary_day=day,
        created_at=datetime(2026, 11, 9, 9, 0),
        original_transcript="We resolved the indexing issue.",
    )
    second = DiaryEntry(
        entry_date=entry_date,
        diary_day=day,
        created_at=datetime(2026, 11, 9, 15, 0),
        original_transcript="The report is still due Friday.",
    )
    completed_task = Task(
        diary_day=day,
        description="Submit the literature survey",
        status="Completed",
    )
    test_db_session.add_all([first, second, completed_task])
    test_db_session.commit()
    first_id, second_id = first.id, second.id
    task_id = completed_task.id

    analysis = _combined_analysis([
        {
            "description": "Submit the literature survey!",
            "due_date": "2026-11-13",
            "priority": "High",
        },
        {
            "description": "Schedule the team review",
            "due_date": None,
            "priority": "Medium",
        },
        {
            "description": "Schedule the team review.",
            "due_date": None,
            "priority": "Medium",
        },
    ])
    DiaryDayService.update_analysis(test_db_session, day, analysis)
    test_db_session.commit()

    assert test_db_session.query(DiaryEntry).filter(
        DiaryEntry.diary_day_id == day.id
    ).count() == 2
    assert [entry.id for entry in test_db_session.query(DiaryEntry)
            .filter(DiaryEntry.diary_day_id == day.id)
            .order_by(DiaryEntry.created_at.asc()).all()] == [first_id, second_id]
    assert day.combined_summary_lines == analysis.summary
    assert day.get_list("recurring_topics") == ["Coursework"]
    assert day.get_list("completed_items") == ["Resolved the query issue."]
    assert len(day.analysis_task_ids) == 2
    assert day.analysis_task_ids[0] == task_id
    assert completed_task.status == "Completed"

    DiaryDayService.update_analysis(
        test_db_session,
        day,
        _combined_analysis([{
            "description": "submit the literature survey",
            "due_date": None,
            "priority": "High",
        }]),
    )
    test_db_session.commit()
    assert test_db_session.query(Task).filter(
        Task.diary_day_id == day.id
    ).count() == 2
    assert test_db_session.query(Task).filter(Task.id == task_id).one().status == "Completed"
    assert test_db_session.query(DiaryEntry).filter(
        DiaryEntry.id.in_([first_id, second_id])
    ).count() == 2


def test_legacy_migration_preserves_recordings_and_links_tasks():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE diary_days ("
            "id VARCHAR(36) PRIMARY KEY, entry_date DATE NOT NULL UNIQUE, "
            "recurring_topics_json TEXT NOT NULL, new_developments_json TEXT NOT NULL, "
            "completed_items_json TEXT NOT NULL, outstanding_items_json TEXT NOT NULL, "
            "analysis_task_ids_json TEXT NOT NULL, combined_summary_line_1 TEXT, "
            "combined_summary_line_2 TEXT, combined_summary_line_3 TEXT, "
            "analysis_updated_at DATETIME)"
        ))
        connection.execute(text(
            "CREATE TABLE diary_entries ("
            "id VARCHAR(36) PRIMARY KEY, entry_date DATE NOT NULL, "
            "original_transcript TEXT NOT NULL)"
        ))
        connection.execute(text(
            "CREATE TABLE tasks (id VARCHAR(36) PRIMARY KEY, diary_entry_id VARCHAR(36))"
        ))
        connection.execute(text(
            "INSERT INTO diary_entries VALUES ('entry-1', '2026-11-09', 'Keep this transcript')"
        ))
        connection.execute(text(
            "INSERT INTO tasks VALUES ('task-1', 'entry-1')"
        ))

    _migrate_diary_days(engine)
    _migrate_diary_days(engine)

    with engine.connect() as connection:
        entry = connection.execute(text(
            "SELECT original_transcript, diary_day_id FROM diary_entries "
            "WHERE id = 'entry-1'"
        )).one()
        task = connection.execute(text(
            "SELECT diary_day_id FROM tasks WHERE id = 'task-1'"
        )).one()
        assert entry.original_transcript == "Keep this transcript"
        assert entry.diary_day_id
        assert task.diary_day_id == entry.diary_day_id
        assert connection.execute(text(
            "SELECT COUNT(*) FROM diary_days WHERE entry_date = '2026-11-09'"
        )).scalar_one() == 1
    engine.dispose()


def test_combined_ollama_analysis_uses_each_recording(monkeypatch):
    service = OllamaService()
    prompts = []
    monkeypatch.setattr(
        service,
        "_call_ollama_generate",
        lambda prompt, _system: prompts.append(prompt) or json.dumps({
            "summary": ["Line one.", "Line two.", "Line three."],
            "recurring_topics": ["Work"],
            "new_developments": ["A decision was made."],
            "completed_items": ["Sent the application."],
            "outstanding_items": ["Call the team."],
            "tasks": [{
                "description": "Call the team",
                "due_date": None,
                "priority": "Medium",
            }],
        }),
    )

    result = service.analyze_combined_day(
        ["Earlier recording transcript.", "Later recording transcript."],
        "2026-11-09",
    )

    assert result.recurring_topics == ["Work"]
    assert len(result.tasks) == 1
    assert "Recording 1:" in prompts[0]
    assert "Recording 2:" in prompts[0]
    assert "2026-11-09" in prompts[0]
