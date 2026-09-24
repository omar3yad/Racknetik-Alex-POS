from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

CAIRO_TZ = ZoneInfo("Africa/Cairo")


def cairo_now() -> datetime:
    """Returns current Cairo local time as a naive datetime (UTC + 2 hours)."""
    return datetime.utcnow() + timedelta(hours=2)


def cairo_today_start() -> datetime:
    """Returns the UTC datetime corresponding to midnight Cairo time today."""
    return cairo_now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=2)


def cairo_date_to_utc_start(d: date) -> datetime:
    """Converts a date to the UTC datetime of Cairo midnight on that date."""
    return datetime(d.year, d.month, d.day, 0, 0, 0) - timedelta(hours=2)


def cairo_date_to_utc_end(d: date) -> datetime:
    """Returns the UTC datetime of Cairo midnight at the end of that date (start of next day)."""
    return cairo_date_to_utc_start(d) + timedelta(days=1)


def utc_to_cairo(dt: datetime) -> datetime:
    """Adds 2 hours to a UTC datetime. Returns Cairo local time as a naive datetime."""
    return dt + timedelta(hours=2)


def cairo_date_str(dt: datetime) -> str:
    """Converts a UTC datetime to a Cairo local date string YYYY-MM-DD."""
    return utc_to_cairo(dt).strftime("%Y-%m-%d")


def cairo_date_str_full(dt: datetime | None) -> str:
    """Converts a UTC datetime to a Cairo local datetime string YYYY-MM-DD HH:mm."""
    if dt is None:
        return ""
    return utc_to_cairo(dt).strftime("%Y-%m-%d %H:%M")


__all__ = [
    "CAIRO_TZ",
    "cairo_now",
    "cairo_today_start",
    "cairo_date_to_utc_start",
    "cairo_date_to_utc_end",
    "utc_to_cairo",
    "cairo_date_str",
    "cairo_date_str_full",
]
