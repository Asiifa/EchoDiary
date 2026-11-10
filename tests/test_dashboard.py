"""Tests for dashboard rendering from detached diary-entry data."""
import os
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
from sqlalchemy.orm import sessionmaker

import app.ui.dashboard as dashboard_module
from app.models.diary_entry import DiaryEntry
from app.models.task import Task
from app.ui.dashboard import DashboardView
from app.utils.date_utils import get_current_week_range, get_today_date


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Create the Qt application required by dashboard widgets."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _use_closing_test_sessions(monkeypatch, test_db_session):
    session_factory = sessionmaker(bind=test_db_session.get_bind(), expire_on_commit=True)
    closed_sessions = []

    @contextmanager
    def get_test_session():
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            closed_sessions.append(session)

    monkeypatch.setattr(dashboard_module, "get_db_session", get_test_session)
    return closed_sessions


def _label_texts(view):
    return [label.text() for label in view.findChildren(QLabel)]


def test_dashboard_without_entries(monkeypatch, test_db_session):
    closed_sessions = _use_closing_test_sessions(monkeypatch, test_db_session)

    view = DashboardView()
    texts = _label_texts(view)

    assert closed_sessions
    assert any("haven't recorded" in text for text in texts)
    assert any("No diary entries recorded yet." in text for text in texts)
    assert any("No entries in the past 7 days." in text for text in texts)
    view.close()


def test_dashboard_today_card_renders_after_session_closes(
    monkeypatch, test_db_session
):
    today = get_today_date()
    entry = DiaryEntry(
        entry_date=today,
        created_at=datetime.combine(today, datetime.min.time()),
        original_transcript="A productive day.",
        summary_line_1="Finished the project.",
        summary_line_2="Went for a walk.",
        primary_mood="Calm",
    )
    entry.tasks.append(Task(description="Prepare tomorrow's notes"))
    test_db_session.add(entry)
    test_db_session.commit()
    entry_id = entry.id

    closed_sessions = _use_closing_test_sessions(monkeypatch, test_db_session)
    view = DashboardView()
    texts = _label_texts(view)

    assert closed_sessions
    assert any("Today's Diary Entry Recorded" in text for text in texts)
    assert "Finished the project." in texts
    assert any("Calm" in text for text in texts)

    requested_ids = []
    view.view_entry_requested.connect(requested_ids.append)
    next(
        button
        for button in view.findChildren(QPushButton)
        if button.text() == "View Entry"
    ).click()
    assert requested_ids == [entry_id]
    view.close()


def test_dashboard_latest_entry_and_weekly_mood_overview(
    monkeypatch, test_db_session
):
    week_start, week_end = get_current_week_range(get_today_date())
    entries = [
        DiaryEntry(
            entry_date=week_start + timedelta(days=day_offset),
            created_at=datetime.combine(
                week_start + timedelta(days=day_offset), datetime.min.time()
            ),
            original_transcript=f"Reflection {day_offset}",
            summary_line_1=f"Summary {day_offset}",
            primary_mood=mood,
        )
        for day_offset, mood in ((0, "Calm"), (2, "Calm"), (5, "Happy"))
        if week_start + timedelta(days=day_offset) <= week_end
    ]
    test_db_session.add_all(entries)
    test_db_session.commit()

    closed_sessions = _use_closing_test_sessions(monkeypatch, test_db_session)
    view = DashboardView()
    texts = _label_texts(view)

    assert closed_sessions
    assert any("Summary 5" in text for text in texts)
    assert "2 days" in texts
    assert "1 day" in texts
    assert any("Calm" in text for text in texts)
    assert any("Happy" in text for text in texts)
    view.close()


def test_dashboard_handles_nullable_mood_and_summary(
    monkeypatch, test_db_session
):
    today = get_today_date()
    test_db_session.add(
        DiaryEntry(
            entry_date=today,
            created_at=datetime.combine(today, datetime.min.time()),
            original_transcript="",
            summary_line_1=None,
            summary_line_2=None,
            summary_line_3=None,
            primary_mood=None,
        )
    )
    test_db_session.commit()

    closed_sessions = _use_closing_test_sessions(monkeypatch, test_db_session)
    view = DashboardView()
    texts = _label_texts(view)

    assert closed_sessions
    assert "Reflections captured for today." in texts
    assert "No summary available." in texts
    assert any("Neutral" in text for text in texts)
    view.close()
