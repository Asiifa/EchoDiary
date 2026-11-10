"""Backup, restore, and local data lifecycle management service."""
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any
from app.config import Config


class BackupError(Exception):
    """Exception raised for backup/restore failures."""
    pass


class BackupService:
    """Manages database backups, restores, and data purge operations."""

    @staticmethod
    def create_backup(target_dir: Optional[Path] = None, include_recordings: bool = False) -> Path:
        """
        Create a timestamped zip archive of the SQLite database and settings.
        Returns the path of the created backup file.
        """
        backup_folder = target_dir or Config.BACKUPS_DIR
        backup_folder.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"EchoDiary_backup_{timestamp}.zip"
        backup_path = backup_folder / backup_filename

        db_file = Config.DATABASE_FILE
        if not db_file.exists():
            raise BackupError("No database file found to back up.")

        try:
            with zipfile.ZipFile(str(backup_path), "w", zipfile.ZIP_DEFLATED) as zf:
                # Add database
                zf.write(str(db_file), arcname="database/echodiary.db")

                if include_recordings and Config.RECORDINGS_DIR.exists():
                    for root, _, files in os.walk(Config.RECORDINGS_DIR):
                        for file in files:
                            file_path = Path(root) / file
                            arc_name = file_path.relative_to(Config.BASE_DATA_DIR)
                            zf.write(str(file_path), arcname=str(arc_name))

            return backup_path
        except Exception as e:
            if backup_path.exists():
                backup_path.unlink()
            raise BackupError(f"Backup creation failed: {str(e)}")

    @staticmethod
    def restore_backup(backup_path: Path) -> bool:
        """
        Restore the database from a verified zip backup file.
        Creates a pre-restore safety copy of the current database first.
        """
        backup_path = Path(backup_path)
        if not backup_path.exists():
            raise BackupError(f"Backup file not found: {backup_path}")

        if not zipfile.is_zipfile(str(backup_path)):
            raise BackupError("Selected file is not a valid zip archive.")

        db_file = Config.DATABASE_FILE
        safety_copy = None
        if db_file.exists():
            safety_copy = db_file.with_suffix(".db.pre_restore_bak")
            shutil.copy2(str(db_file), str(safety_copy))

        try:
            with zipfile.ZipFile(str(backup_path), "r") as zf:
                file_list = zf.namelist()
                db_entries = [f for f in file_list if f.endswith("echodiary.db")]
                if not db_entries:
                    raise BackupError("Archive does not contain a valid 'echodiary.db' file.")

                # Extract to temp directory first
                temp_extract_dir = Config.BACKUPS_DIR / "temp_restore"
                temp_extract_dir.mkdir(parents=True, exist_ok=True)
                zf.extract(db_entries[0], str(temp_extract_dir))

                extracted_db = temp_extract_dir / db_entries[0]
                # Replace active database
                shutil.copy2(str(extracted_db), str(db_file))
                shutil.rmtree(str(temp_extract_dir), ignore_errors=True)

            # Cleanup safety copy after success
            if safety_copy and safety_copy.exists():
                safety_copy.unlink()
            return True

        except Exception as e:
            # Rollback to safety copy
            if safety_copy and safety_copy.exists():
                shutil.copy2(str(safety_copy), str(db_file))
                safety_copy.unlink()
            raise BackupError(f"Restore failed: {str(e)}")

    @staticmethod
    def list_backups(backup_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
        """List available backups with file sizes and creation times."""
        folder = backup_dir or Config.BACKUPS_DIR
        if not folder.exists():
            return []
        backups = []
        for f in folder.glob("*.zip"):
            stat = f.stat()
            backups.append({
                "path": str(f.resolve()),
                "filename": f.name,
                "size_kb": round(stat.st_size / 1024, 1),
                "created_at": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
            })
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups

    @staticmethod
    def delete_all_data() -> None:
        """
        Purge all local diary entries, database tables, and recordings.
        """
        # Remove database
        if Config.DATABASE_FILE.exists():
            Config.DATABASE_FILE.unlink()

        # Remove recordings
        if Config.RECORDINGS_DIR.exists():
            shutil.rmtree(str(Config.RECORDINGS_DIR), ignore_errors=True)
            Config.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

        # Remove exports
        if Config.EXPORTS_DIR.exists():
            shutil.rmtree(str(Config.EXPORTS_DIR), ignore_errors=True)
            Config.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
            Config.EXPORTS_DAILY_DIR.mkdir(parents=True, exist_ok=True)
            Config.EXPORTS_WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
