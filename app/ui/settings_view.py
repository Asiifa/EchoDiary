"""Settings view: hardware config, AI models, data storage paths, backups, and privacy controls."""
import os
import subprocess
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QScrollArea, QMessageBox, QFileDialog,
    QListWidget, QListWidgetItem, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer

from app.config import Config
from app.services.audio_recorder import AudioRecorder
from app.services.ollama_service import OllamaService
from app.services.backup_service import BackupService, BackupError


class SettingsView(QWidget):
    """Application settings, hardware management, local model verification, and privacy center."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ollama = OllamaService()
        self._init_ui()
        self.check_ollama_status()
        self.refresh_backups()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container.setObjectName("ContentArea")
        self.layout = QVBoxLayout(container)
        self.layout.setContentsMargins(18, 28, 18, 28)
        self.layout.setSpacing(22)

        # Header Row
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Settings & Privacy")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #252833;")
        sub = QLabel("Configure your audio hardware, local AI engines, data storage, and local backups.")
        sub.setStyleSheet("font-size: 13px; color: #777985;")
        sub.setWordWrap(True)
        sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        sub.setMinimumWidth(0)
        title_box.addWidget(title)
        title_box.addWidget(sub)
        self.layout.addLayout(title_box)

        # 1. Local AI Services Card (Ollama & faster-whisper)
        ai_card = QFrame()
        ai_card.setObjectName("CardFrame")
        ai_card.setStyleSheet("QFrame#CardFrame { background-color: #FFFFFF; border: 1px solid #E5E2DE; border-radius: 12px; padding: 20px; }")
        ai_layout = QVBoxLayout(ai_card)
        ai_layout.setSpacing(14)

        ai_title = QLabel("LOCAL AI CONFIGURATION")
        ai_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #777985; letter-spacing: 0.5px;")
        ai_layout.addWidget(ai_title)

        # Ollama Status Row
        ollama_row = QVBoxLayout()
        ollama_status_row = QHBoxLayout()
        ollama_lbl = QLabel("Ollama Service (127.0.0.1:11434):")
        ollama_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        ollama_lbl.setWordWrap(True)
        ollama_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        ollama_lbl.setMinimumWidth(0)
        self.ollama_status_badge = QLabel("Checking...")
        self.ollama_status_badge.setStyleSheet("background-color: #EDF2F7; color: #344C59; padding: 4px 10px; border-radius: 10px; font-weight: 600;")

        self.btn_check_ollama = QPushButton("Test Ollama Connection")
        self.btn_check_ollama.setObjectName("SecondaryButton")
        self.btn_check_ollama.setStyleSheet("padding: 6px 14px; font-weight: 500;")
        self.btn_check_ollama.clicked.connect(self.check_ollama_status)

        ollama_status_row.addWidget(ollama_lbl)
        ollama_status_row.addStretch()
        ollama_status_row.addWidget(self.ollama_status_badge)
        ollama_actions = QHBoxLayout()
        ollama_actions.addStretch()
        ollama_actions.addWidget(self.btn_check_ollama)
        ollama_row.addLayout(ollama_status_row)
        ollama_row.addLayout(ollama_actions)
        ai_layout.addLayout(ollama_row)

        # Ollama Model selection
        model_row = QHBoxLayout()
        m_lbl = QLabel("Language Model (LLM):")
        m_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        self.model_combo = QComboBox()
        self.model_combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.model_combo.setMinimumContentsLength(12)
        self.model_combo.addItem(Config.DEFAULT_OLLAMA_MODEL)
        model_row.addWidget(m_lbl)
        model_row.addWidget(self.model_combo)
        model_row.addStretch()
        ai_layout.addLayout(model_row)

        # Whisper Model selection
        whisper_row = QHBoxLayout()
        w_lbl = QLabel("Whisper STT Model:")
        w_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        self.whisper_combo = QComboBox()
        self.whisper_combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.whisper_combo.setMinimumContentsLength(18)
        self.whisper_combo.addItems(["base (Recommended, Multilingual)", "tiny (Fastest)", "small (High Accuracy)"])
        self.whisper_combo.setCurrentIndex(0)
        whisper_row.addWidget(w_lbl)
        whisper_row.addWidget(self.whisper_combo)
        whisper_row.addStretch()
        ai_layout.addLayout(whisper_row)

        self.layout.addWidget(ai_card)

        # 2. Audio Hardware Configuration Card
        audio_card = QFrame()
        audio_card.setObjectName("CardFrame")
        audio_card.setStyleSheet("QFrame#CardFrame { background-color: #FFFFFF; border: 1px solid #E5E2DE; border-radius: 12px; padding: 20px; }")
        a_layout = QVBoxLayout(audio_card)
        a_layout.setSpacing(14)

        a_title = QLabel("AUDIO HARDWARE & RECORDING")
        a_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #777985; letter-spacing: 0.5px;")
        a_layout.addWidget(a_title)

        dev_row = QHBoxLayout()
        d_lbl = QLabel("Default Microphone:")
        d_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        self.settings_dev_combo = QComboBox()
        self.settings_dev_combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.settings_dev_combo.setMinimumContentsLength(12)
        self._populate_devices()
        dev_row.addWidget(d_lbl)
        dev_row.addWidget(self.settings_dev_combo)
        dev_row.addStretch()
        a_layout.addLayout(dev_row)

        sr_row = QHBoxLayout()
        sr_lbl = QLabel("Audio Sample Rate:")
        sr_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        sr_val = QLabel("16,000 Hz Mono (Standard Speech Format)")
        sr_val.setStyleSheet("color: #777985;")
        sr_val.setWordWrap(True)
        sr_val.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        sr_val.setMinimumWidth(0)
        sr_row.addWidget(sr_lbl)
        sr_row.addWidget(sr_val)
        sr_row.addStretch()
        a_layout.addLayout(sr_row)

        self.layout.addWidget(audio_card)

        # 3. Local Data Storage & Directories
        storage_card = QFrame()
        storage_card.setObjectName("CardFrame")
        storage_card.setStyleSheet("QFrame#CardFrame { background-color: #FFFFFF; border: 1px solid #E5E2DE; border-radius: 12px; padding: 20px; }")
        s_layout = QVBoxLayout(storage_card)
        s_layout.setSpacing(12)

        s_title = QLabel("LOCAL DATA STORAGE PATHS")
        s_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #777985; letter-spacing: 0.5px;")
        s_layout.addWidget(s_title)

        # Paths
        paths = [
            ("Database File:", str(Config.DATABASE_FILE), Config.DATABASE_DIR),
            ("Audio Recordings:", str(Config.RECORDINGS_DIR), Config.RECORDINGS_DIR),
            ("Exports Directory:", str(Config.EXPORTS_DIR), Config.EXPORTS_DIR),
        ]
        for label_text, path_str, open_dir in paths:
            p_row = QHBoxLayout()
            p_lbl = QLabel(label_text)
            p_lbl.setStyleSheet("font-weight: 600; color: #344C59; min-width: 140px;")
            p_val = QLabel(path_str)
            p_val.setStyleSheet("color: #777985; font-size: 12px;")
            p_val.setWordWrap(True)
            p_val.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            p_val.setMinimumWidth(0)
            btn_open = QPushButton("Open Folder")
            btn_open.setObjectName("SecondaryButton")
            btn_open.setStyleSheet("padding: 4px 10px; font-size: 11px;")
            btn_open.clicked.connect(lambda _, d=open_dir: self._open_folder(d))

            p_row.addWidget(p_lbl)
            p_row.addWidget(p_val, stretch=1)
            p_row.addWidget(btn_open)
            s_layout.addLayout(p_row)

        self.layout.addWidget(storage_card)

        # 4. Backup & Restore Card
        backup_card = QFrame()
        backup_card.setObjectName("CardFrame")
        backup_card.setStyleSheet("QFrame#CardFrame { background-color: #FFFFFF; border: 1px solid #E5E2DE; border-radius: 12px; padding: 20px; }")
        b_layout = QVBoxLayout(backup_card)
        b_layout.setSpacing(12)

        b_header = QVBoxLayout()
        b_title = QLabel("DATABASE BACKUP & RESTORE")
        b_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #777985; letter-spacing: 0.5px;")
        b_title.setWordWrap(True)
        b_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        b_title.setMinimumWidth(0)

        self.btn_create_backup = QPushButton("+ Create Backup Now")
        self.btn_create_backup.setStyleSheet("""
            QPushButton {
                background-color: #9A8BB8;
                color: #FFFFFF;
                padding: 7px 16px;
                font-weight: 600;
                border-radius: 6px;
            }
        """)
        self.btn_create_backup.clicked.connect(self._create_backup)
        backup_action = QHBoxLayout()
        backup_action.addStretch()
        backup_action.addWidget(self.btn_create_backup)
        b_header.addWidget(b_title)
        b_header.addLayout(backup_action)
        b_layout.addLayout(b_header)

        self.backups_list = QListWidget()
        self.backups_list.setMinimumWidth(0)
        self.backups_list.setMaximumHeight(130)
        self.backups_list.setStyleSheet("border: 1px solid #E5E2DE; border-radius: 8px;")
        b_layout.addWidget(self.backups_list)

        b_btns = QVBoxLayout()
        self.btn_restore = QPushButton("Restore Selected Backup")
        self.btn_restore.setObjectName("SecondaryButton")
        self.btn_restore.setStyleSheet("padding: 6px 14px; font-weight: 600;")
        self.btn_restore.clicked.connect(self._restore_backup)

        self.btn_restore_from_file = QPushButton("Restore from ZIP File...")
        self.btn_restore_from_file.setObjectName("SecondaryButton")
        self.btn_restore_from_file.setStyleSheet("padding: 6px 14px;")
        self.btn_restore_from_file.clicked.connect(self._restore_from_file)

        b_btns.addWidget(self.btn_restore)
        b_btns.addWidget(self.btn_restore_from_file)
        b_layout.addLayout(b_btns)

        self.layout.addWidget(backup_card)

        # 5. Privacy, Security & Data Deletion
        priv_card = QFrame()
        priv_card.setObjectName("CardFrame")
        priv_card.setStyleSheet("QFrame#CardFrame { background-color: #FFFFFF; border: 1px solid #E5E2DE; border-radius: 12px; padding: 20px; }")
        pr_layout = QVBoxLayout(priv_card)
        pr_layout.setSpacing(12)

        pr_title = QLabel("PRIVACY & DATA OWNERSHIP")
        pr_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #777985; letter-spacing: 0.5px;")
        pr_layout.addWidget(pr_title)

        pr_text = QLabel(
            "<b>100% Local & Offline Privacy Guarantee:</b><br>"
            "• All diary audio recordings, transcripts, mood summaries, and tasks are stored exclusively on your local computer.<br>"
            "• Speech-to-text uses local <b>faster-whisper</b> on your CPU with int8 quantization.<br>"
            "• AI text summaries and mood analysis are processed strictly by your local <b>Ollama (qwen2.5:3b)</b> daemon.<br>"
            "• EchoDiary sends zero telemetry, zero transcripts, and zero cloud API requests."
        )
        pr_text.setStyleSheet("color: #344C59; font-size: 12px; line-height: 1.5;")
        pr_text.setWordWrap(True)
        pr_layout.addWidget(pr_text)

        danger_row = QHBoxLayout()
        danger_row.addStretch()
        self.btn_purge_data = QPushButton("Purge All Local Data & Reset")
        self.btn_purge_data.setObjectName("DangerButton")
        self.btn_purge_data.setStyleSheet("""
            QPushButton {
                background-color: #FFF5F5;
                color: #E53E3E;
                border: 1px solid #FEB2B2;
                padding: 8px 18px;
                font-weight: 600;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #FED7D7;
            }
        """)
        self.btn_purge_data.clicked.connect(self._purge_all_data)
        danger_row.addWidget(self.btn_purge_data)
        pr_layout.addLayout(danger_row)

        self.layout.addWidget(priv_card)
        self.layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _populate_devices(self):
        self.settings_dev_combo.clear()
        devs = AudioRecorder.get_input_devices()
        for d in devs:
            self.settings_dev_combo.addItem(f"{d['name']} (ID: {d['index']})", d["index"])

    def check_ollama_status(self):
        is_conn, msg, models = self.ollama.check_connection()
        if is_conn:
            self.ollama_status_badge.setText("● Connected (Local)")
            self.ollama_status_badge.setStyleSheet(
                "background-color: #EAF0E5; color: #506344; padding: 4px 10px; border-radius: 10px; font-weight: 600;"
            )
            # Update model combo
            self.model_combo.clear()
            for m in models:
                self.model_combo.addItem(m)
            if Config.DEFAULT_OLLAMA_MODEL in models:
                self.model_combo.setCurrentText(Config.DEFAULT_OLLAMA_MODEL)
        else:
            self.ollama_status_badge.setText("● Offline / Not Running")
            self.ollama_status_badge.setStyleSheet(
                "background-color: #F5E9E7; color: #8B4E4C; padding: 4px 10px; border-radius: 10px; font-weight: 600;"
            )

    def _open_folder(self, folder_path: Path):
        folder_path.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(folder_path))
            else:
                subprocess.Popen(["xdg-open", str(folder_path)])
        except Exception as e:
            QMessageBox.warning(self, "Open Folder", f"Could not open directory: {str(e)}")

    def refresh_backups(self):
        self.backups_list.clear()
        backups = BackupService.list_backups()
        if not backups:
            item = QListWidgetItem("No backups found in local backups folder.")
            item.setFlags(Qt.NoItemFlags)
            self.backups_list.addItem(item)
            return

        for b in backups:
            item = QListWidgetItem(f"📦 {b['filename']}  ({b['size_kb']} KB, {b['created_at']})")
            item.setData(Qt.UserRole, b["path"])
            self.backups_list.addItem(item)

    def _create_backup(self):
        try:
            backup_path = BackupService.create_backup()
            QMessageBox.information(
                self,
                "Backup Succeeded",
                f"Local database backup saved to:\n{backup_path.name}"
            )
            self.refresh_backups()
        except BackupError as e:
            QMessageBox.critical(self, "Backup Failed", str(e))

    def _restore_backup(self):
        selected = self.backups_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Select Backup", "Please select a backup archive to restore.")
            return

        backup_file = selected[0].data(Qt.UserRole)
        if not backup_file:
            return

        confirm = QMessageBox.warning(
            self,
            "Confirm Database Restore",
            "Restoring will overwrite your active database with the contents of the backup archive.\n\n"
            "A pre-restore safety copy will be made automatically.\n\n"
            "Do you wish to proceed?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            try:
                BackupService.restore_backup(Path(backup_file))
                QMessageBox.information(self, "Restore Completed", "Database restored successfully!")
            except BackupError as e:
                QMessageBox.critical(self, "Restore Failed", str(e))

    def _restore_from_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Backup ZIP", "", "ZIP Archives (*.zip)")
        if not path:
            return
        try:
            BackupService.restore_backup(Path(path))
            QMessageBox.information(self, "Restore Completed", "Database restored successfully from file!")
            self.refresh_backups()
        except BackupError as e:
            QMessageBox.critical(self, "Restore Failed", str(e))

    def _purge_all_data(self):
        confirm = QMessageBox.critical(
            self,
            "PERMANENT DATA DELETION",
            "DANGER: You are about to permanently delete all diary entries, recordings, and tasks.\n\n"
            "This will completely reset your local EchoDiary installation.\n\n"
            "Are you absolutely sure?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            BackupService.delete_all_data()
            from app.database import init_db
            init_db()
            QMessageBox.information(self, "Data Purged", "All personal diary data has been deleted and the database re-initialized.")
            self.refresh_backups()
