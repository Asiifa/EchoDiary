"""Main window container with persistent sidebar navigation and stacked view views."""
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont

from app.ui.styles import LIGHT_THEME_QSS
from app.ui.dashboard import DashboardView
from app.ui.recorder import RecorderView
from app.ui.diary_view import DiaryView
from app.ui.todo_view import TodoView
from app.ui.weekly_view import WeeklyView
from app.ui.settings_view import SettingsView
from app.services.ollama_service import OllamaService
from app.config import Config


class MainWindow(QMainWindow):
    """EchoDiary Main Application Desktop Window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EchoDiary – Voice Diary and Mood Summariser")
        QApplication.setFont(QFont("Segoe UI", 10))
        self.resize(1220, 840)
        self.setMinimumSize(880, 620)

        # Apply global stylesheet
        self.setStyleSheet(LIGHT_THEME_QSS)

        self._init_layout()
        self._check_ollama_status()

    def _init_layout(self):
        root_widget = QWidget()
        root_layout = QHBoxLayout(root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Persistent Sidebar
        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("SidebarContainer")
        sidebar_frame.setFixedWidth(224)
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(0, 0, 0, 16)
        sidebar_layout.setSpacing(4)

        # Brand
        title_lbl = QLabel("🎙 EchoDiary")
        title_lbl.setObjectName("SidebarTitle")
        sub_lbl = QLabel("VOICE DIARY & MOOD SUMMARISER")
        sub_lbl.setObjectName("SidebarSubtitle")
        sidebar_layout.addWidget(title_lbl)
        sidebar_layout.addWidget(sub_lbl)

        # Navigation Buttons
        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "📊  Dashboard"),
            ("recorder", "🎙  New Voice Entry"),
            ("diary", "📖  My Diary"),
            ("todo", "✓  To-Do List"),
            ("weekly", "📈  Weekly Insights"),
            ("settings", "⚙  Settings"),
        ]

        for key, label in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("SidebarNavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self.navigate_to(k))
            sidebar_layout.addWidget(btn)
            self.nav_buttons[key] = btn

        sidebar_layout.addStretch()

        # Offline badge at bottom of sidebar
        offline_box = QFrame()
        offline_box.setObjectName("OfflineBadge")
        off_l = QVBoxLayout(offline_box)
        off_l.setContentsMargins(4, 4, 4, 4)
        off_l.setSpacing(2)

        off_title = QLabel("🔒 100% Local & Private")
        off_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #B4C69A;")
        off_desc = QLabel("No cloud APIs or telemetry.")
        off_desc.setStyleSheet("font-size: 10px; color: #C4C5CC;")
        off_l.addWidget(off_title)
        off_l.addWidget(off_desc)
        sidebar_layout.addWidget(offline_box)

        root_layout.addWidget(sidebar_frame)

        # 2. Right Main Content Area
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Header Bar
        header = QFrame()
        header.setObjectName("HeaderBar")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(28, 14, 28, 14)

        self.header_page_title = QLabel("Dashboard")
        self.header_page_title.setObjectName("HeaderTitle")
        h_layout.addWidget(self.header_page_title)
        h_layout.addStretch()

        # Ollama connection indicator dot in header
        self.header_ollama_status = QLabel("● Ollama Ready")
        self.header_ollama_status.setStyleSheet("color: #506344; font-weight: 600; font-size: 12px;")
        h_layout.addWidget(self.header_ollama_status)

        content_layout.addWidget(header)

        # Stacked Views Widget
        self.stack = QStackedWidget()
        self.stack.setObjectName("ContentStack")

        self.view_dashboard = DashboardView()
        self.view_recorder = RecorderView()
        self.view_diary = DiaryView()
        self.view_todo = TodoView()
        self.view_weekly = WeeklyView()
        self.view_settings = SettingsView()

        self.stack.addWidget(self.view_dashboard)   # Index 0
        self.stack.addWidget(self.view_recorder)    # Index 1
        self.stack.addWidget(self.view_diary)       # Index 2
        self.stack.addWidget(self.view_todo)        # Index 3
        self.stack.addWidget(self.view_weekly)      # Index 4
        self.stack.addWidget(self.view_settings)    # Index 5

        self.view_indices = {
            "dashboard": (0, "Dashboard"),
            "recorder": (1, "New Voice Entry"),
            "diary": (2, "My Diary"),
            "todo": (3, "To-Do List"),
            "weekly": (4, "Weekly Insights & Digest"),
            "settings": (5, "Settings & Privacy"),
        }

        content_layout.addWidget(self.stack, stretch=1)
        root_layout.addWidget(content_container, stretch=1)

        self.setCentralWidget(root_widget)

        # Connect inter-view signals
        self.view_dashboard.navigate_to.connect(self.navigate_to)
        self.view_dashboard.view_entry_requested.connect(self._open_entry_in_diary)
        self.view_recorder.entry_saved.connect(self._on_recorder_entry_saved)
        self.view_recorder.daily_analysis_updated.connect(
            self._on_daily_analysis_updated
        )
        self.view_todo.navigate_to_entry.connect(self._open_entry_in_diary)

        # Set initial page
        self.navigate_to("dashboard")

    def navigate_to(self, page_key: str):
        """Switch active stacked view and update sidebar selection."""
        if page_key not in self.view_indices:
            return

        idx, title = self.view_indices[page_key]
        self.stack.setCurrentIndex(idx)
        self.header_page_title.setText(title)

        # Update button checked states
        for key, btn in self.nav_buttons.items():
            btn.setChecked(key == page_key)

        # Trigger data refreshes on views when navigated to
        if page_key == "dashboard":
            self.view_dashboard.refresh_data()
        elif page_key == "diary":
            self.view_diary.refresh_entries()
        elif page_key == "todo":
            self.view_todo.refresh_tasks()
        elif page_key == "settings":
            self.view_settings.check_ollama_status()
            self.view_settings.refresh_backups()

    def _open_entry_in_diary(self, entry_id: str):
        """Navigate to diary view and automatically select the specified entry."""
        self.navigate_to("diary")
        self.view_diary.select_entry(entry_id)

    def _on_recorder_entry_saved(self, entry_id: str):
        """After recording is saved, navigate to diary view to show entry."""
        self._open_entry_in_diary(entry_id)

    def _on_daily_analysis_updated(self, _entry_date: str):
        """Refresh date-level analysis after its background synthesis completes."""
        self.view_diary.refresh_entries()

    def _check_ollama_status(self):
        try:
            ollama = OllamaService()
            is_conn, _, _ = ollama.check_connection()
            if is_conn:
                self.header_ollama_status.setText("● Local AI (Ollama) Online")
                self.header_ollama_status.setStyleSheet("color: #506344; font-weight: 600; font-size: 12px;")
            else:
                self.header_ollama_status.setText("● Local AI (Ollama) Offline")
                self.header_ollama_status.setStyleSheet("color: #8F6740; font-weight: 600; font-size: 12px;")
        except Exception:
            self.header_ollama_status.setText("● Local AI (Ollama) Offline")
            self.header_ollama_status.setStyleSheet("color: #8F6740; font-weight: 600; font-size: 12px;")
