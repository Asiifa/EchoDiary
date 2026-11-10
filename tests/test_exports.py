"""Tests for daily and weekly file export generators and backup utilities."""
import json
from datetime import date
from pathlib import Path
from app.models.diary_entry import DiaryEntry
from app.models.task import Task
from app.models.weekly_report import WeeklyReport
from app.services.export_service import ExportService
from app.services.backup_service import BackupService
from app.utils.file_manager import FileManager


def test_daily_entry_file_exports(temp_dir):
    """Verify all four daily export files are created atomically with correct content."""
    entry = DiaryEntry(
        entry_date=date(2026, 11, 9),
        original_transcript="Spoken voice transcript here.",
        edited_transcript="Edited polished voice transcript here.",
        duration_seconds=45.2,
        summary_line_1="Line 1: Attended class.",
        summary_line_2="Line 2: Finished assignment.",
        summary_line_3="Line 3: Prepared dinner.",
        primary_mood="Grateful",
        secondary_mood="Calm",
        mood_confidence=0.92,
        mood_evidence="Expressed appreciation for help received.",
    )
    task = Task(description="Email professor", priority="High", status="Pending")
    entry.tasks.append(task)

    export_paths = ExportService.export_daily_entry(entry, custom_dir=temp_dir)

    # 1. Diary txt
    assert export_paths["diary_txt"].exists()
    diary_content = export_paths["diary_txt"].read_text(encoding="utf-8")
    assert "ECHODIARY - DAILY ENTRY" in diary_content
    assert "Edited polished voice transcript here." in diary_content
    assert "Primary Mood: Grateful" in diary_content

    # 2. Summary txt
    assert export_paths["summary_txt"].exists()
    summary_content = export_paths["summary_txt"].read_text(encoding="utf-8")
    assert "Line 1: Attended class." in summary_content
    assert "Line 2: Finished assignment." in summary_content

    # 3. Tasks txt
    assert export_paths["tasks_txt"].exists()
    tasks_content = export_paths["tasks_txt"].read_text(encoding="utf-8")
    assert "Email professor" in tasks_content
    assert "[HIGH]" in tasks_content

    # 4. JSON export
    assert export_paths["entry_json"].exists()
    parsed_json = json.loads(export_paths["entry_json"].read_text(encoding="utf-8"))
    assert parsed_json["primary_mood"] == "Grateful"
    assert len(parsed_json["summary"]) == 3
    assert len(parsed_json["tasks"]) == 1


def test_weekly_report_file_exports(temp_dir):
    """Verify weekly Markdown and TXT digest exports are created."""
    report = WeeklyReport(
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 8),
        overview="A very productive week with multiple milestones reached.",
        highlights_json=json.dumps(["Launched research phase", "Passed quiz"]),
        accomplishments_json=json.dumps(["Completed 5 tasks"]),
        main_topics_json=json.dumps(["AI", "Databases"]),
        mood_distribution_json=json.dumps({"Happy": 4, "Calm": 3}),
        recurring_themes_json=json.dumps(["Focus"]),
        suggested_priorities_json=json.dumps(["Prepare final draft"]),
        is_partial_week=False,
        entries_count=7,
    )

    paths = ExportService.export_weekly_report(report, custom_dir=temp_dir)

    # Markdown
    assert paths["digest_md"].exists()
    md_content = paths["digest_md"].read_text(encoding="utf-8")
    assert "# EchoDiary Weekly Digest" in md_content
    assert "Full Week (7/7 entries logged)" in md_content
    assert "Launched research phase" in md_content

    # TXT
    assert paths["digest_txt"].exists()
    txt_content = paths["digest_txt"].read_text(encoding="utf-8")
    assert "ECHODIARY WEEKLY DIGEST" in txt_content
    assert "Happy: 4" in txt_content


def test_atomic_file_write(temp_dir):
    """Verify atomic write utility writes safely without corruption."""
    target_file = temp_dir / "safe_atomic.txt"
    content = "Atomic file content verification."
    FileManager.atomic_write_text(target_file, content)
    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8") == content

