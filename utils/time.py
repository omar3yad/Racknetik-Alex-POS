from datetime import datetime, timezone
from zoneinfo import ZoneInfo

CAIRO_TZ = ZoneInfo("Africa/Cairo")


def cairo_now() -> datetime:
    """Returns current datetime in Cairo timezone (Africa/Cairo)."""
    return datetime.now(CAIRO_TZ)


def cairo_today_start() -> datetime:
    """Returns midnight (00:00:00) of today in Cairo timezone, converted to naive UTC datetime."""
    now = cairo_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start.astimezone(timezone.utc).replace(tzinfo=None)


__all__ = ["CAIRO_TZ", "cairo_now", "cairo_today_start"]
