"""Regression tests for detached task data and diary detail widgets."""
import os
from contextlib import contextmanager
from datetime import date, datetime

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QLabel, QSlider, QTextEdit, QScrollArea
)
from sqlalchemy.orm import sessionmaker

import app.ui.diary_view as diary_view_module
import app.ui.dashboard as dashboard_view_module
import app.ui.todo_view as todo_view_module
from app.models.diary_entry import DiaryEntry
from app.models.diary_day import DiaryDay
from app.models.task import Task
from app.models.weekly_report import WeeklyReport
from app.ui.diary_view import DiaryView
from app.ui.dashboard import DashboardView
from app.ui.todo_view import TaskItemWidget, TodoView
import app.ui.weekly_view as weekly_view_module
from app.ui.weekly_view import WeeklyView
import app.ui.settings_view as settings_view_module
import app.ui.main_window as main_window_module
from app.ui.main_window import MainWindow
from app.utils.date_utils import get_current_week_range, get_today_date
from app.ui.styles import LIGHT_THEME_QSS


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Create the Qt application required by the widget tests."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _use_closing_test_sessions(monkeypatch, test_db_session, module):
    session_factory = sessionmaker(
        bind=test_db_session.get_bind(), expire_on_commit=True
    )
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

    monkeypatch.setattr(module, "get_db_session", get_test_session)
    return closed_sessions


def test_todo_view_renders_detached_tasks_and_toggles_completion(
    monkeypatch, test_db_session
):
    diary_entry = DiaryEntry(
        entry_date=date(2026, 11, 9),
        original_transcript="Task-related reflection",
    )
    pending_task = Task(
        diary_entry=diary_entry,
        description="Finish the report",
        due_date=date(2026, 11, 12),
        priority="High",
        status="Pending",
    )
    completed_task = Task(
        description="Book the appointment",
        priority="Low",
        status="Completed",
    )
    test_db_session.add_all([diary_entry, pending_task, completed_task])
    test_db_session.commit()
    pending_id = pending_task.id
    completed_id = completed_task.id
    diary_entry_id = diary_entry.id

    closed_sessions = _use_closing_test_sessions(
        monkeypatch, test_db_session, todo_view_module
    )
    view = TodoView()
    view.resize(880, 620)
    view.show()
    QApplication.instance().processEvents()

    assert closed_sessions
    assert view.tasks_list.count() == 1
    item = view.tasks_list.item(0)
    widget = view.tasks_list.itemWidget(item)
    assert isinstance(widget, TaskItemWidget)
    assert widget.width() <= view.tasks_list.viewport().width()
    assert widget.task_id == pending_id
    assert widget.diary_entry_id == diary_entry_id
    assert widget.chk_status.isChecked() is False
    assert any(
        label.text() == "Finish the report"
        for label in widget.findChildren(QLabel)
    )
    assert any(
        "Due: 2026-11-12" in label.text()
        for label in widget.findChildren(QLabel)
    )

    widget.chk_status.click()
    assert view.tasks_list.count() == 1
    empty_state = view.tasks_list.itemWidget(view.tasks_list.item(0))
    assert isinstance(empty_state, QLabel)
    assert "No pending tasks found." in empty_state.text()

    with sessionmaker(bind=test_db_session.get_bind())() as session:
        assert session.query(Task).filter_by(id=pending_id).one().status == "Completed"

    view.status_combo.setCurrentText("Completed")
    assert view.tasks_list.count() == 2
    completed_widgets = [
        view.tasks_list.itemWidget(view.tasks_list.item(index))
        for index in range(view.tasks_list.count())
    ]
    assert all(widget.chk_status.isChecked() for widget in completed_widgets)
    assert any(widget.task_id == completed_id for widget in completed_widgets)
    view.close()


def test_diary_detail_creates_audio_slider(
    monkeypatch, test_db_session, tmp_path
):
    audio_file = tmp_path / "entry.wav"
    audio_file.write_bytes(b"test audio placeholder")
    entry = DiaryEntry(
        entry_date=date(2026, 11, 9),
        created_at=datetime(2026, 11, 9),
        original_transcript="A diary reflection",
        audio_file_path=str(audio_file),
    )
    test_db_session.add(entry)
    test_db_session.commit()
    entry_id = entry.id

    closed_sessions = _use_closing_test_sessions(
        monkeypatch, test_db_session, diary_view_module
    )
    view = DiaryView()
    view._load_entry_detail(entry_id)

    assert closed_sessions
    assert isinstance(view.detail_slider, QSlider)
    assert view.detail_slider.minimum() == 0
    assert view.detail_slider.maximum() == 1000
    view.close()


def test_diary_list_selection_and_task_toggle_use_session_snapshots(
    monkeypatch, test_db_session
):
    diary_entry = DiaryEntry(
        entry_date=date(2026, 11, 9),
        original_transcript="A detailed diary reflection",
        summary_line_1="A useful summary",
        primary_mood=None,
    )
    task = Task(
        diary_entry=diary_entry,
        description="Review the notes",
        priority="Medium",
        status="Pending",
    )
    test_db_session.add_all([diary_entry, task])
    test_db_session.commit()
    entry_id = diary_entry.id
    task_id = task.id

    closed_sessions = _use_closing_test_sessions(
        monkeypatch, test_db_session, diary_view_module
    )
    view = DiaryView()

    assert closed_sessions
    assert view.entries_list.topLevelItemCount() == 1
    assert view.entries_list.topLevelItem(0).childCount() == 1
    view.select_entry(entry_id)
    assert view.entries_list.currentItem().data(0, Qt.UserRole)["entry_id"] == entry_id
    labels = [label.text() for label in view.findChildren(QLabel)]
    assert any("A useful summary" in label for label in labels)
    assert any("Neutral" in text for text in labels)

    task_checkbox = next(
        checkbox for checkbox in view.findChildren(QCheckBox)
        if checkbox.text() == "Review the notes"
    )
    assert not task_checkbox.isChecked()
    task_checkbox.click()
    refreshed_checkbox = next(
        checkbox for checkbox in view.findChildren(QCheckBox)
        if checkbox.text() == "Review the notes"
    )
    assert refreshed_checkbox.isChecked()

    with sessionmaker(bind=test_db_session.get_bind())() as session:
        assert session.query(Task).filter_by(id=task_id).one().status == "Completed"
    view.close()


def test_weekly_view_converts_cached_report_before_session_closes(
    monkeypatch, test_db_session
):
    start_date, end_date = get_current_week_range(get_today_date())
    report = WeeklyReport(
        start_date=start_date,
        end_date=end_date,
        overview="A calm and productive week.",
        highlights_json='["Completed a project"]',
        mood_distribution_json='{"Calm": 2}',
        mood_trends_json='[{"date": "2026-11-09", "mood": "Calm", "confidence": 0.8}]',
        entries_count=2,
    )
    test_db_session.add(report)
    test_db_session.commit()

    closed_sessions = _use_closing_test_sessions(
        monkeypatch, test_db_session, weekly_view_module
    )
    view = WeeklyView()

    assert closed_sessions
    assert view.current_report_data["overview"] == "A calm and productive week."
    assert view.current_report_data["highlights"] == ["Completed a project"]
    assert view.current_report_data["mood_distribution"] == {"Calm": 2}
    view.close()


def test_diary_layout_handles_empty_long_entries_and_resizing(
    monkeypatch, test_db_session,
):
    _use_closing_test_sessions(
        monkeypatch, test_db_session, diary_view_module
    )
    view = DiaryView()
    view.setStyleSheet(LIGHT_THEME_QSS)
    view.resize(1220, 840)
    view.show()
    QApplication.instance().processEvents()

    assert view.entries_list.topLevelItemCount() == 0
    assert view.detail_scroll.widgetResizable()

    long_summary = "Detailed reflection and progress. " * 35
    long_transcript = "A longer spoken reflection with many details. " * 80
    older_entry = DiaryEntry(
        entry_date=date(2026, 11, 8),
        original_transcript="Older entry transcript for selection testing.",
        summary_line_1="Older summary",
        primary_mood="Happy",
    )
    newest_entry = DiaryEntry(
        entry_date=date(2026, 11, 9),
        original_transcript=long_transcript,
        summary_line_1=long_summary,
        primary_mood="Calm",
    )
    test_db_session.add_all([older_entry, newest_entry])
    test_db_session.commit()
    older_id = older_entry.id

    view.refresh_entries()
    QApplication.instance().processEvents()
    assert view.entries_list.topLevelItemCount() == 2
    newest_day = view.entries_list.topLevelItem(0)
    assert newest_day.data(0, Qt.UserRole)["entry_date"] == "2026-11-09"

    card = view.entries_list.itemWidget(newest_day, 0)
    assert card is not None
    assert card.height() > 60
    assert card.width() <= view.entries_list.viewport().width()
    card_labels = [label for label in card.findChildren(QLabel)]
    card_text = " ".join(label.text() for label in card_labels)
    assert "Monday, Nov 09, 2026" in card_text
    assert "1 recording" in card_text
    assert newest_day.childCount() == 1
    recording_card = view.entries_list.itemWidget(newest_day.child(0), 0)
    assert recording_card is not None
    assert recording_card.width() <= view.entries_list.viewport().width()
    recording_text = " ".join(
        label.text() for label in recording_card.findChildren(QLabel)
    )
    assert "Calm" in recording_text
    assert "Duration" in recording_text

    view.select_entry(older_id)
    QApplication.instance().processEvents()
    assert any(
        "Older entry transcript" in text
        for edit in view.findChildren(QTextEdit)
        for text in [edit.toPlainText()]
    )

    for width, height in ((960, 640), (1220, 840)):
        view.resize(width, height)
        QApplication.instance().processEvents()
        list_width, detail_width = view.splitter.sizes()
        assert detail_width > list_width
        assert view.detail_scroll.viewport().width() >= 320
        assert view.entries_list.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
        assert view.detail_scroll.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
        assert view.entries_list.itemWidget(
            view.entries_list.topLevelItem(0), 0
        ).width() <= view.entries_list.viewport().width()
    view.close()


def test_diary_groups_same_date_and_shows_all_recordings_in_order(
    monkeypatch, test_db_session
):
    entry_date = date(2026, 11, 9)
    day = DiaryDay(
        entry_date=entry_date,
        combined_summary_line_1="The day moved forward.",
        combined_summary_line_2="A recurring project topic came up.",
        combined_summary_line_3="One task remains outstanding.",
        recurring_topics_json='["Project"]',
        outstanding_items_json='["Send the final notes"]',
    )
    morning = DiaryEntry(
        entry_date=entry_date,
        diary_day=day,
        created_at=datetime(2026, 11, 9, 9, 15),
        original_transcript="Morning recording transcript.",
        summary_line_1="Completed the first project step.",
        primary_mood="Calm",
        duration_seconds=74.5,
    )
    afternoon = DiaryEntry(
        entry_date=entry_date,
        diary_day=day,
        created_at=datetime(2026, 11, 9, 16, 45),
        original_transcript="Afternoon recording transcript.",
        summary_line_1="The second step is still open.",
        primary_mood="Happy",
        duration_seconds=125.0,
    )
    test_db_session.add_all([day, morning, afternoon])
    test_db_session.commit()
    afternoon_id = afternoon.id

    _use_closing_test_sessions(monkeypatch, test_db_session, diary_view_module)
    view = DiaryView()

    assert view.entries_list.topLevelItemCount() == 1
    day_item = view.entries_list.topLevelItem(0)
    assert day_item.childCount() == 2
    assert view.selected_day_date == entry_date
    displayed_text = " ".join(
        label.text() for label in view.findChildren(QLabel)
    )
    assert "Monday, Nov 09, 2026" in displayed_text
    assert "2 recordings" in displayed_text
    assert "The day moved forward." in displayed_text
    assert "Morning recording transcript." in " ".join(
        edit.toPlainText() for edit in view.findChildren(QTextEdit)
    )
    assert "Afternoon recording transcript." in " ".join(
        edit.toPlainText() for edit in view.findChildren(QTextEdit)
    )
    recording_times = [
        " ".join(
            label.text()
            for label in view.entries_list.itemWidget(
                day_item.child(index), 0
            ).findChildren(QLabel)
        )
        for index in range(day_item.childCount())
    ]
    assert diary_view_module._format_recording_time(
        datetime(2026, 11, 9, 9, 15)
    ) in recording_times[0]
    assert diary_view_module._format_recording_time(
        datetime(2026, 11, 9, 16, 45)
    ) in recording_times[1]
    assert "Recording duration" in displayed_text

    view.select_entry(afternoon_id)
    assert view.selected_entry_id == afternoon_id
    assert "Afternoon recording transcript." in " ".join(
        edit.toPlainText() for edit in view.findChildren(QTextEdit)
    )
    assert any(
        "INDIVIDUAL RECORDING ANALYSIS" in label.text()
        for label in view.findChildren(QLabel)
    )
    view.close()


def test_dashboard_reflows_cards_at_narrow_and_wide_sizes(
    monkeypatch, test_db_session
):
    _use_closing_test_sessions(
        monkeypatch, test_db_session, dashboard_view_module
    )
    view = DashboardView()
    view.resize(820, 680)
    view.show()
    QApplication.instance().processEvents()

    assert sorted(
        view.stats_grid.getItemPosition(index)[0]
        for index in range(view.stats_grid.count())
    ) == [0, 0, 1, 1]
    assert sorted(
        view.middle_layout.getItemPosition(index)[0]
        for index in range(view.middle_layout.count())
    ) == [0, 1]

    view.resize(1120, 760)
    QApplication.instance().processEvents()
    assert all(
        view.stats_grid.getItemPosition(index)[0] == 0
        for index in range(view.stats_grid.count())
    )
    assert all(
        view.middle_layout.getItemPosition(index)[0] == 0
        for index in range(view.middle_layout.count())
    )
    assert view.card_total.isVisible()
    assert view.card_week.isVisible()
    assert view.card_pending.isVisible()
    assert view.card_completed.isVisible()
    view.close()


def test_all_screens_fit_small_and_large_windows(
    monkeypatch, test_db_session
):
    for module in (
        dashboard_view_module,
        diary_view_module,
        todo_view_module,
        weekly_view_module,
    ):
        _use_closing_test_sessions(monkeypatch, test_db_session, module)

    monkeypatch.setattr(
        settings_view_module.SettingsView,
        "check_ollama_status",
        lambda self: None,
    )
    monkeypatch.setattr(
        settings_view_module.SettingsView,
        "refresh_backups",
        lambda self: None,
    )
    monkeypatch.setattr(
        main_window_module.OllamaService,
        "check_connection",
        lambda self: (False, "not available", []),
    )
    window = MainWindow()

    for width, height, expected_page_width in (
        (880, 620, 656),
        (900, 640, 676),
        (1220, 840, 996),
    ):
        window.resize(width, height)
        window.show()
        QApplication.instance().processEvents()
        for page_key, (page_index, _) in window.view_indices.items():
            window.navigate_to(page_key)
            QApplication.instance().processEvents()
            view = window.stack.widget(page_index)
            assert view.width() == expected_page_width
            assert all(
                area.horizontalScrollBar().maximum() == 0
                for area in view.findChildren(QScrollArea)
            )

        assert window.view_diary.detail_scroll.viewport().width() >= 300
        assert window.view_recorder._device_tools_columns == (
            4 if width > 1000 else 2
        )
        assert window.view_recorder._record_controls_columns == (
            4 if width > 1000 else 1
        )
        assert window.view_weekly._chart_columns == (
            2 if width > 1000 else 1
        )

    window.close()
