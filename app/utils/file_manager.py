"""File management, path resolution, atomic writes, and local storage utilities."""
import os
import shutil
import json
import tempfile
from pathlib import Path
from datetime import date
from typing import Dict, Any, Optional
from app.config import Config


class FileManager:
    """Manages files, structured directory paths, and safe atomic writes."""

    @staticmethod
    def get_recording_path(entry_date: date, entry_id: str, ext: str = ".wav") -> Path:
        """
        Generate structured path for recording:
        EchoDiary/recordings/YYYY/MM/YYYY-MM-DD_{entry_id[:8]}.wav
        """
        year_str = str(entry_date.year)
        month_str = f"{entry_date.month:02d}"
        dir_path = Config.RECORDINGS_DIR / year_str / month_str
        dir_path.mkdir(parents=True, exist_ok=True)

        prefix = entry_date.strftime("%Y-%m-%d")
        clean_ext = ext if ext.startswith(".") else f".{ext}"
        filename = f"{prefix}_{entry_id[:8]}{clean_ext}"
        return dir_path / filename

    @staticmethod
    def get_daily_export_paths(entry_date: date, custom_dir: Optional[Path] = None) -> Dict[str, Path]:
        """
        Generate export paths for a daily entry:
        - YYYY-MM-DD_diary.txt
        - YYYY-MM-DD_summary.txt
        - YYYY-MM-DD_tasks.txt
        - YYYY-MM-DD_entry.json
        """
        base_dir = custom_dir or Config.EXPORTS_DAILY_DIR
        base_dir.mkdir(parents=True, exist_ok=True)
        prefix = entry_date.strftime("%Y-%m-%d")

        return {
            "diary_txt": base_dir / f"{prefix}_diary.txt",
            "summary_txt": base_dir / f"{prefix}_summary.txt",
            "tasks_txt": base_dir / f"{prefix}_tasks.txt",
            "entry_json": base_dir / f"{prefix}_entry.json",
        }

    @staticmethod
    def get_weekly_export_paths(start_date: date, end_date: date, custom_dir: Optional[Path] = None) -> Dict[str, Path]:
        """
        Generate export paths for weekly digest:
        - YYYY-MM-DD_weekly_digest.md
        - YYYY-MM-DD_weekly_digest.txt
        """
        base_dir = custom_dir or Config.EXPORTS_WEEKLY_DIR
        base_dir.mkdir(parents=True, exist_ok=True)
        prefix = f"{start_date.strftime('%Y-%m-%d')}_to_{end_date.strftime('%Y-%m-%d')}"

        return {
            "digest_md": base_dir / f"{prefix}_weekly_digest.md",
            "digest_txt": base_dir / f"{prefix}_weekly_digest.txt",
        }

    @staticmethod
    def atomic_write_text(file_path: Path, content: str, encoding: str = "utf-8") -> None:
        """Write content to file atomically using a temporary file in the same directory."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # Create temp file in the same directory to allow atomic os.replace on the same filesystem
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(file_path.parent),
            delete=False,
            encoding=encoding,
        )
        try:
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()
            os.replace(temp_file.name, str(file_path))
        except Exception:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)
            raise

    @staticmethod
    def atomic_write_json(file_path: Path, data: Any, indent: int = 2) -> None:
        """Write json data atomically."""
        serialized = json.dumps(data, indent=indent, default=str, ensure_ascii=False)
        FileManager.atomic_write_text(file_path, serialized)

    @staticmethod
    def copy_file_safe(src: Path, dest: Path) -> Path:
        """Safely copy file, ensuring destination directory exists."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        return Path(shutil.copy2(str(src), str(dest)))

    @staticmethod
    def check_disk_space(directory: Path, min_mb: int = 50) -> bool:
        """Check if target directory has at least min_mb megabytes available."""
        try:
            total, used, free = shutil.disk_usage(str(directory))
            free_mb = free / (1024 * 1024)
            return free_mb >= min_mb
        except Exception:
            return True  # Fallback to true if cannot check

