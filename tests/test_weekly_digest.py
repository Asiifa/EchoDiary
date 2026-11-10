"""Tests for 7-day weekly digest calculations, partial week flags, and aggregations."""
from datetime import date, timedelta
from unittest.mock import MagicMock
from app.models.diary_entry import DiaryEntry
from app.models.weekly_report import WeeklyReport
from app.services.weekly_digest_service import WeeklyDigestService
from app.schemas.weekly_schema import WeeklyDigestOutput
from app.utils.date_utils import get_current_week_range


def test_seven_day_date_range():
    """Verify 7-day range calculations are strictly 7 days inclusive."""
    ref_d = date(2026, 11, 9)
    start_d, end_d = get_current_week_range(ref_d)
    assert (end_d - start_d).days == 6
    assert start_d == date(2026, 11, 3)
    assert end_d == date(2026, 11, 9)


def test_partial_week_detection(test_db_session):
    """Verify that fewer than 7 entries flags is_partial_week = True."""
    start_d = date(2026, 11, 1)
    end_d = start_d + timedelta(days=6)

    # Add only 3 entries
    for i in range(3):
        entry = DiaryEntry(
            entry_date=start_d + timedelta(days=i),
            original_transcript=f"Entry on day {i}",
            primary_mood="Calm" if i % 2 == 0 else "Happy",
            mood_confidence=0.85,
            summary_line_1=f"Activity on day {i}",
            summary_line_2="Continued daily routine",
            summary_line_3="Reflected on personal progress",
        )
        test_db_session.add(entry)
    test_db_session.commit()

    mock_ollama = MagicMock()
    mock_ollama.generate_weekly_digest.return_value = WeeklyDigestOutput(
        overview="Overall calm and productive partial week.",
        highlights=["Made steady progress on coursework"],
        accomplishments=["Completed scheduled check-ins"],
        main_topics=["Study", "Routine"],
        recurring_themes=["Consistency"],
        suggested_priorities=["Maintain study momentum"],
        mood_trend_summary="Stable positive emotions.",
    )

    service = WeeklyDigestService(ollama_service=mock_ollama)
    report = service.generate_digest(test_db_session, start_d, end_d)

    assert report is not None
    assert report.is_partial_week is True
    assert report.entries_count == 3
    assert report.mood_distribution == {"Calm": 2, "Happy": 1}
    assert "Made steady progress on coursework" in report.highlights


def test_empty_week_handling(test_db_session):
    """Verify empty week does not crash and handles zero entries gracefully."""
    start_d = date(2026, 10, 1)
    end_d = start_d + timedelta(days=6)

    service = WeeklyDigestService()
    report = service.generate_digest(test_db_session, start_d, end_d)

    assert report is not None
    assert report.entries_count == 0
    assert report.is_partial_week is True
    assert "No diary entries were logged" in report.overview

