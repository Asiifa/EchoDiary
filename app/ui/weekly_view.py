"""Weekly Digest & Analytics view featuring 7-day AI synthesis and PyQtGraph visualizations."""
from datetime import date, timedelta
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDateEdit, QFrame, QScrollArea, QMessageBox, QProgressBar,
    QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal
import pyqtgraph as pg

from app.database import get_db_session
from app.models.diary_entry import DiaryEntry
from app.models.weekly_report import WeeklyReport
from app.services.weekly_digest_service import WeeklyDigestService
from app.services.export_service import ExportService
from app.services.mood_service import MoodService
from app.utils.date_utils import format_display_date, get_current_week_range, get_today_date
from app.config import Config


class WeeklyWorker(QThread):
    """Background worker for local Ollama weekly synthesis."""
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, start_d: date, end_d: date):
        super().__init__()
        self.start_d = start_d
        self.end_d = end_d

    def run(self):
        try:
            with get_db_session() as session:
                service = WeeklyDigestService()
                report = service.generate_digest(session, self.start_d, self.end_d)
                # Read into dictionary to safely pass across thread
                data = report.to_dict()
            self.finished.emit(data)
        except Exception as e:
            self.failed.emit(str(e))


class WeeklyView(QWidget):
    """Weekly digest dashboard with period selector, PyQtGraph charts, and export actions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_report_data: Optional[Dict[str, Any]] = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container.setObjectName("ContentArea")
        self.layout = QVBoxLayout(container)
        self.layout.setContentsMargins(32, 28, 32, 28)
        self.layout.setSpacing(20)

        # 1. Header
        header_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Weekly Insights & Digest")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #252833;")
        sub = QLabel("Comprehensive 7-day synthesis of your reflections, mood trends, and accomplishments.")
        sub.setStyleSheet("font-size: 13px; color: #777985;")
        sub.setWordWrap(True)
        sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title_box.addWidget(title)
        title_box.addWidget(sub)
        header_row.addLayout(title_box)
        header_row.addStretch()
        self.layout.addLayout(header_row)

        # Date range controls use two rows so they remain usable at narrow widths.
        ctrl_box = QVBoxLayout()
        ctrl_box.setSpacing(10)

        self.btn_prev_week = QPushButton("← Previous Week")
        self.btn_prev_week.setObjectName("SecondaryButton")
        self.btn_prev_week.setStyleSheet("padding: 7px 12px; font-weight: 500;")
        self.btn_prev_week.clicked.connect(self._select_prev_week)

        self.btn_this_week = QPushButton("Current 7 Days")
        self.btn_this_week.setObjectName("SecondaryButton")
        self.btn_this_week.setStyleSheet("padding: 7px 12px; font-weight: 500;")
        self.btn_this_week.clicked.connect(self._select_this_week)

        date_lbl = QLabel("Start Date:")
        date_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        self.start_date_picker = QDateEdit()
        self.start_date_picker.setCalendarPopup(True)
        today = get_today_date()
        w_start, _ = get_current_week_range(today)
        self.start_date_picker.setDate(w_start)
        self.start_date_picker.dateChanged.connect(self._on_date_changed)

        self.end_date_label = QLabel(f"to {format_display_date(w_start + timedelta(days=6))}")
        self.end_date_label.setStyleSheet("color: #777985; font-weight: 600;")

        self.btn_generate = QPushButton("✨ Generate Weekly Digest")
        self.btn_generate.setStyleSheet("""
            QPushButton {
                background-color: #9A8BB8;
                color: #FFFFFF;
                font-weight: 600;
                padding: 9px 18px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #81749B;
            }
        """)
        self.btn_generate.clicked.connect(self._generate_digest)

        week_buttons = QHBoxLayout()
        week_buttons.setSpacing(10)
        week_buttons.addWidget(self.btn_prev_week)
        week_buttons.addWidget(self.btn_this_week)
        ctrl_box.addLayout(week_buttons)
        date_controls = QVBoxLayout()
        date_controls.setSpacing(4)
        date_controls.addWidget(date_lbl)
        date_controls.addWidget(self.start_date_picker)
        date_controls.addWidget(self.end_date_label)
        ctrl_box.addLayout(date_controls)
        generate_row = QHBoxLayout()
        generate_row.addStretch()
        generate_row.addWidget(self.btn_generate)
        ctrl_box.addLayout(generate_row)
        self.layout.addLayout(ctrl_box)

        # 2. Progress / Status indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.layout.addWidget(self.progress_bar)

        self.status_msg = QLabel("")
        self.status_msg.setStyleSheet("color: #777985; font-size: 13px; font-weight: 500;")
        self.layout.addWidget(self.status_msg)

        # 3. Partial Week Banner Frame
        self.banner_frame = QFrame()
        self.banner_frame.setStyleSheet("""
            QFrame {
                background-color: #F5EEE4;
                border: 1px solid #D8BD92;
                border-radius: 8px;
                padding: 10px 16px;
            }
        """)
        b_layout = QHBoxLayout(self.banner_frame)
        self.banner_text = QLabel("⚠️ Partial Data Notice: This digest is based on fewer than 7 days of entries.")
        self.banner_text.setStyleSheet("color: #8F6740; font-weight: 600; font-size: 12px; background: transparent;")
        self.banner_text.setWordWrap(True)
        self.banner_text.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        b_layout.addWidget(self.banner_text)
        self.banner_frame.setVisible(False)
        self.layout.addWidget(self.banner_frame)

        # 4. Content Area: Charts & Narrative Cards
        # Charts Row (PyQtGraph)
        self.charts_row = QGridLayout()
        self.charts_row.setSpacing(18)

        # Chart 1: Mood Distribution
        chart1_frame = QFrame()
        chart1_frame.setObjectName("CardFrame")
        chart1_frame.setMinimumWidth(0)
        chart1_frame.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        chart1_frame.setStyleSheet("QFrame#CardFrame { background-color: #FFFFFF; border: 1px solid #E5E2DE; border-radius: 12px; padding: 14px; }")
        c1_layout = QVBoxLayout(chart1_frame)
        c1_title = QLabel("MOOD DISTRIBUTION (7 DAYS)")
        c1_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #777985; letter-spacing: 0.5px;")
        c1_layout.addWidget(c1_title)

        pg.setConfigOption("background", "#FFFFFF")
        pg.setConfigOption("foreground", "#344C59")

        self.plot_mood = pg.PlotWidget()
        self.plot_mood.setMinimumWidth(0)
        self.plot_mood.setMinimumHeight(190)
        self.plot_mood.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.plot_mood.showGrid(x=False, y=True, alpha=0.15)
        c1_layout.addWidget(self.plot_mood)
        self.chart_frames = [chart1_frame]

        # Chart 2: 7-Day Activity & Emotional Trend
        chart2_frame = QFrame()
        chart2_frame.setObjectName("CardFrame")
        chart2_frame.setMinimumWidth(0)
        chart2_frame.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        chart2_frame.setStyleSheet("QFrame#CardFrame { background-color: #FFFFFF; border: 1px solid #E5E2DE; border-radius: 12px; padding: 14px; }")
        c2_layout = QVBoxLayout(chart2_frame)
        c2_title = QLabel("7-DAY DIARY LOGGING & CONFIDENCE")
        c2_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #777985; letter-spacing: 0.5px;")
        c2_layout.addWidget(c2_title)

        self.plot_activity = pg.PlotWidget()
        self.plot_activity.setMinimumWidth(0)
        self.plot_activity.setMinimumHeight(190)
        self.plot_activity.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.plot_activity.showGrid(x=True, y=True, alpha=0.15)
        c2_layout.addWidget(self.plot_activity)
        self.chart_frames.append(chart2_frame)

        self.layout.addLayout(self.charts_row)

        # 5. Digest Details Container
        self.digest_card = QFrame()
        self.digest_card.setObjectName("CardFrame")
        self.digest_card.setStyleSheet("QFrame#CardFrame { background-color: #FFFFFF; border: 1px solid #E5E2DE; border-radius: 12px; padding: 24px; }")
        self.digest_layout = QVBoxLayout(self.digest_card)
        self.digest_layout.setSpacing(18)
        self.layout.addWidget(self.digest_card)

        # 6. Export Buttons Row
        self.export_row = QGridLayout()
        self.export_row.setSpacing(12)

        self.btn_export_md = QPushButton("Export Markdown (.md)")
        self.btn_export_md.setObjectName("SecondaryButton")
        self.btn_export_md.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #344C59;
                border: 1px solid #E5E2DE;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #F5F3EF;
            }
        """)
        self.btn_export_md.clicked.connect(lambda: self._export_digest_files("md"))

        self.btn_export_txt = QPushButton("Export Plain Text (.txt)")
        self.btn_export_txt.setObjectName("SecondaryButton")
        self.btn_export_txt.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #344C59;
                border: 1px solid #E5E2DE;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #F5F3EF;
            }
        """)
        self.btn_export_txt.clicked.connect(lambda: self._export_digest_files("txt"))

        self.export_buttons = [self.btn_export_md, self.btn_export_txt]
        self.layout.addLayout(self.export_row)
        self.layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Load initial week preview
        self._load_cached_or_preview()
        self._chart_columns = 0
        self._update_chart_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_chart_layout()

    def _update_chart_layout(self):
        if not hasattr(self, "chart_frames") or not hasattr(self, "export_buttons"):
            return
        columns = 1 if self.width() < 900 else 2
        if columns == getattr(self, "_chart_columns", 0):
            return
        for frame in self.chart_frames:
            self.charts_row.removeWidget(frame)
        for index, frame in enumerate(self.chart_frames):
            self.charts_row.addWidget(frame, index // columns, index % columns)
        for column in range(2):
            self.charts_row.setColumnStretch(column, 1 if column < columns else 0)
        for button in self.export_buttons:
            self.export_row.removeWidget(button)
        for index, button in enumerate(self.export_buttons):
            self.export_row.addWidget(
                button,
                index // columns,
                index % columns,
                alignment=Qt.AlignRight,
            )
        for column in range(2):
            self.export_row.setColumnStretch(column, 1 if column < columns else 0)
        self._chart_columns = columns

    def _on_date_changed(self, qdate):
        start_d = qdate.toPython()
        end_d = start_d + timedelta(days=6)
        self.end_date_label.setText(f"to {format_display_date(end_d)}")
        self._load_cached_or_preview()

    def _select_this_week(self):
        today = get_today_date()
        start_d, _ = get_current_week_range(today)
        self.start_date_picker.setDate(start_d)

    def _select_prev_week(self):
        curr_start = self.start_date_picker.date().toPython()
        prev_start = curr_start - timedelta(days=7)
        self.start_date_picker.setDate(prev_start)

    def _load_cached_or_preview(self):
        start_d = self.start_date_picker.date().toPython()
        end_d = start_d + timedelta(days=6)

        with get_db_session() as session:
            # Check if report already generated
            report = (
                session.query(WeeklyReport)
                .filter(WeeklyReport.start_date == start_d, WeeklyReport.end_date == end_d)
                .first()
            )
            entry_count = (
                session.query(DiaryEntry)
                .filter(
                    DiaryEntry.entry_date >= start_d,
                    DiaryEntry.entry_date <= end_d,
                    DiaryEntry.is_deleted == False,
                )
                .count()
            )
            report_data = report.to_dict() if report else None

        if report_data:
            self._render_report(report_data)
        else:
            self._render_empty_preview(start_d, end_d, entry_count)

    def _render_empty_preview(self, start_d: date, end_d: date, entry_count: int):
        self.current_report_data = None
        self.banner_frame.setVisible(False)
        self.btn_export_md.setEnabled(False)
        self.btn_export_txt.setEnabled(False)

        while self.digest_layout.count():
            item = self.digest_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        box = QVBoxLayout()
        box.setSpacing(10)
        box.setAlignment(Qt.AlignCenter)

        msg = QLabel(
            f"You have logged <b>{entry_count}</b> entry(ies) between "
            f"{format_display_date(start_d)} and {format_display_date(end_d)}."
        )
        msg.setStyleSheet("font-size: 14px; color: #344C59;")
        msg.setAlignment(Qt.AlignCenter)
        msg.setWordWrap(True)
        msg.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        prompt = QLabel("Click <b>✨ Generate Weekly Digest</b> above to analyze this 7-day period with local Ollama.")
        prompt.setStyleSheet("font-size: 13px; color: #777985;")
        prompt.setAlignment(Qt.AlignCenter)
        prompt.setWordWrap(True)
        prompt.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        box.addWidget(msg)
        box.addWidget(prompt)
        self.digest_layout.addLayout(box)

        # Clear charts
        self.plot_mood.clear()
        self.plot_activity.clear()

    def _generate_digest(self):
        start_d = self.start_date_picker.date().toPython()
        end_d = start_d + timedelta(days=6)

        self.btn_generate.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_msg.setText("Analyzing 7-day reflections with Ollama (qwen2.5:3b)...")

        self.worker = WeeklyWorker(start_d, end_d)
        self.worker.finished.connect(self._on_digest_finished)
        self.worker.failed.connect(self._on_digest_failed)
        self.worker.start()

    def _on_digest_finished(self, report_dict: dict):
        self.btn_generate.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_msg.setText(f"✓ Digest ready for {report_dict['start_date']} to {report_dict['end_date']}")
        self._render_report(report_dict)

    def _on_digest_failed(self, error_msg: str):
        self.btn_generate.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_msg.setText("Failed to generate digest.")
        QMessageBox.critical(self, "Weekly Digest Error", f"Ollama generation failed:\n{error_msg}")

    def _render_report(self, data: dict):
        self.current_report_data = data
        self.btn_export_md.setEnabled(True)
        self.btn_export_txt.setEnabled(True)

        is_partial = data.get("is_partial_week", False)
        entries_count = data.get("entries_count", 0)

        # Show / hide partial week banner
        if is_partial:
            self.banner_text.setText(
                f"⚠️ Partial Data: This report is based on {entries_count} of 7 days logged for this period."
            )
            self.banner_frame.setVisible(True)
        else:
            self.banner_frame.setVisible(False)

        # Clear layout
        while self.digest_layout.count():
            item = self.digest_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 1. Weekly Overview Card
        ov_title = QLabel("1. WEEKLY OVERVIEW")
        ov_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #777985; letter-spacing: 0.5px;")
        ov_text = QLabel(data.get("overview", "No overview available."))
        ov_text.setStyleSheet("font-size: 14px; color: #252833; line-height: 1.5;")
        ov_text.setWordWrap(True)
        self.digest_layout.addWidget(ov_title)
        self.digest_layout.addWidget(ov_text)

        # 2. Key Highlights & Accomplishments (Two columns)
        two_col = QHBoxLayout()
        two_col.setSpacing(16)

        # Highlights
        h_box = QVBoxLayout()
        h_title = QLabel("2. KEY HIGHLIGHTS")
        h_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #777985;")
        h_box.addWidget(h_title)
        for h in data.get("highlights", []):
            hl = QLabel(f"★ {h}")
            hl.setStyleSheet("font-size: 12px; color: #344C59;")
            hl.setWordWrap(True)
            h_box.addWidget(hl)
        two_col.addLayout(h_box, stretch=1)

        # Accomplishments
        a_box = QVBoxLayout()
        a_title = QLabel("3. ACCOMPLISHMENTS")
        a_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #777985;")
        a_box.addWidget(a_title)
        for a in data.get("accomplishments", []):
            al = QLabel(f"✓ {a}")
            al.setStyleSheet("font-size: 12px; color: #506344; font-weight: 500;")
            al.setWordWrap(True)
            a_box.addWidget(al)
        two_col.addLayout(a_box, stretch=1)
        self.digest_layout.addLayout(two_col)

        # 3. Main Topics & Recurring Themes
        t_row = QHBoxLayout()
        t_row.setSpacing(16)

        topics_box = QVBoxLayout()
        t_title = QLabel("4. MAIN TOPICS DISCUSSED")
        t_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #777985;")
        topics_box.addWidget(t_title)
        t_chips = QHBoxLayout()
        for topic in data.get("main_topics", []):
            chip = QLabel(f"#{topic}")
            chip.setStyleSheet("background-color: #EFECF3; color: #344C59; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 10px;")
            t_chips.addWidget(chip)
        t_chips.addStretch()
        topics_box.addLayout(t_chips)
        t_row.addLayout(topics_box, stretch=1)

        themes_box = QVBoxLayout()
        th_title = QLabel("5. RECURRING THEMES")
        th_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #777985;")
        themes_box.addWidget(th_title)
        for th in data.get("recurring_themes", []):
            tl = QLabel(f"• {th}")
            tl.setStyleSheet("font-size: 12px; color: #344C59;")
            tl.setWordWrap(True)
            themes_box.addWidget(tl)
        t_row.addLayout(themes_box, stretch=1)
        self.digest_layout.addLayout(t_row)

        # 4. Next Week Suggested Priorities
        p_title = QLabel("6. NEXT WEEK'S SUGGESTED PRIORITIES")
        p_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #777985; letter-spacing: 0.5px;")
        self.digest_layout.addWidget(p_title)
        for sp in data.get("suggested_priorities", []):
            sp_lbl = QLabel(f"→ {sp}")
            sp_lbl.setStyleSheet("font-size: 13px; color: #252833; font-weight: 500;")
            sp_lbl.setWordWrap(True)
            self.digest_layout.addWidget(sp_lbl)

        # Update PyQtGraph Charts with real data
        self._update_charts(data)

    def _update_charts(self, data: dict):
        # 1. Plot Mood Distribution
        self.plot_mood.clear()
        dist = data.get("mood_distribution", {})
        if dist:
            moods = list(dist.keys())
            counts = list(dist.values())
            x_vals = list(range(len(moods)))

            bg_bar = pg.BarGraphItem(x=x_vals, height=counts, width=0.5, brush="#9A8BB8")
            self.plot_mood.addItem(bg_bar)

            ax = self.plot_mood.getAxis("bottom")
            ax.setTicks([[(i, m) for i, m in enumerate(moods)]])
        else:
            self.plot_mood.setTitle("No mood entries for this week")

        # 2. Plot 7-day Activity & Trend
        self.plot_activity.clear()
        trends = data.get("mood_trends", [])
        if trends:
            x_indices = list(range(len(trends)))
            conf_vals = [t.get("confidence", 0.5) * 100 for t in trends]

            # Line plot with markers
            self.plot_activity.plot(
                x_indices,
                conf_vals,
                pen=pg.mkPen("#344C59", width=2.5),
                symbol="o",
                symbolSize=8,
                symbolBrush="#9A8BB8",
            )

            ax2 = self.plot_activity.getAxis("bottom")
            # Format dates on axis
            ticks = []
            for i, t in enumerate(trends):
                d_str = t.get("date", "")[-5:]  # MM-DD
                ticks.append((i, d_str))
            ax2.setTicks([ticks])
            self.plot_activity.setYRange(0, 100)

    def _export_digest_files(self, format_type: str):
        if not self.current_report_data:
            QMessageBox.warning(self, "No Report", "Please generate a weekly digest first.")
            return

        start_d = self.start_date_picker.date().toPython()
        end_d = start_d + timedelta(days=6)

        with get_db_session() as session:
            report = (
                session.query(WeeklyReport)
                .filter(WeeklyReport.start_date == start_d, WeeklyReport.end_date == end_d)
                .first()
            )
            if not report:
                QMessageBox.warning(self, "Missing Report", "Weekly report not saved in database.")
                return
            paths = ExportService.export_weekly_report(report)

        target_file = paths["digest_md"] if format_type == "md" else paths["digest_txt"]
        QMessageBox.information(
            self,
            "Weekly Digest Exported",
            f"Successfully exported weekly digest to:\n{target_file}"
        )
