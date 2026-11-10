"""Date utilities for daily diary entries and 7-day weekly digest calculations."""
from datetime import date, datetime, timedelta
from typing import Tuple, List


def get_today_date() -> date:
    """Return current local date."""
    return date.today()


def get_current_week_range(reference_date: date = None) -> Tuple[date, date]:
    """
    Return a 7-day range ending on the reference date (or current date if omitted).
    The range is inclusive: [start_date, end_date] where end_date - start_date = 6 days.
    """
    end_d = reference_date or date.today()
    start_d = end_d - timedelta(days=6)
    return start_d, end_d


def get_calendar_week_range(reference_date: date = None) -> Tuple[date, date]:
    """
    Return Monday through Sunday of the reference date's calendar week.
    """
    ref = reference_date or date.today()
    # Monday is 0, Sunday is 6
    start_d = ref - timedelta(days=ref.weekday())
    end_d = start_d + timedelta(days=6)
    return start_d, end_d


def format_display_date(d: any) -> str:
    """Format date for friendly UI display, e.g. 'Monday, Nov 9, 2026'."""
    if not d:
        return ""
    if isinstance(d, str):
        parsed = parse_date(d)
        if not parsed:
            return str(d)
        d = parsed
    return d.strftime("%A, %b %d, %Y")


def format_short_date(d: date) -> str:
    """Format date in ISO style 'YYYY-MM-DD'."""
    if not d:
        return ""
    return d.strftime("%Y-%m-%d")


def parse_date(date_str: str) -> date:
    """Parse date from string."""
    if not date_str:
        return None
    return datetime.strptime(date_str[:10], "%Y-%m-%d").date()


def generate_date_range(start_date: date, end_date: date) -> List[date]:
    """Generate list of dates between start and end inclusive."""
    days = (end_date - start_date).days
    return [start_date + timedelta(days=i) for i in range(days + 1)]

