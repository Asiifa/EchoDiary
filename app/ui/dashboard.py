"""Dashboard view displaying daily status, statistics, latest entry, and weekly mood overview."""
from datetime import datetime, date
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.models.diary_entry import DiaryEntry
from app.models.task import Task
from app.schemas.entry_dto import DiaryEntryDTO
from app.ui.components.stat_card import StatCard
from app.ui.components.mood_badge import MoodBadge
from app.utils.date_utils import format_display_date, get_current_week_range, get_today_date
from app.services.mood_service import MoodService


class DashboardView(QWidget):
    """Modern, calming dashboard showing daily status, metrics, and latest reflections."""

    navigate_to = Signal(str)  # Emits target page name: 'recorder', 'diary', 'todo', 'weekly', 'settings'
    view_entry_requested = Signal(str)  # Emits entry_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.refresh_data()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for responsive resizing
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }")

        container = QWidget()
        container.setObjectName("ContentArea")
        self.layout = QVBoxLayout(container)
        self.layout.setContentsMargins(32, 28, 32, 28)
        self.layout.setSpacing(22)

        # 1. Header with dynamic greeting and date
        header_layout = QHBoxLayout()
        greeting_box = QVBoxLayout()
        greeting_box.setSpacing(4)

        hour = datetime.now().hour
        if hour < 12:
            greet = "Good morning"
        elif hour < 18:
            greet = "Good afternoon"
        else:
            greet = "Good evening"

        self.greeting_label = QLabel(f"{greet}")
        self.greeting_label.setStyleSheet("font-size: 24px; font-weight: 700; color: #252833;")

        self.date_label = QLabel(format_display_date(get_today_date()))
        self.date_label.setStyleSheet("font-size: 13px; color: #777985; font-weight: 500;")

        greeting_box.addWidget(self.greeting_label)
        greeting_box.addWidget(self.date_label)
        header_layout.addLayout(greeting_box)
        header_layout.addStretch()

        self.record_quick_btn = QPushButton("+ New Voice Entry")
        self.record_quick_btn.setStyleSheet("""
            QPushButton {
                background-color: #9A8BB8;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 600;
                padding: 10px 22px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #81749B;
            }
        """)
        self.record_quick_btn.clicked.connect(lambda: self.navigate_to.emit("recorder"))
        header_layout.addWidget(self.record_quick_btn)
        self.layout.addLayout(header_layout)

        # 2. Today's Diary Status Card
        self.today_status_card = QFrame()
        self.today_status_card.setObjectName("CardFrame")
        self.today_status_card.setStyleSheet("""
            QFrame#CardFrame {
                background-color: #FFFFFF;
                border: 1px solid #E5E2DE;
                border-radius: 12px;
                padding: 18px 24px;
            }
        """)
        self.today_card_layout = QHBoxLayout(self.today_status_card)
        self.layout.addWidget(self.today_status_card)

        # 3. 4-Grid Stat Cards
        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(16)

        self.card_total = StatCard("Total Entries", "0", "All-time recordings", "#9A8BB8")
        self.card_week = StatCard("This Week", "0", "Last 7 days logged", "#344C59")
        self.card_pending = StatCard("Tasks Pending", "0", "Action items", "#8F6740")
        self.card_completed = StatCard("Tasks Done", "0", "Accomplished", "#506344")

        self.stat_cards = [
            self.card_total,
            self.card_week,
            self.card_pending,
            self.card_completed,
        ]
        self.layout.addLayout(self.stats_grid)
        self._stats_columns = 0
        self._update_responsive_layout()

        # 4. Two columns: Latest Entry (Left) and Weekly Mood Overview (Right)
        self.middle_layout = QGridLayout()
        self.middle_layout.setSpacing(18)

        # Left: Latest Entry Card
        self.latest_card = QFrame()
        self.latest_card.setObjectName("CardFrame")
        self.latest_card.setStyleSheet("""
            QFrame#CardFrame {
                background-color: #FFFFFF;
                border: 1px solid #E5E2DE;
                border-radius: 12px;
                padding: 20px 24px;
            }
        """)
        self.latest_layout = QVBoxLayout(self.latest_card)
        self.latest_layout.setSpacing(12)
        self.middle_layout.addWidget(self.latest_card, 0, 0)

        # Right: Weekly Mood Overview & Weekly Digest Card
        self.mood_card = QFrame()
        self.mood_card.setObjectName("CardFrame")
        self.mood_card.setStyleSheet("""
            QFrame#CardFrame {
                background-color: #FFFFFF;
                border: 1px solid #E5E2DE;
                border-radius: 12px;
                padding: 20px 24px;
            }
        """)
        self.mood_layout = QVBoxLayout(self.mood_card)
        self.mood_layout.setSpacing(14)
        self.middle_layout.addWidget(self.mood_card, 0, 1)

        self.layout.addLayout(self.middle_layout)
        self.layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        self._update_responsive_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_responsive_layout()

    def _update_responsive_layout(self):
        if not hasattr(self, "stats_grid"):
            return

        columns = 2 if self.width() < 960 else 4
        if columns != self._stats_columns:
            for card in self.stat_cards:
                self.stats_grid.removeWidget(card)
            for index, card in enumerate(self.stat_cards):
                self.stats_grid.addWidget(card, index // columns, index % columns)
            self._stats_columns = columns

        if hasattr(self, "middle_layout"):
            narrow = self.width() < 900
            if getattr(self, "_middle_is_narrow", None) != narrow:
                self.middle_layout.removeWidget(self.latest_card)
                self.middle_layout.removeWidget(self.mood_card)
                if narrow:
                    self.middle_layout.addWidget(self.latest_card, 0, 0)
                    self.middle_layout.addWidget(self.mood_card, 1, 0)
                    self.middle_layout.setColumnStretch(0, 1)
                    self.middle_layout.setColumnStretch(1, 0)
                else:
                    self.middle_layout.addWidget(self.latest_card, 0, 0)
                    self.middle_layout.addWidget(self.mood_card, 0, 1)
                    self.middle_layout.setColumnStretch(0, 3)
                    self.middle_layout.setColumnStretch(1, 2)
                self._middle_is_narrow = narrow

    def refresh_data(self):
        """Query SQLite database and update all dashboard components with real data."""
        today = get_today_date()
        week_start, week_end = get_current_week_range(today)

        with get_db_session() as session:
            # Query counts
            total_entries = session.query(DiaryEntry).filter(DiaryEntry.is_deleted == False).count()
            week_entries = (
                session.query(DiaryEntry)
                .filter(
                    DiaryEntry.entry_date >= week_start,
                    DiaryEntry.entry_date <= week_end,
                    DiaryEntry.is_deleted == False,
                )
                .count()
            )
            pending_tasks = session.query(Task).filter(Task.status == "Pending").count()
            completed_tasks = session.query(Task).filter(Task.status == "Completed").count()

            # Check today's entry
            today_entry_orm = (
                session.query(DiaryEntry)
                .filter(DiaryEntry.entry_date == today, DiaryEntry.is_deleted == False)
                .order_by(DiaryEntry.created_at.desc())
                .first()
            )
            # Convert to detached DTO while session is active
            today_entry_dto = DiaryEntryDTO.from_orm(today_entry_orm) if today_entry_orm else None

            # Query latest entry
            latest_entry_orm = (
                session.query(DiaryEntry)
                .filter(DiaryEntry.is_deleted == False)
                .order_by(DiaryEntry.entry_date.desc(), DiaryEntry.created_at.desc())
                .first()
            )
            # Convert to detached DTO while session is active
            latest_entry_dto = DiaryEntryDTO.from_orm(latest_entry_orm) if latest_entry_orm else None

            # Query week's entries for mood distribution
            week_entry_list_orm = (
                session.query(DiaryEntry)
                .filter(
                    DiaryEntry.entry_date >= week_start,
                    DiaryEntry.entry_date <= week_end,
                    DiaryEntry.is_deleted == False,
                )
                .all()
            )
            # Convert list of ORM entries to detached DTOs while session is active
            week_entry_dtos = [DiaryEntryDTO.from_orm(entry) for entry in week_entry_list_orm]

        # Update Stat Cards
        self.card_total.set_value(str(total_entries))
        self.card_week.set_value(str(week_entries))
        self.card_pending.set_value(str(pending_tasks))
        self.card_completed.set_value(str(completed_tasks))

        # Update Today's Status Banner using detached DTO
        self._update_today_card(today_entry_dto)

        # Update Latest Entry Card using detached DTO
        self._update_latest_card(latest_entry_dto)

        # Update Mood Overview Card using detached DTO list
        self._update_mood_overview(week_entry_dtos)

    def _update_today_card(self, entry: Optional[DiaryEntryDTO] = None):
        # Clear existing layout
        while self.today_card_layout.count():
            item = self.today_card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if entry:
            info_layout = QVBoxLayout()
            info_layout.setSpacing(4)

            title_row = QHBoxLayout()
            title_row.setSpacing(10)
            check_icon = QLabel("✓")
            check_icon.setStyleSheet("color: #506344; font-weight: 800; font-size: 16px;")
            status_title = QLabel("Today's Diary Entry Recorded")
            status_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #252833;")
            status_title.setWordWrap(True)
            status_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

            title_row.addWidget(check_icon)
            title_row.addWidget(status_title)
            title_row.addWidget(MoodBadge(entry.primary_mood or "Neutral"))
            title_row.addStretch()

            summary_preview = (
                entry.summary_lines[0]
                if entry.summary_lines
                else (entry.effective_transcript[:120] + "..." if len(entry.effective_transcript) > 120 else entry.effective_transcript)
            )
            sub_lbl = QLabel(summary_preview or "Reflections captured for today.")
            sub_lbl.setStyleSheet("color: #777985; font-size: 12px;")
            sub_lbl.setWordWrap(True)
            sub_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

            info_layout.addLayout(title_row)
            info_layout.addWidget(sub_lbl)
            self.today_card_layout.addLayout(info_layout, stretch=1)

            btn_view = QPushButton("View Entry")
            btn_view.setObjectName("SecondaryButton")
            btn_view.setStyleSheet("""
                QPushButton {
                    background-color: #F5F3EF;
                    color: #344C59;
                    border: 1px solid #E5E2DE;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #EFECF3;
                    color: #344C59;
                }
            """)
            entry_id = str(entry.id)
            btn_view.clicked.connect(lambda checked=False, eid=entry_id: self.view_entry_requested.emit(eid))
            self.today_card_layout.addWidget(btn_view)
        else:
            info_layout = QVBoxLayout()
            info_layout.setSpacing(4)
            status_title = QLabel("You haven't recorded your voice diary today yet")
            status_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #344C59;")
            status_title.setWordWrap(True)
            status_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            sub_lbl = QLabel("Take 1-2 minutes to record your reflections, activities, and tasks.")
            sub_lbl.setStyleSheet("color: #777985; font-size: 12px;")
            sub_lbl.setWordWrap(True)
            sub_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            info_layout.addWidget(status_title)
            info_layout.addWidget(sub_lbl)
            self.today_card_layout.addLayout(info_layout, stretch=1)

            btn_record = QPushButton("Record Today's Entry")
            btn_record.setStyleSheet("""
                QPushButton {
                    background-color: #9A8BB8;
                    color: #FFFFFF;
                    padding: 9px 18px;
                    border-radius: 6px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #81749B;
                }
            """)
            btn_record.clicked.connect(lambda: self.navigate_to.emit("recorder"))
            self.today_card_layout.addWidget(btn_record)

    def _update_latest_card(self, entry: Optional[DiaryEntryDTO] = None):
        while self.latest_layout.count():
            item = self.latest_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        header_row = QHBoxLayout()
        header_title = QLabel("LATEST DIARY ENTRY")
        header_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #777985; letter-spacing: 0.5px;")
        header_row.addWidget(header_title)
        header_row.addStretch()

        if entry:
            badge = MoodBadge(entry.primary_mood or "Neutral")
            header_row.addWidget(badge)
            self.latest_layout.addLayout(header_row)

            date_str = format_display_date(entry.entry_date) if entry.entry_date else "Unknown Date"
            dur = round(float(entry.duration_seconds or 0.0), 1)
            date_line = QLabel(f"{date_str}  •  {dur}s audio")
            date_line.setStyleSheet("font-size: 13px; font-weight: 600; color: #344C59;")
            self.latest_layout.addWidget(date_line)

            # Three-line summary box
            summary_box = QFrame()
            summary_box.setStyleSheet("background-color: #F5F3EF; border-radius: 8px; padding: 12px;")
            s_layout = QVBoxLayout(summary_box)
            s_layout.setContentsMargins(10, 8, 10, 8)
            s_layout.setSpacing(6)

            lines = entry.summary_lines or []
            if lines:
                for i, line in enumerate(lines[:3]):
                    line_lbl = QLabel(f"{i+1}. {line}")
                    line_lbl.setStyleSheet("font-size: 12px; color: #252833; line-height: 1.4;")
                    line_lbl.setWordWrap(True)
                    line_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
                    s_layout.addWidget(line_lbl)
            else:
                eff_text = entry.effective_transcript or ""
                raw_text = eff_text[:180] + ("..." if len(eff_text) > 180 else "")
                t_lbl = QLabel(raw_text or "No summary available.")
                t_lbl.setStyleSheet("font-size: 12px; color: #344C59;")
                t_lbl.setWordWrap(True)
                t_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
                s_layout.addWidget(t_lbl)

            self.latest_layout.addWidget(summary_box)

            # Footer with button
            footer_row = QHBoxLayout()
            tasks_count = entry.tasks_count if hasattr(entry, "tasks_count") else (len(entry.tasks) if entry.tasks else 0)
            tasks_info = QLabel(f"{tasks_count} task(s) linked")
            tasks_info.setStyleSheet("color: #777985; font-size: 11px;")
            footer_row.addWidget(tasks_info)
            footer_row.addStretch()

            open_btn = QPushButton("Open in My Diary →")
            open_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #9A8BB8;
                    font-size: 12px;
                    font-weight: 600;
                    border: none;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    color: #4C3C73;
                    text-decoration: underline;
                }
            """)
            entry_id = str(entry.id)
            open_btn.clicked.connect(lambda checked=False, eid=entry_id: self.view_entry_requested.emit(eid))
            footer_row.addWidget(open_btn)
            self.latest_layout.addLayout(footer_row)
        else:
            self.latest_layout.addLayout(header_row)
            empty_lbl = QLabel("No diary entries recorded yet.\nYour spoken reflections, 3-line summaries, and mood analytics will appear here.")
            empty_lbl.setStyleSheet("color: #96979E; font-size: 13px; padding: 24px 0px;")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setWordWrap(True)
            empty_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            self.latest_layout.addWidget(empty_lbl)

    def _update_mood_overview(self, week_entries: Optional[List[DiaryEntryDTO]] = None):
        while self.mood_layout.count():
            item = self.mood_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        header_title = QLabel("WEEKLY MOOD OVERVIEW")
        header_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #777985; letter-spacing: 0.5px;")
        self.mood_layout.addWidget(header_title)

        if week_entries:
            # Calculate counts
            counts = {}
            for e in week_entries:
                m = e.primary_mood or "Neutral"
                counts[m] = counts.get(m, 0) + 1

            pills_layout = QVBoxLayout()
            pills_layout.setSpacing(8)

            for mood, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:4]:
                row = QHBoxLayout()
                row.addWidget(MoodBadge(mood))
                count_lbl = QLabel(f"{count} day{'s' if count > 1 else ''}")
                count_lbl.setStyleSheet("color: #777985; font-size: 12px; font-weight: 500;")
                row.addStretch()
                row.addWidget(count_lbl)
                pills_layout.addLayout(row)

            self.mood_layout.addLayout(pills_layout)
        else:
            no_mood = QLabel("No entries in the past 7 days.\nRecord your diary to see mood patterns.")
            no_mood.setStyleSheet("color: #96979E; font-size: 12px; padding: 16px 0;")
            no_mood.setAlignment(Qt.AlignCenter)
            no_mood.setWordWrap(True)
            no_mood.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            self.mood_layout.addWidget(no_mood)

        self.mood_layout.addStretch()

        digest_btn = QPushButton("View Weekly Insights →")
        digest_btn.setObjectName("SecondaryButton")
        digest_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F3EF;
                color: #344C59;
                border: 1px solid #E5E2DE;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #EFECF3;
                color: #344C59;
            }
        """)
        digest_btn.clicked.connect(lambda: self.navigate_to.emit("weekly"))
        self.mood_layout.addWidget(digest_btn)
