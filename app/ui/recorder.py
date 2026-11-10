"""Voice recording, audio import, local faster-whisper transcription, and AI analysis UI."""
import os
import uuid
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFileDialog, QTextEdit, QProgressBar, QFrame,
    QScrollArea, QSlider, QMessageBox, QDateEdit, QSizePolicy,
    QGridLayout
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, Slot
from PySide6.QtGui import QIcon

from app.config import Config
from app.services.audio_recorder import AudioRecorder, AudioRecorderError
from app.services.audio_player import AudioPlayer, AudioPlayerError
from app.services.transcription_service import TranscriptionService, TranscriptionError
from app.services.ollama_service import OllamaService, OllamaServiceError
from app.services.export_service import ExportService
from app.models.diary_entry import DiaryEntry
from app.models.diary_day import DiaryDay
from app.models.task import Task
from app.database import get_db_session
from app.services.diary_day_service import DiaryDayService
from app.utils.file_manager import FileManager
from app.utils.validators import validate_audio_file, AudioValidationError
from app.utils.date_utils import format_display_date, get_today_date
from app.ui.components.audio_waveform import AudioWaveformVisualizer


class TranscriptionWorker(QThread):
    """Background worker for local faster-whisper transcription."""
    progress_changed = Signal(float, str)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, audio_path: str, model_size: str, language: Optional[str] = None):
        super().__init__()
        self.audio_path = audio_path
        self.model_size = model_size
        self.language = language

    def run(self):
        try:
            service = TranscriptionService(model_size=self.model_size)
            result = service.transcribe(
                audio_file_path=self.audio_path,
                language=self.language,
                progress_callback=lambda pct, msg: self.progress_changed.emit(pct, msg)
            )
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class AnalysisWorker(QThread):
    """Background worker for local Ollama structured analysis."""
    finished = Signal(object)  # DailyAnalysisOutput
    failed = Signal(str)

    def __init__(self, transcript: str, entry_date_str: str, model_name: str):
        super().__init__()
        self.transcript = transcript
        self.entry_date_str = entry_date_str
        self.model_name = model_name

    def run(self):
        try:
            service = OllamaService(model_name=self.model_name)
            result = service.analyze_daily_entry(self.transcript, self.entry_date_str)
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class CombinedAnalysisWorker(QThread):
    """Background worker for date-level synthesis across saved recordings."""
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, transcripts: List[str], entry_date_str: str, model_name: str):
        super().__init__()
        self.transcripts = transcripts
        self.entry_date_str = entry_date_str
        self.model_name = model_name

    def run(self):
        try:
            service = OllamaService(model_name=self.model_name)
            result = service.analyze_combined_day(self.transcripts, self.entry_date_str)
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class RecorderView(QWidget):
    """Full-featured Voice Recording and Speech-to-Text Diary Entry Creation View."""

    entry_saved = Signal(str)  # Emits entry_id on successful save
    daily_analysis_updated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_entry_id = str(uuid.uuid4())
        self.recorded_audio_path: Optional[Path] = None
        self.audio_duration: float = 0.0
        self.original_transcript: str = ""
        self._combined_analysis_workers: List[CombinedAnalysisWorker] = []

        # Services
        self.recorder = AudioRecorder(level_callback=self._on_audio_level)
        self.player = AudioPlayer(
            position_callback=self._on_player_position,
            finished_callback=self._on_player_finished,
        )

        self._init_ui()
        self._populate_audio_devices()

        # UI timer for recording duration display
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_recording_timer)

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

        # 1. Header Row
        header_row = QGridLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Record Voice Diary Entry")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #252833;")
        sub = QLabel("Record through your microphone or import an audio file. All AI processing is 100% offline.")
        sub.setStyleSheet("font-size: 13px; color: #777985;")
        sub.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(sub)

        # Target entry date picker
        date_box = QHBoxLayout()
        date_lbl = QLabel("Entry Date:")
        date_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        self.date_picker = QDateEdit()
        self.date_picker.setCalendarPopup(True)
        self.date_picker.setDate(get_today_date())
        self.date_picker.setStyleSheet("padding: 6px 10px; border-radius: 6px; font-weight: 500;")
        date_box.addWidget(date_lbl)
        date_box.addWidget(self.date_picker)
        self.recorder_header_layout = header_row
        self.recorder_title_layout = title_box
        self.recorder_date_layout = date_box
        self._header_is_wide = None
        self._update_header_layout()
        self.layout.addLayout(header_row)

        # 2. Recording Station Card
        rec_card = QFrame()
        rec_card.setObjectName("CardFrame")
        rec_card.setStyleSheet("""
            QFrame#CardFrame {
                background-color: #FFFFFF;
                border: 1px solid #E5E2DE;
                border-radius: 12px;
                padding: 24px;
            }
        """)
        rec_layout = QVBoxLayout(rec_card)
        rec_layout.setSpacing(16)

        # Device selection & import toolbar
        tool_row = QGridLayout()
        tool_row.setHorizontalSpacing(10)
        tool_row.setVerticalSpacing(8)
        dev_lbl = QLabel("Microphone:")
        dev_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        self.device_combo.setMinimumWidth(130)
        self.device_combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.device_combo.setMinimumContentsLength(12)

        self.btn_refresh_devs = QPushButton("↻ Refresh")
        self.btn_refresh_devs.setObjectName("SecondaryButton")
        self.btn_refresh_devs.setStyleSheet("""
            QPushButton {
                background-color: #F5F3EF;
                color: #344C59;
                border: 1px solid #E5E2DE;
                padding: 6px 12px;
                font-weight: 500;
            }
        """)
        self.btn_refresh_devs.clicked.connect(self._populate_audio_devices)

        self.btn_import_audio = QPushButton("📁 Import Audio File...")
        self.btn_import_audio.setObjectName("SecondaryButton")
        self.btn_import_audio.setStyleSheet("""
            QPushButton {
                background-color: #F5F3EF;
                color: #344C59;
                border: 1px solid #E5E2DE;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #EFECF3;
                color: #344C59;
            }
        """)
        self.btn_import_audio.clicked.connect(self._import_audio_file)

        self.device_tool_widgets = [
            dev_lbl,
            self.device_combo,
            self.btn_refresh_devs,
            self.btn_import_audio,
        ]
        self.device_tools_layout = tool_row
        self._device_tools_columns = 0
        self._update_device_tools_layout()
        rec_layout.addLayout(tool_row)

        # Live waveform meter
        self.visualizer = AudioWaveformVisualizer(num_bars=42)
        rec_layout.addWidget(self.visualizer)

        # Timer & Status Row
        timer_box = QHBoxLayout()
        self.timer_label = QLabel("00:00")
        self.timer_label.setStyleSheet("font-size: 32px; font-weight: 700; color: #252833; letter-spacing: 1px;")

        self.status_label = QLabel("Ready to record")
        self.status_label.setStyleSheet("font-size: 13px; color: #777985; font-weight: 500;")

        timer_box.addStretch()
        t_vbox = QVBoxLayout()
        t_vbox.setAlignment(Qt.AlignCenter)
        t_vbox.addWidget(self.timer_label, alignment=Qt.AlignCenter)
        t_vbox.addWidget(self.status_label, alignment=Qt.AlignCenter)
        timer_box.addLayout(t_vbox)
        timer_box.addStretch()
        rec_layout.addLayout(timer_box)

        # Recording Control Buttons
        ctrl_row = QGridLayout()
        ctrl_row.setHorizontalSpacing(12)
        ctrl_row.setVerticalSpacing(10)

        self.btn_record = QPushButton("● Start Recording")
        self.btn_record.setStyleSheet("""
            QPushButton {
                background-color: #A65353;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: 700;
                padding: 12px 28px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #853F3F;
            }
        """)
        self.btn_record.clicked.connect(self._on_record_clicked)

        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setObjectName("SecondaryButton")
        self.btn_pause.setEnabled(False)
        self.btn_pause.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #344C59;
                border: 1px solid #E5E2DE;
                font-size: 13px;
                font-weight: 600;
                padding: 12px 22px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #F5F3EF;
            }
        """)
        self.btn_pause.clicked.connect(self._on_pause_clicked)

        self.btn_stop = QPushButton("■ Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #344C59;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 600;
                padding: 12px 22px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #252833;
            }
        """)
        self.btn_stop.clicked.connect(self._on_stop_clicked)

        self.btn_discard = QPushButton("🗑 Re-record")
        self.btn_discard.setObjectName("DangerButton")
        self.btn_discard.setEnabled(False)
        self.btn_discard.setStyleSheet("""
            QPushButton {
                background-color: #FFF5F5;
                color: #E53E3E;
                border: 1px solid #FEB2B2;
                font-size: 13px;
                font-weight: 600;
                padding: 12px 20px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #FED7D7;
            }
        """)
        self.btn_discard.clicked.connect(self._on_discard_clicked)

        self.record_control_buttons = [
            self.btn_record,
            self.btn_pause,
            self.btn_stop,
            self.btn_discard,
        ]
        self.record_controls_layout = ctrl_row
        self._record_controls_columns = 0
        self._update_record_controls_layout()
        rec_layout.addLayout(ctrl_row)

        # 3. Audio Playback Bar (Visible after audio is recorded or imported)
        self.playback_frame = QFrame()
        self.playback_frame.setStyleSheet("background-color: #F5F3EF; border-radius: 8px; padding: 12px 18px;")
        pb_layout = QHBoxLayout(self.playback_frame)
        pb_layout.setContentsMargins(0, 0, 0, 0)
        pb_layout.setSpacing(12)

        self.btn_play = QPushButton("▶ Play")
        self.btn_play.setStyleSheet("""
            QPushButton {
                background-color: #344C59;
                color: #FFFFFF;
                padding: 7px 16px;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #263A44;
            }
        """)
        self.btn_play.clicked.connect(self._toggle_playback)

        self.slider_playback = QSlider(Qt.Horizontal)
        self.slider_playback.setRange(0, 1000)
        self.slider_playback.sliderMoved.connect(self._on_slider_moved)

        self.lbl_playback_time = QLabel("00:00 / 00:00")
        self.lbl_playback_time.setStyleSheet("font-size: 12px; color: #344C59; font-weight: 600;")

        pb_layout.addWidget(self.btn_play)
        pb_layout.addWidget(self.slider_playback, stretch=1)
        pb_layout.addWidget(self.lbl_playback_time)
        self.playback_frame.setVisible(False)
        rec_layout.addWidget(self.playback_frame)

        self.layout.addWidget(rec_card)

        # 4. Speech-to-Text & Transcript Editor Card
        trans_card = QFrame()
        trans_card.setObjectName("CardFrame")
        trans_card.setStyleSheet("""
            QFrame#CardFrame {
                background-color: #FFFFFF;
                border: 1px solid #E5E2DE;
                border-radius: 12px;
                padding: 24px;
            }
        """)
        t_card_layout = QVBoxLayout(trans_card)
        t_card_layout.setSpacing(14)

        t_header = QVBoxLayout()
        title_row = QHBoxLayout()
        t_title = QLabel("Transcript & AI Review")
        t_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #252833;")
        t_sub = QLabel("faster-whisper local model extracts words; you can refine the text before AI analysis.")
        t_sub.setStyleSheet("font-size: 12px; color: #777985;")
        t_sub.setWordWrap(True)
        t_sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title_row.addWidget(t_title)
        title_row.addStretch()
        t_header.addLayout(title_row)
        t_header.addWidget(t_sub)

        self.btn_transcribe = QPushButton("Transcribe Audio (Local Whisper)")
        self.btn_transcribe.setEnabled(False)
        self.btn_transcribe.setStyleSheet("""
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
        self.btn_transcribe.clicked.connect(self._start_transcription)
        transcribe_row = QHBoxLayout()
        transcribe_row.addStretch()
        transcribe_row.addWidget(self.btn_transcribe)
        t_header.addLayout(transcribe_row)
        t_card_layout.addLayout(t_header)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        t_card_layout.addWidget(self.progress_bar)

        # Text editor
        self.transcript_edit = QTextEdit()
        self.transcript_edit.setPlaceholderText(
            "Spoken transcript will appear here automatically after transcription...\n"
            "You can review, edit, or append details before running the AI analysis."
        )
        self.transcript_edit.setMinimumHeight(140)
        t_card_layout.addWidget(self.transcript_edit)

        # Bottom action row
        bottom_row = QHBoxLayout()
        self.ai_status_label = QLabel("")
        self.ai_status_label.setStyleSheet("color: #777985; font-size: 12px; font-weight: 500;")
        bottom_row.addWidget(self.ai_status_label)
        bottom_row.addStretch()

        self.btn_analyze = QPushButton("✨ Analyze with AI & Save Entry")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setStyleSheet("""
            QPushButton {
                background-color: #344C59;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: 700;
                padding: 11px 26px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #263A44;
            }
        """)
        self.btn_analyze.clicked.connect(self._start_ai_analysis)
        bottom_row.addWidget(self.btn_analyze)
        t_card_layout.addLayout(bottom_row)

        self.layout.addWidget(trans_card)
        self.layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_header_layout()
        self._update_record_controls_layout()
        self._update_device_tools_layout()

    def _update_header_layout(self):
        if not hasattr(self, "recorder_header_layout"):
            return

        wide = self.width() >= 900
        if wide == self._header_is_wide:
            return
        self.recorder_header_layout.removeItem(self.recorder_title_layout)
        self.recorder_header_layout.removeItem(self.recorder_date_layout)
        if wide:
            self.recorder_header_layout.addLayout(self.recorder_title_layout, 0, 0)
            self.recorder_header_layout.addLayout(self.recorder_date_layout, 0, 1)
            self.recorder_header_layout.setColumnStretch(0, 1)
        else:
            self.recorder_header_layout.addLayout(self.recorder_title_layout, 0, 0)
            self.recorder_header_layout.addLayout(self.recorder_date_layout, 1, 0)
            self.recorder_header_layout.setColumnStretch(0, 1)
        self._header_is_wide = wide

    def _update_record_controls_layout(self):
        if not hasattr(self, "record_controls_layout"):
            return

        columns = 4 if self.width() >= 900 else 1
        if columns == self._record_controls_columns:
            return
        for button in self.record_control_buttons:
            self.record_controls_layout.removeWidget(button)
        for index, button in enumerate(self.record_control_buttons):
            self.record_controls_layout.addWidget(
                button, index // columns, index % columns
            )
        self._record_controls_columns = columns

    def _update_device_tools_layout(self):
        if not hasattr(self, "device_tools_layout"):
            return

        columns = 4 if self.width() >= 900 else 2
        if columns == self._device_tools_columns:
            return
        for widget in self.device_tool_widgets:
            self.device_tools_layout.removeWidget(widget)
        if columns == 4:
            positions = [(0, 0), (0, 1), (0, 2), (0, 3)]
        else:
            positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        for widget, (row, column) in zip(self.device_tool_widgets, positions):
            self.device_tools_layout.addWidget(widget, row, column)
        self.device_tools_layout.setColumnStretch(1, 1)
        self._device_tools_columns = columns

    def _populate_audio_devices(self):
        self.device_combo.clear()
        devices = AudioRecorder.get_input_devices()
        default_idx = 0
        for i, dev in enumerate(devices):
            name = dev["name"]
            idx = dev["index"]
            self.device_combo.addItem(f"{name} ({idx})", idx)
            if dev.get("is_default"):
                default_idx = i

        if devices:
            self.device_combo.setCurrentIndex(default_idx)

    def _on_device_changed(self, index: int):
        dev_id = self.device_combo.currentData()
        self.recorder.set_device(dev_id)

    def _on_audio_level(self, level: float):
        """Called from audio callback thread."""
        self.visualizer.update_level(level)

    def _on_record_clicked(self):
        try:
            self.active_entry_id = str(uuid.uuid4())
            self.recorder.start_recording()
            self.timer.start(250)
            self.status_label.setText("Recording in progress... (Speak clearly into your microphone)")
            self.status_label.setStyleSheet("color: #C53030; font-weight: 600;")
            self.btn_record.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_stop.setEnabled(True)
            self.btn_discard.setEnabled(True)
            self.btn_import_audio.setEnabled(False)
            self.btn_transcribe.setEnabled(False)
            self.playback_frame.setVisible(False)
        except AudioRecorderError as e:
            QMessageBox.critical(self, "Recording Error", str(e))

    def _on_pause_clicked(self):
        if self.recorder.state == AudioRecorder.STATE_RECORDING:
            self.recorder.pause_recording()
            self.btn_pause.setText("▶ Resume")
            self.status_label.setText("Recording paused")
            self.status_label.setStyleSheet("color: #D97706; font-weight: 600;")
        elif self.recorder.state == AudioRecorder.STATE_PAUSED:
            self.recorder.resume_recording()
            self.btn_pause.setText("⏸ Pause")
            self.status_label.setText("Recording in progress...")
            self.status_label.setStyleSheet("color: #C53030; font-weight: 600;")

    def _on_stop_clicked(self):
        self.timer.stop()
        duration = self.recorder.stop_recording()
        self.audio_duration = duration

        self.btn_record.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setText("⏸ Pause")
        self.btn_stop.setEnabled(False)
        self.btn_discard.setEnabled(True)
        self.btn_import_audio.setEnabled(True)

        if duration < 0.5:
            QMessageBox.warning(self, "Recording Too Short", "The recording was less than 1 second. Please record a bit longer.")
            self._reset_recording_state()
            return

        # Save audio file to structured path
        entry_date = self.date_picker.date().toPython()
        save_path = FileManager.get_recording_path(entry_date, self.active_entry_id, ext=".wav")
        try:
            self.recorded_audio_path = self.recorder.save_to_file(save_path)
            self.status_label.setText(f"Recording stopped. Captured {round(duration, 1)} seconds.")
            self.status_label.setStyleSheet("color: #16A34A; font-weight: 600;")
            self._setup_playback(str(self.recorded_audio_path))
            self.btn_transcribe.setEnabled(True)
        except AudioRecorderError as e:
            QMessageBox.critical(self, "File Save Error", str(e))
            self._reset_recording_state()

    def _on_discard_clicked(self):
        reply = QMessageBox.question(
            self,
            "Confirm Re-record",
            "Are you sure you want to discard this recording and start over?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._reset_recording_state()

    def _reset_recording_state(self):
        self.timer.stop()
        self.player.stop()
        self.recorder.cancel_recording()
        self.visualizer.reset()
        self.timer_label.setText("00:00")
        self.status_label.setText("Ready to record")
        self.status_label.setStyleSheet("color: #777985;")
        self.btn_record.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_discard.setEnabled(False)
        self.btn_import_audio.setEnabled(True)
        self.btn_transcribe.setEnabled(False)
        self.playback_frame.setVisible(False)
        self.recorded_audio_path = None
        self.audio_duration = 0.0

    def _update_recording_timer(self):
        sec = int(self.recorder.get_duration())
        mins = sec // 60
        secs = sec % 60
        self.timer_label.setText(f"{mins:02d}:{secs:02d}")

    def _import_audio_file(self):
        file_filter = "Audio Files (*.wav *.mp3 *.m4a *.flac *.ogg);;All Files (*.*)"
        path, _ = QFileDialog.getOpenFileName(self, "Import Audio File", "", file_filter)
        if not path:
            return

        try:
            validation = validate_audio_file(path)
            src_path = Path(path)
            entry_date = self.date_picker.date().toPython()
            self.active_entry_id = str(uuid.uuid4())

            # Copy safely into our local recordings folder
            dest_path = FileManager.get_recording_path(entry_date, self.active_entry_id, ext=src_path.suffix.lower())
            FileManager.copy_file_safe(src_path, dest_path)

            self.recorded_audio_path = dest_path
            self.audio_duration = validation["duration_seconds"]

            sec = int(self.audio_duration)
            mins = sec // 60
            secs = sec % 60
            self.timer_label.setText(f"{mins:02d}:{secs:02d}")
            self.status_label.setText(f"Imported '{src_path.name}' ({round(self.audio_duration, 1)}s)")
            self.status_label.setStyleSheet("color: #16A34A; font-weight: 600;")

            self._setup_playback(str(dest_path))
            self.btn_discard.setEnabled(True)
            self.btn_transcribe.setEnabled(True)

        except AudioValidationError as e:
            QMessageBox.critical(self, "Invalid Audio File", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import audio: {str(e)}")

    def _setup_playback(self, file_path: str):
        try:
            dur = self.player.load(file_path)
            self.slider_playback.setValue(0)
            self.lbl_playback_time.setText(f"00:00 / {self._format_seconds(dur)}")
            self.btn_play.setText("▶ Play")
            self.playback_frame.setVisible(True)
        except Exception as e:
            QMessageBox.warning(self, "Playback Setup", f"Could not initialize audio playback: {str(e)}")

    def _toggle_playback(self):
        if self.player.state == AudioPlayer.STATE_PLAYING:
            self.player.pause()
            self.btn_play.setText("▶ Play")
        elif self.player.state == AudioPlayer.STATE_PAUSED:
            self.player.resume()
            self.btn_play.setText("⏸ Pause")
        else:
            self.player.play(from_start=False)
            self.btn_play.setText("⏸ Pause")

    def _on_player_position(self, current: float, total: float):
        if total > 0:
            pct = int((current / total) * 1000)
            self.slider_playback.setValue(pct)
            self.lbl_playback_time.setText(f"{self._format_seconds(current)} / {self._format_seconds(total)}")

    def _on_player_finished(self):
        self.btn_play.setText("▶ Play")
        self.slider_playback.setValue(0)

    def _on_slider_moved(self, value: int):
        target_sec = (value / 1000.0) * self.player.duration
        self.player.seek(target_sec)

    @staticmethod
    def _format_seconds(s: float) -> str:
        sec = int(s)
        return f"{sec // 60:02d}:{sec % 60:02d}"

    def _start_transcription(self):
        if not self.recorded_audio_path or not self.recorded_audio_path.exists():
            QMessageBox.warning(self, "Missing Audio", "No audio file available to transcribe.")
            return

        self.btn_transcribe.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10)
        self.ai_status_label.setText("Starting offline transcription with faster-whisper...")

        self.trans_worker = TranscriptionWorker(
            audio_path=str(self.recorded_audio_path),
            model_size=Config.DEFAULT_WHISPER_MODEL,
        )
        self.trans_worker.progress_changed.connect(self._on_transcription_progress)
        self.trans_worker.finished.connect(self._on_transcription_finished)
        self.trans_worker.failed.connect(self._on_transcription_failed)
        self.trans_worker.start()

    def _on_transcription_progress(self, pct: float, msg: str):
        self.progress_bar.setValue(int(pct * 100))
        self.ai_status_label.setText(msg)

    def _on_transcription_finished(self, result: dict):
        self.progress_bar.setVisible(False)
        self.btn_transcribe.setEnabled(True)

        full_text = result.get("text", "")
        detected_lang = result.get("language", "en")
        prob = result.get("language_probability", 1.0)

        self.original_transcript = full_text
        self.transcript_edit.setText(full_text)
        self.ai_status_label.setText(f"✓ Transcribed in language: {detected_lang} (Confidence: {int(prob * 100)}%)")
        self.btn_analyze.setEnabled(bool(full_text.strip()))

    def _on_transcription_failed(self, error_msg: str):
        self.progress_bar.setVisible(False)
        self.btn_transcribe.setEnabled(True)
        self.ai_status_label.setText("Transcription failed.")
        QMessageBox.critical(self, "Transcription Error", f"Faster-Whisper encountered an error:\n{error_msg}")

    def _start_ai_analysis(self):
        edited_text = self.transcript_edit.toPlainText().strip()
        if not edited_text:
            QMessageBox.warning(self, "Empty Transcript", "Please transcribe or write diary content before analyzing.")
            return

        entry_date = self.date_picker.date().toPython()

        # Check for duplicate entry on the same date
        with get_db_session() as session:
            existing = session.query(DiaryEntry).filter(
                DiaryEntry.entry_date == entry_date,
                DiaryEntry.is_deleted == False
            ).first()

            if existing:
                reply = QMessageBox.question(
                    self,
                    "Duplicate Entry Date",
                    f"A diary entry for {format_display_date(entry_date)} already exists.\n\n"
                    "Would you like to save this as an additional entry for today?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

        self.btn_analyze.setEnabled(False)
        self.ai_status_label.setText("Sending transcript to local Ollama (qwen2.5:3b)...")

        self.analysis_worker = AnalysisWorker(
            transcript=edited_text,
            entry_date_str=entry_date.isoformat(),
            model_name=Config.DEFAULT_OLLAMA_MODEL,
        )
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.failed.connect(self._on_analysis_failed)
        self.analysis_worker.start()

    def _on_analysis_finished(self, analysis_result):
        self.btn_analyze.setEnabled(True)
        self.ai_status_label.setText("✓ Analysis complete. Saving entry locally...")

        entry_date = self.date_picker.date().toPython()
        edited_text = self.transcript_edit.toPlainText().strip()

        # Save to SQLite
        try:
            with get_db_session() as session:
                day = DiaryDayService.get_or_create(session, entry_date)
                entry = DiaryEntry(
                    id=self.active_entry_id,
                    entry_date=entry_date,
                    diary_day_id=day.id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    audio_file_path=str(self.recorded_audio_path) if self.recorded_audio_path else None,
                    duration_seconds=self.audio_duration,
                    original_transcript=self.original_transcript,
                    edited_transcript=edited_text,
                    summary_line_1=analysis_result.summary[0] if len(analysis_result.summary) > 0 else "",
                    summary_line_2=analysis_result.summary[1] if len(analysis_result.summary) > 1 else "",
                    summary_line_3=analysis_result.summary[2] if len(analysis_result.summary) > 2 else "",
                    primary_mood=analysis_result.primary_mood,
                    secondary_mood=analysis_result.secondary_mood,
                    mood_confidence=analysis_result.mood_confidence,
                    mood_evidence=analysis_result.mood_evidence,
                )
                entry.topics = analysis_result.topics
                entry.highlights = analysis_result.highlights
                session.add(entry)
                session.flush()

                # Add extracted tasks
                for item in analysis_result.tasks:
                    from app.utils.date_utils import parse_date
                    due_d = parse_date(item.due_date) if item.due_date else None
                    task = Task(
                        diary_entry_id=entry.id,
                        diary_day_id=day.id,
                        description=item.description,
                        due_date=due_d,
                        priority=item.priority,
                        status="Pending",
                        created_at=datetime.utcnow(),
                    )
                    session.add(task)
                session.flush()

                # Export required files
                ExportService.export_daily_entry(entry)
                day_id = day.id
                day_recordings = (
                    session.query(DiaryEntry)
                    .filter(
                        DiaryEntry.diary_day_id == day_id,
                        DiaryEntry.is_deleted == False,
                    )
                    .order_by(DiaryEntry.created_at.asc(), DiaryEntry.id.asc())
                    .all()
                )
                transcripts = [record.effective_transcript for record in day_recordings]

            QMessageBox.information(
                self,
                "Diary Entry Saved",
                f"Your diary entry for {format_display_date(entry_date)} has been saved successfully!\n\n"
                f"• Mood: {analysis_result.primary_mood}\n"
                f"• Tasks Extracted: {len(analysis_result.tasks)}\n"
                f"• Daily exports generated in exports/daily/"
            )

            # Signal completion and reset recorder
            saved_id = self.active_entry_id
            self._reset_recording_state()
            self.transcript_edit.clear()
            self.ai_status_label.setText("")
            self.entry_saved.emit(saved_id)
            self._start_combined_analysis(day_id, entry_date.isoformat(), transcripts)

        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save entry to database: {str(e)}")

    def _start_combined_analysis(
        self, day_id: str, entry_date_str: str, transcripts: List[str]
    ) -> None:
        self.ai_status_label.setText("Updating combined analysis for this date...")
        self.combined_analysis_worker = CombinedAnalysisWorker(
            transcripts=transcripts,
            entry_date_str=entry_date_str,
            model_name=Config.DEFAULT_OLLAMA_MODEL,
        )
        self.combined_analysis_worker.setParent(self)
        worker = self.combined_analysis_worker
        self._combined_analysis_workers.append(worker)
        self.combined_analysis_worker.finished.connect(
            lambda result, target_day_id=day_id, target_date=entry_date_str,
            analyzed_transcripts=transcripts, target_worker=worker:
            self._on_combined_analysis_finished(
                target_day_id,
                target_date,
                analyzed_transcripts,
                target_worker,
                result,
            )
        )
        self.combined_analysis_worker.failed.connect(
            lambda error, target_day_id=day_id, target_date=entry_date_str,
            analyzed_transcripts=transcripts, target_worker=worker:
            self._on_combined_analysis_failed(
                target_day_id,
                target_date,
                analyzed_transcripts,
                target_worker,
                error,
            )
        )
        self.combined_analysis_worker.start()

    def _on_combined_analysis_finished(
        self,
        day_id: str,
        entry_date_str: str,
        analyzed_transcripts: List[str],
        worker: CombinedAnalysisWorker,
        analysis_result,
    ) -> None:
        self._release_combined_analysis_worker(worker)
        try:
            with get_db_session() as session:
                day = session.query(DiaryDay).filter(DiaryDay.id == day_id).first()
                if day is None:
                    raise ValueError(f"Diary day {entry_date_str} no longer exists.")
                current_transcripts = [
                    record.effective_transcript
                    for record in session.query(DiaryEntry)
                    .filter(
                        DiaryEntry.diary_day_id == day_id,
                        DiaryEntry.is_deleted == False,
                    )
                    .order_by(DiaryEntry.created_at.asc(), DiaryEntry.id.asc())
                    .all()
                ]
                if current_transcripts != analyzed_transcripts:
                    if current_transcripts:
                        self._start_combined_analysis(
                            day_id, entry_date_str, current_transcripts
                        )
                    return
                DiaryDayService.update_analysis(session, day, analysis_result)
            self.ai_status_label.setText("✓ Combined daily analysis updated.")
            self.daily_analysis_updated.emit(entry_date_str)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Combined Analysis Save Error",
                f"The recording was saved, but its combined daily analysis could not be saved:\n{error}",
            )

    def _on_combined_analysis_failed(
        self,
        day_id: str,
        entry_date_str: str,
        analyzed_transcripts: List[str],
        worker: CombinedAnalysisWorker,
        error_msg: str,
    ) -> None:
        self._release_combined_analysis_worker(worker)
        with get_db_session() as session:
            current_transcripts = [
                record.effective_transcript
                for record in session.query(DiaryEntry)
                .filter(
                    DiaryEntry.diary_day_id == day_id,
                    DiaryEntry.is_deleted == False,
                )
                .order_by(DiaryEntry.created_at.asc(), DiaryEntry.id.asc())
                .all()
            ]
        if current_transcripts != analyzed_transcripts:
            if current_transcripts:
                self._start_combined_analysis(
                    day_id, entry_date_str, current_transcripts
                )
            return
        self.ai_status_label.setText("Combined daily analysis could not be updated.")
        QMessageBox.warning(
            self,
            "Combined Analysis Error",
            "The recording was saved and its individual analysis is available, but "
            f"the combined analysis for this date failed:\n{error_msg}",
        )

    def _release_combined_analysis_worker(
        self, worker: CombinedAnalysisWorker
    ) -> None:
        worker.wait()
        if worker in self._combined_analysis_workers:
            self._combined_analysis_workers.remove(worker)

    def _on_analysis_failed(self, error_msg: str):
        self.btn_analyze.setEnabled(True)
        self.ai_status_label.setText("AI analysis failed.")
        QMessageBox.critical(
            self,
            "Ollama Analysis Error",
            f"Local AI analysis failed:\n{error_msg}\n\n"
            "Ensure Ollama is running at 127.0.0.1:11434 and model 'qwen2.5:3b' is installed."
        )
