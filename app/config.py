"""Application configuration and directory management."""
import os
import sys
from pathlib import Path
from typing import List


class Config:
    """Application-wide configuration parameters and directory resolvers."""

    APP_NAME: str = "EchoDiary"
    APP_VERSION: str = "1.0.0"

    # Default paths
    # If ECHODIARY_DATA_DIR env var is set, use it; otherwise use Windows LocalAppData or User Home
    _custom_dir = os.environ.get("ECHODIARY_DATA_DIR")
    if _custom_dir:
        BASE_DATA_DIR = Path(_custom_dir).resolve()
    elif os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            BASE_DATA_DIR = Path(local_app_data) / APP_NAME
        else:
            BASE_DATA_DIR = Path.home() / f".{APP_NAME.lower()}"
    else:
        BASE_DATA_DIR = Path.home() / f".{APP_NAME.lower()}"

    DATABASE_DIR = BASE_DATA_DIR / "database"
    RECORDINGS_DIR = BASE_DATA_DIR / "recordings"
    EXPORTS_DIR = BASE_DATA_DIR / "exports"
    EXPORTS_DAILY_DIR = EXPORTS_DIR / "daily"
    EXPORTS_WEEKLY_DIR = EXPORTS_DIR / "weekly"
    BACKUPS_DIR = BASE_DATA_DIR / "backups"
    LOGS_DIR = BASE_DATA_DIR / "logs"

    DATABASE_FILE = DATABASE_DIR / "echodiary.db"
    DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

    # Audio defaults
    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_CHANNELS: int = 1
    AUDIO_SUBTYPE: str = "PCM_16"
    AUDIO_FORMAT: str = "WAV"
    SUPPORTED_AUDIO_EXTENSIONS: tuple = (".wav", ".mp3", ".m4a", ".flac", ".ogg")

    # Speech recognition defaults
    DEFAULT_WHISPER_MODEL: str = "base"
    WHISPER_MODELS: List[str] = ["tiny", "base", "small"]
    DEFAULT_WHISPER_DEVICE: str = "cpu"
    DEFAULT_WHISPER_COMPUTE_TYPE: str = "int8"
    DEFAULT_LANGUAGE: str = "auto"

    # Ollama defaults
    OLLAMA_HOST: str = "http://127.0.0.1:11434"
    DEFAULT_OLLAMA_MODEL: str = "qwen2.5:3b"
    OLLAMA_REQUEST_TIMEOUT: int = 90  # seconds

    # Domain constants
    SUPPORTED_MOODS: List[str] = [
        "Happy",
        "Excited",
        "Calm",
        "Grateful",
        "Neutral",
        "Stressed",
        "Sad",
        "Frustrated",
        "Mixed",
        "Uncertain",
    ]

    TASK_PRIORITIES: List[str] = ["Low", "Medium", "High"]
    TASK_STATUSES: List[str] = ["Pending", "Completed"]

    @classmethod
    def ensure_directories(cls) -> None:
        """Create all required directories if they do not exist."""
        cls.BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.DATABASE_DIR.mkdir(parents=True, exist_ok=True)
        cls.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        cls.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.EXPORTS_DAILY_DIR.mkdir(parents=True, exist_ok=True)
        cls.EXPORTS_WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
        cls.BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)

