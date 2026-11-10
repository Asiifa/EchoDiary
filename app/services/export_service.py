"""Export service for daily entries, weekly digests, and task lists."""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import date

from app.models.diary_entry import DiaryEntry
from app.models.weekly_report import WeeklyReport
from app.models.task import Task
from app.utils.file_manager import FileManager
from app.utils.date_utils import format_display_date


class ExportService:
    """Manages file exports in Markdown, TXT, and JSON formats."""

    @staticmethod
    def export_daily_entry(entry: DiaryEntry, custom_dir: Optional[Path] = None) -> Dict[str, Path]:
        """
        Generate all required daily export files:
        1. YYYY-MM-DD_diary.txt
        2. YYYY-MM-DD_summary.txt
        3. YYYY-MM-DD_tasks.txt
        4. YYYY-MM-DD_entry.json
        """
        paths = FileManager.get_daily_export_paths(entry.entry_date, custom_dir)

        # 1. Diary text (full transcript and mood)
        diary_content = (
            f"ECHODIARY - DAILY ENTRY\n"
            f"Date: {format_display_date(entry.entry_date)} ({entry.entry_date})\n"
            f"Duration: {entry.duration_seconds}s\n"
            f"Primary Mood: {entry.primary_mood} (Confidence: {int(entry.mood_confidence * 100)}%)\n"
            f"Secondary Mood: {entry.secondary_mood or 'None'}\n"
            f"Evidence: {entry.mood_evidence or 'N/A'}\n"
            f"{'='*60}\n\n"
            f"EDITED TRANSCRIPT:\n{entry.effective_transcript}\n\n"
            f"{'='*60}\n"
            f"ORIGINAL TRANSCRIPT:\n{entry.original_transcript}\n"
        )
        FileManager.atomic_write_text(paths["diary_txt"], diary_content)

        # 2. Three-line summary text
        summary_lines = entry.summary_lines
        summary_body = "\n".join(f"{i+1}. {line}" for i, line in enumerate(summary_lines))
        summary_content = (
            f"ECHODIARY - THREE-LINE SUMMARY\n"
            f"Date: {format_display_date(entry.entry_date)}\n"
            f"Primary Mood: {entry.primary_mood}\n"
            f"{'-'*40}\n"
            f"{summary_body}\n"
        )
        FileManager.atomic_write_text(paths["summary_txt"], summary_content)

        # 3. Tasks text
        tasks_lines = []
        if entry.tasks:
            for t in entry.tasks:
                status_box = "[X]" if t.status == "Completed" else "[ ]"
                due_info = f" (Due: {t.due_date})" if t.due_date else ""
                tasks_lines.append(f"{status_box} [{t.priority.upper()}] {t.description}{due_info}")
        else:
            tasks_lines.append("No actionable tasks recorded for this entry.")

        tasks_content = (
            f"ECHODIARY - ACTIONABLE TO-DO ITEMS\n"
            f"Date: {format_display_date(entry.entry_date)}\n"
            f"{'-'*40}\n" + "\n".join(tasks_lines) + "\n"
        )
        FileManager.atomic_write_text(paths["tasks_txt"], tasks_content)

        # 4. Structured JSON
        FileManager.atomic_write_json(paths["entry_json"], entry.to_dict())

        return paths

    @staticmethod
    def export_weekly_report(report: WeeklyReport, custom_dir: Optional[Path] = None) -> Dict[str, Path]:
        """
        Generate weekly digest export files:
        1. YYYY-MM-DD_weekly_digest.md
        2. YYYY-MM-DD_weekly_digest.txt
        """
        paths = FileManager.get_weekly_export_paths(report.start_date, report.end_date, custom_dir)

        # Markdown Export
        md_lines = [
            f"# EchoDiary Weekly Digest",
            f"**Period:** {format_display_date(report.start_date)} to {format_display_date(report.end_date)}",
            f"**Status:** {'Partial Week (' + str(report.entries_count) + '/7 entries logged)' if report.is_partial_week else 'Full Week (7/7 entries logged)'}",
            f"**Tasks Summary:** {report.completed_tasks_count} completed, {report.pending_tasks_count} pending",
            "",
            "## 1. Overview",
            report.overview,
            "",
            "## 2. Key Highlights",
        ]
        for h in report.highlights:
            md_lines.append(f"- {h}")
        if not report.highlights:
            md_lines.append("- No highlights recorded.")

        md_lines.extend(["", "## 3. Accomplishments"])
        for a in report.accomplishments:
            md_lines.append(f"- {a}")
        if not report.accomplishments:
            md_lines.append("- No accomplishments recorded.")

        md_lines.extend(["", "## 4. Main Topics Discussed"])
        for topic in report.main_topics:
            md_lines.append(f"- **{topic}**")
        if not report.main_topics:
            md_lines.append("- None")

        md_lines.extend(["", "## 5. Mood Distribution"])
        for mood, count in report.mood_distribution.items():
            md_lines.append(f"- **{mood}**: {count} day(s)")
        if not report.mood_distribution:
            md_lines.append("- No mood data available.")

        md_lines.extend(["", "## 6. Recurring Themes & Patterns"])
        for th in report.recurring_themes:
            md_lines.append(f"- {th}")
        if not report.recurring_themes:
            md_lines.append("- None observed.")

        md_lines.extend(["", "## 7. Suggested Priorities for Next Week"])
        for sp in report.suggested_priorities:
            md_lines.append(f"- {sp}")
        if not report.suggested_priorities:
            md_lines.append("- Continue daily diary check-ins.")

        FileManager.atomic_write_text(paths["digest_md"], "\n".join(md_lines))

        # Plain Text Export
        txt_lines = [
            "============================================================",
            f"ECHODIARY WEEKLY DIGEST",
            f"Period: {report.start_date} to {report.end_date}",
            f"Coverage: {report.entries_count}/7 entries ({'Partial' if report.is_partial_week else 'Complete'})",
            f"Tasks: {report.completed_tasks_count} Completed, {report.pending_tasks_count} Pending",
            "============================================================",
            "",
            "OVERVIEW:",
            report.overview,
            "",
            "KEY HIGHLIGHTS:",
        ]
        txt_lines.extend([f" * {h}" for h in report.highlights] or [" * None"])
        txt_lines.append("\nACCOMPLISHMENTS:")
        txt_lines.extend([f" * {a}" for a in report.accomplishments] or [" * None"])
        txt_lines.append("\nMAIN TOPICS:")
        txt_lines.extend([f" * {t}" for t in report.main_topics] or [" * None"])
        txt_lines.append("\nMOOD BREAKDOWN:")
        txt_lines.extend([f" * {m}: {c}" for m, c in report.mood_distribution.items()] or [" * None"])
        txt_lines.append("\nSUGGESTED PRIORITIES:")
        txt_lines.extend([f" * {sp}" for sp in report.suggested_priorities] or [" * None"])

        FileManager.atomic_write_text(paths["digest_txt"], "\n".join(txt_lines))

        return paths

    @staticmethod
    def export_all_tasks(tasks: List[Task], output_file: Path) -> Path:
        """Export task list to text file."""
        lines = [
            "ECHODIARY - TASK LIST EXPORT",
            f"Exported: {format_display_date(date.today())}",
            f"Total Tasks: {len(tasks)}",
            "-" * 50,
        ]
        for t in tasks:
            status = "[COMPLETED]" if t.status == "Completed" else "[PENDING]  "
            due = f" | Due: {t.due_date}" if t.due_date else ""
            lines.append(f"{status} [{t.priority.upper()}] {t.description}{due}")

        FileManager.atomic_write_text(output_file, "\n".join(lines))
        return output_file
