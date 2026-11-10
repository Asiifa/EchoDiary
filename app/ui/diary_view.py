"""My Diary management view: list, search, filter, detailed view, playback, and entry editing."""
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTreeWidget, QTreeWidgetItem,
    QSplitter, QFrame, QScrollArea, QMessageBox, QTabWidget,
    QTextEdit, QCheckBox, QDialog, QDialogButtonBox, QSlider, QSizePolicy
)
from PySide6.QtCore import Qt, QSize, QTimer
from sqlalchemy import desc

from app.database import get_db_session
from app.models.diary_entry import DiaryEntry
from app.models.diary_day import DiaryDay
from app.models.task import Task
from app.schemas.entry_dto import DiaryEntryDTO
from app.services.audio_player import AudioPlayer
from app.services.export_service import ExportService
from app.services.task_service import TaskService
from app.ui.components.mood_badge import MoodBadge
from app.ui.styles import PRIORITY_STYLES
from app.utils.date_utils import format_display_date
from app.config import Config


def _format_recording_time(value: Optional[datetime]) -> str:
    if value is None:
        return "Time unavailable"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%I:%M %p")


class DiaryDayListItem(QWidget):
    """Date group card in the diary navigation tree."""

    def __init__(
        self,
        entry_date: date,
        recording_count: int,
        summary_snippet: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("DiaryDayListItem")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(78)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        date_lbl = QLabel(format_display_date(entry_date))
        date_lbl.setStyleSheet("font-weight: 700; font-size: 13px; color: #252833;")
        date_lbl.setWordWrap(True)
        title_row.addWidget(date_lbl, stretch=1)
        count_lbl = QLabel(
            f"{recording_count} recording" + ("" if recording_count == 1 else "s")
        )
        count_lbl.setStyleSheet(
            "background: #EFECF3; color: #344C59; font-size: 11px; "
            "font-weight: 600; padding: 4px 8px; border-radius: 8px;"
        )
        count_lbl.setMinimumHeight(24)
        title_row.addWidget(count_lbl, alignment=Qt.AlignTop)
        layout.addLayout(title_row)

        summary_text = summary_snippet or "Select to review this day's recordings."
        summary_preview = summary_text if len(summary_text) <= 92 else summary_text[:89].rstrip() + "..."
        summary_label = QLabel(summary_preview)
        summary_label.setToolTip(summary_text)
        summary_label.setStyleSheet("color: #777985; font-size: 11px;")
        summary_label.setWordWrap(True)
        summary_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(summary_label)

class DiaryRecordingListItem(QWidget):
    """Chronological recording row nested under a date."""

    def __init__(self, created_at: Optional[datetime], mood: str, duration: float, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(50)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 7, 8, 7)
        layout.setSpacing(4)

        time_value = _format_recording_time(created_at)
        top_row = QHBoxLayout()
        time_label = QLabel(time_value)
        time_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #344C59;")
        top_row.addWidget(time_label)
        top_row.addStretch()
        top_row.addWidget(MoodBadge(mood or "Neutral"))
        layout.addLayout(top_row)

        duration_frame = QFrame()
        duration_frame.setStyleSheet(
            "background: #F5F3EF; border: 1px solid #E5E2DE; border-radius: 6px;"
        )
        duration_layout = QHBoxLayout(duration_frame)
        duration_layout.setContentsMargins(8, 3, 8, 3)
        duration_layout.setSpacing(6)
        duration_label = QLabel("Duration")
        duration_label.setStyleSheet("font-size: 10px; color: #777985;")
        duration_value = QLabel(f"{round(duration, 1)} sec")
        duration_value.setMinimumWidth(56)
        duration_value.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #344C59;"
        )
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(duration_value)
        duration_layout.addStretch()
        layout.addWidget(duration_frame)


class EditEntryDialog(QDialog):
    """Dialog to edit diary entry transcript and notes."""

    def __init__(self, entry: DiaryEntryDTO, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Diary Entry")
        self.resize(600, 480)
        self.entry_id = entry.id

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        info_lbl = QLabel(f"Editing entry for: {format_display_date(entry.entry_date)}")
        info_lbl.setStyleSheet("font-weight: 700; font-size: 14px; color: #252833;")
        layout.addWidget(info_lbl)

        trans_lbl = QLabel("Transcript Content:")
        trans_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        layout.addWidget(trans_lbl)

        self.edit_text = QTextEdit()
        self.edit_text.setText(entry.effective_transcript)
        layout.addWidget(self.edit_text)

        mood_row = QHBoxLayout()
        mood_lbl = QLabel("Primary Mood:")
        mood_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        self.mood_combo = QComboBox()
        self.mood_combo.addItems(Config.SUPPORTED_MOODS)
        if entry.primary_mood in Config.SUPPORTED_MOODS:
            self.mood_combo.setCurrentText(entry.primary_mood)
        mood_row.addWidget(mood_lbl)
        mood_row.addWidget(self.mood_combo)
        mood_row.addStretch()
        layout.addLayout(mood_row)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self):
        return {
            "transcript": self.edit_text.toPlainText().strip(),
            "mood": self.mood_combo.currentText(),
        }


class DiaryView(QWidget):
    """Section for browsing, searching, listening, and managing personal diary entries."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_entry_id: Optional[str] = None
        self.selected_day_date: Optional[date] = None
        self.player = AudioPlayer(
            position_callback=self._on_player_position,
            finished_callback=self._on_player_finished,
        )
        self._init_ui()
        self.refresh_entries()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 28)
        main_layout.setSpacing(18)

        # Header with Search & Filter
        header_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("My Diary")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #252833;")
        sub = QLabel("Explore your voice journal entries, summaries, and extracted tasks.")
        sub.setStyleSheet("font-size: 13px; color: #777985;")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        header_row.addLayout(title_box)
        header_row.addStretch()
        main_layout.addLayout(header_row)

        # Filter bar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search transcripts, summaries, or topics...")
        self.search_input.textChanged.connect(self._apply_filters)
        self.search_input.setMinimumWidth(180)
        filter_bar.addWidget(self.search_input)

        mood_filter_lbl = QLabel("Mood:")
        mood_filter_lbl.setStyleSheet("color: #344C59; font-weight: 600;")
        self.mood_filter = QComboBox()
        self.mood_filter.addItem("All Moods")
        self.mood_filter.addItems(Config.SUPPORTED_MOODS)
        self.mood_filter.currentIndexChanged.connect(self._apply_filters)
        filter_bar.addWidget(mood_filter_lbl)
        filter_bar.addWidget(self.mood_filter)

        self.btn_clear_filters = QPushButton("Clear Filters")
        self.btn_clear_filters.setObjectName("SecondaryButton")
        self.btn_clear_filters.clicked.connect(self._clear_filters)
        filter_bar.addWidget(self.btn_clear_filters)
        filter_bar.addStretch()

        main_layout.addLayout(filter_bar)

        # Splitter: List on Left, Detail Panel on Right
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(8)
        self.splitter.setMinimumWidth(0)

        # Left Column: Entries List
        list_container = QFrame()
        list_container.setMinimumWidth(215)
        list_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        list_container.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E5E2DE; border-radius: 12px; padding: 6px;")
        l_layout = QVBoxLayout(list_container)
        l_layout.setContentsMargins(4, 4, 4, 4)

        self.entries_list = QTreeWidget()
        self.entries_list.setFrameShape(QFrame.NoFrame)
        self.entries_list.setHeaderHidden(True)
        self.entries_list.setIndentation(12)
        self.entries_list.setAnimated(False)
        self.entries_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.entries_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.entries_list.itemSelectionChanged.connect(self._on_entry_selected)
        l_layout.addWidget(self.entries_list)
        self.splitter.addWidget(list_container)

        # Right Column: Detail Panel
        detail_scroll = QScrollArea()
        self.detail_scroll = detail_scroll
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFrameShape(QFrame.NoFrame)
        detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        detail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        detail_scroll.setMinimumWidth(300)
        detail_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.detail_container = QWidget()
        self.detail_container.setObjectName("DiaryDetailContent")
        self.detail_container.setMinimumWidth(0)
        self.detail_container.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.detail_layout = QVBoxLayout(self.detail_container)
        self.detail_layout.setContentsMargins(18, 12, 18, 12)
        self.detail_layout.setSpacing(16)
        self.detail_layout.setAlignment(Qt.AlignTop)
        detail_scroll.setWidget(self.detail_container)

        self.splitter.addWidget(detail_scroll)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes([360, 720])

        main_layout.addWidget(self.splitter, stretch=1)

    def refresh_entries(self):
        """Reload entries from database with current search and mood filters."""
        self._apply_filters()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._resize_entry_cards)

    def _resize_entry_cards(self):
        viewport_width = self.entries_list.viewport().width()
        for day_index in range(self.entries_list.topLevelItemCount()):
            day_item = self.entries_list.topLevelItem(day_index)
            for item in [day_item] + [
                day_item.child(index) for index in range(day_item.childCount())
            ]:
                card = self.entries_list.itemWidget(item, 0)
                if card is not None:
                    card.setMaximumWidth(viewport_width)
                    card.updateGeometry()
                    item.setSizeHint(0, QSize(viewport_width, card.sizeHint().height()))

    def select_entry(self, entry_id: str):
        """Programmatically select and display an entry by ID."""
        self.selected_entry_id = entry_id
        for day_index in range(self.entries_list.topLevelItemCount()):
            day_item = self.entries_list.topLevelItem(day_index)
            for recording_index in range(day_item.childCount()):
                item = day_item.child(recording_index)
                item_data = item.data(0, Qt.UserRole) or {}
                if item_data.get("entry_id") == entry_id:
                    day_item.setExpanded(True)
                    self.entries_list.setCurrentItem(item)
                    return

    def _clear_filters(self):
        self.search_input.clear()
        self.mood_filter.setCurrentIndex(0)
        self._apply_filters()

    def _apply_filters(self):
        search_text = self.search_input.text().strip().lower()
        selected_mood = self.mood_filter.currentText()

        self.entries_list.clear()

        grouped_rows = {}
        with get_db_session() as session:
            query = session.query(DiaryEntry).filter(DiaryEntry.is_deleted == False)

            if selected_mood != "All Moods":
                query = query.filter(DiaryEntry.primary_mood == selected_mood)

            entries = query.order_by(
                desc(DiaryEntry.entry_date), DiaryEntry.created_at.asc(), DiaryEntry.id.asc()
            ).all()

            for entry in entries:
                # Text search match check across transcripts, summary lines, and topics
                if search_text:
                    full_content = (
                        (entry.original_transcript or "") + " " +
                        (entry.edited_transcript or "") + " " +
                        " ".join(entry.summary_lines or []) + " " +
                        " ".join(entry.topics or [])
                    ).lower()
                    if entry.diary_day is not None:
                        day_analysis = (
                            " ".join(entry.diary_day.combined_summary_lines) + " " +
                            " ".join(entry.diary_day.get_list("recurring_topics")) + " " +
                            " ".join(entry.diary_day.get_list("new_developments")) + " " +
                            " ".join(entry.diary_day.get_list("outstanding_items"))
                        ).lower()
                        full_content += " " + day_analysis
                    if search_text not in full_content:
                        continue

                row = {
                    "id": entry.id,
                    "entry_date": entry.entry_date,
                    "created_at": entry.created_at,
                    "primary_mood": entry.primary_mood,
                    "summary": " ".join(entry.summary_lines or []),
                    "transcript": entry.effective_transcript or "",
                    "duration": entry.duration_seconds,
                }
                grouped_rows.setdefault(entry.entry_date, []).append(row)

        for entry_date in sorted(grouped_rows, reverse=True):
            recordings = grouped_rows[entry_date]
            day_item = QTreeWidgetItem(self.entries_list)
            day_item.setData(0, Qt.UserRole, {
                "type": "day",
                "entry_date": entry_date.isoformat(),
            })
            summary_snippet = next(
                (record["summary"] for record in recordings if record["summary"]),
                "",
            )
            day_widget = DiaryDayListItem(
                entry_date=entry_date,
                recording_count=len(recordings),
                summary_snippet=summary_snippet,
            )
            day_item.setSizeHint(0, QSize(0, day_widget.sizeHint().height()))
            self.entries_list.setItemWidget(day_item, 0, day_widget)

            for recording in recordings:
                item = QTreeWidgetItem(day_item)
                item.setData(0, Qt.UserRole, {
                    "type": "entry",
                    "entry_id": recording["id"],
                })
                transcript = recording["transcript"] or "No transcript recorded."
                summary = recording["summary"] or "No individual analysis available."
                item.setToolTip(
                    0, f"{summary}\n\nTranscript: {transcript}"
                )
                recording_widget = DiaryRecordingListItem(
                    created_at=recording["created_at"],
                    mood=recording["primary_mood"],
                    duration=recording["duration"],
                )
                item.setSizeHint(
                    0, QSize(0, recording_widget.sizeHint().height())
                )
                self.entries_list.setItemWidget(item, 0, recording_widget)
            day_item.setExpanded(True)

        if self.entries_list.topLevelItemCount() > 0:
            if self.selected_entry_id:
                self.select_entry(self.selected_entry_id)
            elif self.selected_day_date:
                self._select_day(self.selected_day_date)
            else:
                self.entries_list.setCurrentItem(self.entries_list.topLevelItem(0))
        else:
            self._show_empty_detail()

    def _select_day(self, entry_date: date) -> None:
        for index in range(self.entries_list.topLevelItemCount()):
            item = self.entries_list.topLevelItem(index)
            data = item.data(0, Qt.UserRole) or {}
            if data.get("entry_date") == entry_date.isoformat():
                self.entries_list.setCurrentItem(item)
                return

    def _on_entry_selected(self):
        selected_items = self.entries_list.selectedItems()
        if not selected_items:
            self._show_empty_detail()
            return

        item_data = selected_items[0].data(0, Qt.UserRole) or {}
        if item_data.get("type") == "entry":
            entry_id = item_data["entry_id"]
            self.selected_entry_id = entry_id
            self.selected_day_date = None
            self._load_entry_detail(entry_id)
        else:
            entry_date = date.fromisoformat(item_data["entry_date"])
            self.selected_entry_id = None
            self.selected_day_date = entry_date
            self._load_day_detail(entry_date)

    def _show_empty_detail(self):
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lbl = QLabel("Select an entry from the list to view its audio, summary, and extracted tasks.")
        lbl.setStyleSheet("color: #96979E; font-size: 14px; padding: 48px;")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.detail_layout.addWidget(lbl)

    def _load_day_detail(self, entry_date: date) -> None:
        self.player.stop()
        self._active_play_button = None
        self.detail_slider = None
        self.lbl_detail_time = None
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        with get_db_session() as session:
            day = session.query(DiaryDay).filter(
                DiaryDay.entry_date == entry_date
            ).first()
            recordings = (
                session.query(DiaryEntry)
                .filter(
                    DiaryEntry.entry_date == entry_date,
                    DiaryEntry.is_deleted == False,
                )
                .order_by(DiaryEntry.created_at.asc(), DiaryEntry.id.asc())
                .all()
            )
            day_data = None
            if day is not None:
                task_ids = day.analysis_task_ids
                day_data = {
                    "summary": day.combined_summary_lines,
                    "recurring_topics": day.get_list("recurring_topics"),
                    "new_developments": day.get_list("new_developments"),
                    "completed_items": day.get_list("completed_items"),
                    "outstanding_items": day.get_list("outstanding_items"),
                    "tasks": [
                        {
                            "id": task.id,
                            "description": task.description,
                            "due_date": task.due_date,
                            "priority": task.priority,
                            "status": task.status,
                        }
                        for task in session.query(Task)
                        .filter(Task.id.in_(task_ids))
                        .all()
                    ] if task_ids else [],
                    "analysis_updated_at": day.analysis_updated_at,
                }

            recording_data = [
                {
                    "id": entry.id,
                    "created_at": entry.created_at,
                    "audio_file_path": entry.audio_file_path,
                    "duration_seconds": entry.duration_seconds or 0.0,
                    "primary_mood": entry.primary_mood or "Neutral",
                    "summary": entry.summary_lines,
                    "topics": entry.topics,
                    "transcript": entry.effective_transcript,
                }
                for entry in recordings
            ]

        date_card = QFrame()
        date_card.setStyleSheet(
            "background: #FFFFFF; border: 1px solid #E5E2DE; "
            "border-radius: 12px; padding: 18px;"
        )
        date_layout = QVBoxLayout(date_card)
        date_title = QLabel(format_display_date(entry_date))
        date_title.setStyleSheet(
            "font-size: 20px; font-weight: 700; color: #252833;"
        )
        date_title.setWordWrap(True)
        date_layout.addWidget(date_title)
        count_label = QLabel(
            f"{len(recording_data)} recording" + (
                "" if len(recording_data) == 1 else "s"
            )
        )
        count_label.setStyleSheet(
            "font-size: 12px; color: #344C59; font-weight: 600;"
        )
        date_layout.addWidget(count_label)
        self.detail_layout.addWidget(date_card)

        combined_card = QFrame()
        combined_card.setStyleSheet(
            "background: #FFFFFF; border: 1px solid #E5E2DE; "
            "border-radius: 12px; padding: 18px;"
        )
        combined_layout = QVBoxLayout(combined_card)
        combined_layout.setSpacing(9)
        combined_title = QLabel("COMBINED DAILY ANALYSIS")
        combined_title.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #777985; "
            "letter-spacing: 0.5px;"
        )
        combined_layout.addWidget(combined_title)
        if day_data and day_data["summary"]:
            for line in day_data["summary"]:
                summary_label = QLabel(f"• {line}")
                summary_label.setStyleSheet("font-size: 13px; color: #252833;")
                summary_label.setWordWrap(True)
                combined_layout.addWidget(summary_label)
        else:
            pending_label = QLabel(
                "Combined analysis will appear after the recordings for this date "
                "have been analyzed."
            )
            pending_label.setStyleSheet("font-size: 12px; color: #777985;")
            pending_label.setWordWrap(True)
            combined_layout.addWidget(pending_label)
        if day_data and day_data["analysis_updated_at"]:
            updated_label = QLabel(
                "Updated " + day_data["analysis_updated_at"].strftime("%I:%M %p")
            )
            updated_label.setStyleSheet("font-size: 10px; color: #96979E;")
            combined_layout.addWidget(updated_label)

        for label, key in (
            ("Recurring topics", "recurring_topics"),
            ("New developments", "new_developments"),
            ("Completed", "completed_items"),
            ("Outstanding", "outstanding_items"),
        ):
            values = day_data[key] if day_data else []
            if values:
                detail_label = QLabel(f"<b>{label}:</b> " + "; ".join(values))
                detail_label.setStyleSheet("font-size: 12px; color: #344C59;")
                detail_label.setWordWrap(True)
                combined_layout.addWidget(detail_label)
        self.detail_layout.addWidget(combined_card)

        daily_tasks_card = QFrame()
        daily_tasks_card.setStyleSheet(
            "background: #FFFFFF; border: 1px solid #E5E2DE; "
            "border-radius: 12px; padding: 18px;"
        )
        daily_tasks_layout = QVBoxLayout(daily_tasks_card)
        daily_tasks_layout.setSpacing(8)
        daily_tasks_title = QLabel("TOP ACTIONABLE TASKS FOR THIS DAY")
        daily_tasks_title.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #777985; "
            "letter-spacing: 0.5px;"
        )
        daily_tasks_layout.addWidget(daily_tasks_title)
        daily_tasks = day_data["tasks"] if day_data else []
        if daily_tasks:
            for task in daily_tasks:
                task_row = QHBoxLayout()
                checkbox = QCheckBox(task["description"])
                checkbox.setChecked(task["status"] == "Completed")
                checkbox.setStyleSheet(
                    "font-size: 13px; color: "
                    + ("#96979E; text-decoration: line-through;" if task["status"] == "Completed" else "#252833;")
                )
                checkbox.stateChanged.connect(
                    lambda _state, task_id=task["id"]:
                    self._toggle_task_from_diary(task_id)
                )
                task_row.addWidget(checkbox, stretch=1)
                if task["due_date"]:
                    due_label = QLabel(f"Due: {task['due_date']}")
                    due_label.setStyleSheet(
                        "font-size: 11px; color: #8F6740; font-weight: 600;"
                    )
                    task_row.addWidget(due_label)
                daily_tasks_layout.addLayout(task_row)
        else:
            no_tasks = QLabel("No combined actionable tasks are available yet.")
            no_tasks.setStyleSheet("font-size: 12px; color: #96979E;")
            daily_tasks_layout.addWidget(no_tasks)
        self.detail_layout.addWidget(daily_tasks_card)

        recordings_title = QLabel("RECORDINGS IN CHRONOLOGICAL ORDER")
        recordings_title.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #777985; "
            "letter-spacing: 0.5px; padding: 4px 2px;"
        )
        self.detail_layout.addWidget(recordings_title)

        for index, recording in enumerate(recording_data, start=1):
            recording_card = QFrame()
            recording_card.setStyleSheet(
                "background: #FFFFFF; border: 1px solid #E5E2DE; "
                "border-radius: 12px; padding: 16px;"
            )
            recording_layout = QVBoxLayout(recording_card)
            recording_layout.setSpacing(8)
            created_at = recording["created_at"]
            time_text = _format_recording_time(created_at)
            recording_header = QHBoxLayout()
            recording_title = QLabel(f"Recording {index} · {time_text}")
            recording_title.setStyleSheet(
                "font-size: 14px; font-weight: 700; color: #252833;"
            )
            recording_header.addWidget(recording_title, stretch=1)
            recording_header.addWidget(MoodBadge(recording["primary_mood"]))
            recording_layout.addLayout(recording_header)

            duration_frame = QFrame()
            duration_frame.setMinimumHeight(42)
            duration_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            duration_frame.setStyleSheet(
                "background: #F5F3EF; border: 1px solid #E5E2DE; "
                "border-radius: 7px;"
            )
            duration_row = QHBoxLayout(duration_frame)
            duration_row.setContentsMargins(12, 6, 12, 6)
            duration_row.setSpacing(8)
            duration_caption = QLabel("Recording duration")
            duration_caption.setStyleSheet(
                "font-size: 12px; color: #777985; font-weight: 600;"
            )
            duration_value = QLabel(
                f"{round(recording['duration_seconds'], 1)} seconds"
            )
            duration_value.setMinimumWidth(90)
            duration_value.setStyleSheet(
                "font-size: 14px; color: #344C59; font-weight: 700;"
            )
            duration_row.addWidget(duration_caption)
            duration_row.addWidget(duration_value)
            duration_row.addStretch()
            recording_layout.addWidget(duration_frame)

            individual_title = QLabel("INDIVIDUAL RECORDING ANALYSIS")
            individual_title.setStyleSheet(
                "font-size: 10px; font-weight: 700; color: #777985;"
            )
            recording_layout.addWidget(individual_title)
            for line in recording["summary"] or ["No individual analysis available."]:
                summary_label = QLabel(f"• {line}")
                summary_label.setStyleSheet("font-size: 12px; color: #252833;")
                summary_label.setWordWrap(True)
                recording_layout.addWidget(summary_label)

            transcript = QTextEdit()
            transcript.setReadOnly(True)
            transcript.setPlainText(recording["transcript"] or "No transcript recorded.")
            transcript.setMaximumHeight(100)
            transcript.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            recording_layout.addWidget(transcript)

            actions = QHBoxLayout()
            open_button = QPushButton("Open full recording details")
            open_button.setObjectName("SecondaryButton")
            open_button.clicked.connect(
                lambda _checked=False, target_id=recording["id"]:
                self.select_entry(target_id)
            )
            actions.addWidget(open_button)
            audio_path = recording["audio_file_path"]
            if audio_path and Path(audio_path).exists():
                play_button = QPushButton("▶ Play")
                play_button.setObjectName("SecondaryButton")
                play_button.clicked.connect(
                    lambda _checked=False, target=audio_path, button=play_button:
                    self._toggle_day_recording_playback(target, button)
                )
                actions.addWidget(play_button)
            actions.addStretch()
            recording_layout.addLayout(actions)
            self.detail_layout.addWidget(recording_card)

    def _load_entry_detail(self, entry_id: str):
        self.player.stop()
        self._active_play_button = None
        self.detail_slider = None
        self.lbl_detail_time = None
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        with get_db_session() as session:
            entry = session.query(DiaryEntry).filter(DiaryEntry.id == entry_id).first()
            if not entry:
                self._show_empty_detail()
                return

            tasks = session.query(Task).filter(Task.diary_entry_id == entry.id).all()
            entry = DiaryEntryDTO.from_orm(entry)
            tasks = [
                {
                    "id": task.id,
                    "description": task.description,
                    "due_date": task.due_date,
                    "priority": task.priority,
                    "status": task.status,
                }
                for task in tasks
            ]

            # 1. Header Card
            card = QFrame()
            card.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E5E2DE; border-radius: 12px; padding: 20px;")
            c_layout = QVBoxLayout(card)
            c_layout.setSpacing(12)

            top_row = QHBoxLayout()
            entry_time = _format_recording_time(entry.created_at)
            date_title = QLabel(
                f"{format_display_date(entry.entry_date)} · {entry_time}"
            )
            date_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #252833;")
            date_title.setWordWrap(True)
            date_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            top_row.addWidget(date_title)
            top_row.addStretch()
            top_row.addWidget(MoodBadge(entry.primary_mood or "Neutral"))
            c_layout.addLayout(top_row)

            # Metadata info
            meta_str = ""
            if entry.secondary_mood:
                meta_str += f"Secondary Mood: {entry.secondary_mood}  •  "
            meta_str += f"Confidence: {int(entry.mood_confidence * 100)}%"
            meta_lbl = QLabel(meta_str)
            meta_lbl.setStyleSheet("color: #777985; font-size: 12px;")
            meta_lbl.setWordWrap(True)
            meta_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            c_layout.addWidget(meta_lbl)

            duration_frame = QFrame()
            duration_frame.setMinimumHeight(44)
            duration_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            duration_frame.setStyleSheet(
                "background: #F5F3EF; border: 1px solid #E5E2DE; "
                "border-radius: 7px;"
            )
            duration_row = QHBoxLayout(duration_frame)
            duration_row.setContentsMargins(12, 6, 12, 6)
            duration_row.setSpacing(8)
            duration_caption = QLabel("Recording duration")
            duration_caption.setStyleSheet(
                "font-size: 12px; color: #777985; font-weight: 600;"
            )
            duration_value = QLabel(
                f"{round(entry.duration_seconds, 1)} seconds"
            )
            duration_value.setMinimumWidth(90)
            duration_value.setStyleSheet(
                "font-size: 14px; color: #344C59; font-weight: 700;"
            )
            duration_row.addWidget(duration_caption)
            duration_row.addWidget(duration_value)
            duration_row.addStretch()
            c_layout.addWidget(duration_frame)

            if entry.mood_evidence:
                ev_lbl = QLabel(f"<b>Mood Evidence:</b> <i>\"{entry.mood_evidence}\"</i>")
                ev_lbl.setStyleSheet("color: #344C59; font-size: 12px; background: #F5F3EF; border-radius: 6px; padding: 8px 12px;")
                ev_lbl.setWordWrap(True)
                c_layout.addWidget(ev_lbl)

            # Audio Player Bar
            if entry.audio_file_path and Path(entry.audio_file_path).exists():
                pb_frame = QFrame()
                pb_frame.setStyleSheet("background-color: #F5F3EF; border-radius: 8px; padding: 10px 14px;")
                pb_layout = QHBoxLayout(pb_frame)
                pb_layout.setContentsMargins(0, 0, 0, 0)
                pb_layout.setSpacing(10)

                self.btn_detail_play = QPushButton("▶ Play")
                self._active_play_button = self.btn_detail_play
                self.btn_detail_play.setStyleSheet("""
                    QPushButton {
                        background-color: #344C59;
                        color: #FFFFFF;
                        padding: 6px 14px;
                        font-weight: 600;
                    }
                """)
                self.btn_detail_play.clicked.connect(lambda: self._toggle_detail_playback(entry.audio_file_path))

                self.detail_slider = QSlider(Qt.Horizontal)
                self.detail_slider.setRange(0, 1000)
                self.detail_slider.sliderMoved.connect(self._on_detail_slider_moved)

                self.lbl_detail_time = QLabel("00:00 / 00:00")
                self.lbl_detail_time.setStyleSheet("font-size: 11px; color: #344C59; font-weight: 600;")

                pb_layout.addWidget(self.btn_detail_play)
                pb_layout.addWidget(self.detail_slider, stretch=1)
                pb_layout.addWidget(self.lbl_detail_time)
                c_layout.addWidget(pb_frame)

            card.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            self.detail_layout.addWidget(card)

            # 2. Three-Line Summary Card
            summary_card = QFrame()
            summary_card.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E5E2DE; border-radius: 12px; padding: 18px;")
            s_layout = QVBoxLayout(summary_card)
            s_layout.setSpacing(8)

            s_title = QLabel("INDIVIDUAL RECORDING ANALYSIS")
            s_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #777985; letter-spacing: 0.5px;")
            s_layout.addWidget(s_title)

            lines = entry.summary_lines
            if lines:
                for i, line in enumerate(lines[:3]):
                    line_lbl = QLabel(f"• {line}")
                    line_lbl.setStyleSheet("font-size: 13px; color: #252833; line-height: 1.4;")
                    line_lbl.setWordWrap(True)
                    line_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
                    s_layout.addWidget(line_lbl)
            else:
                empty_s = QLabel("No three-line summary generated.")
                empty_s.setStyleSheet("color: #96979E;")
                s_layout.addWidget(empty_s)

            summary_card.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            self.detail_layout.addWidget(summary_card)

            # 3. Topics & Highlights Chips
            chips_card = QFrame()
            chips_card.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E5E2DE; border-radius: 12px; padding: 18px;")
            chips_layout = QVBoxLayout(chips_card)
            chips_layout.setSpacing(10)

            t_lbl = QLabel("KEY TOPICS & HIGHLIGHTS")
            t_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #777985; letter-spacing: 0.5px;")
            chips_layout.addWidget(t_lbl)

            topics = entry.topics
            if topics:
                t_row = QHBoxLayout()
                t_row.setSpacing(6)
                for t in topics:
                    chip = QLabel(f"#{t}")
                    chip.setStyleSheet("background-color: #EFECF3; color: #344C59; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 10px;")
                    chip.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
                    t_row.addWidget(chip)
                t_row.addStretch()
                chips_layout.addLayout(t_row)

            highlights = entry.highlights
            if highlights:
                for h in highlights:
                    h_lbl = QLabel(f"★ {h}")
                    h_lbl.setStyleSheet("color: #344C59; font-size: 12px;")
                    h_lbl.setWordWrap(True)
                    h_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
                    chips_layout.addWidget(h_lbl)

            chips_card.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            self.detail_layout.addWidget(chips_card)

            # 4. Extracted To-Do Items Card
            todo_card = QFrame()
            todo_card.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E5E2DE; border-radius: 12px; padding: 18px;")
            td_layout = QVBoxLayout(todo_card)
            td_layout.setSpacing(10)

            td_title = QLabel(f"EXTRACTED TO-DO ITEMS ({len(tasks)})")
            td_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #777985; letter-spacing: 0.5px;")
            td_layout.addWidget(td_title)

            if tasks:
                for task in tasks:
                    t_row = QHBoxLayout()
                    t_row.setSpacing(8)
                    chk = QCheckBox(task["description"])
                    chk.setChecked(task["status"] == "Completed")
                    chk.setStyleSheet(
                        "font-size: 13px; color: " + ("#96979E; text-decoration: line-through;" if task["status"] == "Completed" else "#252833;")
                    )
                    # Wire up status toggling
                    chk.stateChanged.connect(lambda state, tid=task["id"]: self._toggle_task_from_diary(tid))
                    t_row.addWidget(chk, stretch=1)

                    if task["due_date"]:
                        due_tag = QLabel(f"Due: {task['due_date']}")
                        due_tag.setStyleSheet("color: #8F6740; font-size: 11px; font-weight: 600;")
                        t_row.addWidget(due_tag)

                    priority_style = PRIORITY_STYLES.get(
                        task["priority"], PRIORITY_STYLES["Default"]
                    )
                    prio_tag = QLabel(task["priority"])
                    prio_tag.setStyleSheet(
                        f"color: {priority_style['foreground']}; "
                        "font-size: 11px; font-weight: 700; padding: 2px 6px;"
                    )
                    t_row.addWidget(prio_tag)

                    td_layout.addLayout(t_row)
            else:
                no_tasks = QLabel("No actionable tasks were extracted from this diary entry.")
                no_tasks.setStyleSheet("color: #96979E; font-size: 12px;")
                td_layout.addWidget(no_tasks)

            todo_card.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            self.detail_layout.addWidget(todo_card)

            # 5. Full Transcripts (Tabs for Original vs Edited)
            tabs = QTabWidget()
            tabs.setStyleSheet("""
                QTabWidget::pane {
                    border: 1px solid #E5E2DE;
                    background: #FFFFFF;
                    border-radius: 8px;
                    padding: 12px;
                }
                QTabBar::tab {
                    background: #F5F3EF;
                    padding: 8px 16px;
                    margin-right: 4px;
                    border-top-left-radius: 6px;
                    border-top-right-radius: 6px;
                    font-weight: 600;
                    color: #777985;
                }
                QTabBar::tab:selected {
                    background: #FFFFFF;
                    color: #344C59;
                    border: 1px solid #E5E2DE;
                    border-bottom: none;
                }
            """)

            edited_text = QTextEdit()
            edited_text.setReadOnly(True)
            edited_text.setText(entry.effective_transcript)
            edited_text.setMinimumHeight(160)
            edited_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            tabs.addTab(edited_text, "Edited / Effective Transcript")

            orig_text = QTextEdit()
            orig_text.setReadOnly(True)
            orig_text.setText(entry.original_transcript or "No original speech transcript.")
            orig_text.setMinimumHeight(160)
            orig_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            tabs.addTab(orig_text, "Original Speech Transcript")

            tabs.setMinimumHeight(220)
            tabs.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
            self.detail_layout.addWidget(tabs)

            # 6. Action Buttons Bar (Edit, Export, Delete)
            btn_bar = QHBoxLayout()
            btn_bar.setSpacing(10)

            btn_edit = QPushButton("✏ Edit Entry")
            btn_edit.setObjectName("SecondaryButton")
            btn_edit.clicked.connect(lambda checked=False, eid=entry.id: self._edit_entry(eid))

            btn_export = QPushButton("📤 Export to Files")
            btn_export.setObjectName("SecondaryButton")
            btn_export.clicked.connect(lambda checked=False, eid=entry.id: self._export_entry_files(eid))

            btn_delete = QPushButton("🗑 Delete Entry")
            btn_delete.setObjectName("DangerButton")
            btn_delete.clicked.connect(lambda checked=False, eid=entry.id: self._delete_entry(eid))

            btn_bar.addWidget(btn_edit)
            btn_bar.addWidget(btn_export)
            btn_bar.addStretch()
            btn_bar.addWidget(btn_delete)
            self.detail_layout.addLayout(btn_bar)

    def _toggle_detail_playback(self, audio_path: str):
        self._toggle_audio_playback(audio_path, self.btn_detail_play)

    def _toggle_day_recording_playback(self, audio_path: str, button: QPushButton):
        self._toggle_audio_playback(audio_path, button)

    def _toggle_audio_playback(self, audio_path: str, button: QPushButton):
        if self.player.state == AudioPlayer.STATE_PLAYING:
            if getattr(self, "_active_audio_path", None) == audio_path:
                self.player.pause()
                if self._active_play_button:
                    self._active_play_button.setText("▶ Play")
            else:
                self.player.stop()
                self._play_audio(audio_path, button)
        elif self.player.state == AudioPlayer.STATE_PAUSED:
            if getattr(self, "_active_audio_path", None) == audio_path:
                self.player.resume()
                button.setText("⏸ Pause")
            else:
                self.player.stop()
                self._play_audio(audio_path, button)
        else:
            self._play_audio(audio_path, button)

    def _play_audio(self, audio_path: str, button: QPushButton):
        try:
            self.player.load(audio_path)
            self.player.play()
            self._active_play_button = button
            self._active_audio_path = audio_path
            button.setText("⏸ Pause")
        except Exception as e:
            QMessageBox.warning(self, "Playback Error", str(e))

    def _on_player_position(self, current: float, total: float):
        if getattr(self, "detail_slider", None) is not None and total > 0:
            pct = int((current / total) * 1000)
            self.detail_slider.setValue(pct)
            c_min = int(current) // 60
            c_sec = int(current) % 60
            t_min = int(total) // 60
            t_sec = int(total) % 60
            if self.lbl_detail_time is not None:
                self.lbl_detail_time.setText(
                    f"{c_min:02d}:{c_sec:02d} / {t_min:02d}:{t_sec:02d}"
                )

    def _on_player_finished(self):
        if self._active_play_button:
            self._active_play_button.setText("▶ Play")
        if getattr(self, "detail_slider", None) is not None:
            self.detail_slider.setValue(0)
        self._active_play_button = None

    def _on_detail_slider_moved(self, value: int):
        target_sec = (value / 1000.0) * self.player.duration
        self.player.seek(target_sec)

    def _toggle_task_from_diary(self, task_id: str):
        with get_db_session() as session:
            TaskService.toggle_task_status(session, task_id)
        if self.selected_entry_id:
            self._load_entry_detail(self.selected_entry_id)
        elif self.selected_day_date:
            self._load_day_detail(self.selected_day_date)

    def _edit_entry(self, entry_id: str):
        with get_db_session() as session:
            record = session.query(DiaryEntry).filter(DiaryEntry.id == entry_id).first()
            entry = DiaryEntryDTO.from_orm(record) if record else None
        if entry is None:
            QMessageBox.warning(self, "Entry Not Found", "This diary entry is no longer available.")
            return

        dialog = EditEntryDialog(entry, self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            updated = False
            with get_db_session() as session:
                rec = session.query(DiaryEntry).filter(DiaryEntry.id == entry_id).first()
                if rec:
                    rec.edited_transcript = data["transcript"]
                    rec.primary_mood = data["mood"]
                    session.flush()
                    # Re-export files with updated content
                    ExportService.export_daily_entry(rec)
                    updated = True

            if updated:
                QMessageBox.information(self, "Entry Updated", "Diary entry has been updated successfully.")
                self.refresh_entries()
            else:
                QMessageBox.warning(self, "Entry Not Found", "This diary entry is no longer available.")

    def _export_entry_files(self, entry_id: str):
        try:
            with get_db_session() as session:
                rec = session.query(DiaryEntry).filter(DiaryEntry.id == entry_id).first()
                if not rec:
                    QMessageBox.warning(self, "Entry Not Found", "This diary entry is no longer available.")
                    return
                entry_date = rec.entry_date
                paths = ExportService.export_daily_entry(rec)

            summary_msg = (
                f"Export files created for {entry_date}:\n\n"
                f"• {paths['diary_txt'].name}\n"
                f"• {paths['summary_txt'].name}\n"
                f"• {paths['tasks_txt'].name}\n"
                f"• {paths['entry_json'].name}\n\n"
                f"Location: {Config.EXPORTS_DAILY_DIR}"
            )
            QMessageBox.information(self, "Export Succeeded", summary_msg)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export entry files: {str(e)}")

    def _delete_entry(self, entry_id: str):
        with get_db_session() as session:
            record = session.query(DiaryEntry).filter(DiaryEntry.id == entry_id).first()
            entry_date = record.entry_date if record else None
        if entry_date is None:
            QMessageBox.warning(self, "Entry Not Found", "This diary entry is no longer available.")
            return

        confirm = QMessageBox.warning(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the diary entry for {format_display_date(entry_date)}?\n\n"
            "CONSEQUENCES:\n"
            "• The diary record will be removed from your database.\n"
            "• All associated tasks extracted from this entry will be removed.\n"
            "• The recorded audio file on disk will be safely unlinked.\n\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.player.stop()
            with get_db_session() as session:
                rec = session.query(DiaryEntry).filter(DiaryEntry.id == entry_id).first()
                if rec:
                    # Remove audio file from disk if it exists
                    if rec.audio_file_path and Path(rec.audio_file_path).exists():
                        try:
                            Path(rec.audio_file_path).unlink()
                        except Exception:
                            pass
                    session.delete(rec)

            self.selected_entry_id = None
            self.refresh_entries()
            QMessageBox.information(self, "Entry Deleted", "The diary entry and its associated tasks have been deleted.")
