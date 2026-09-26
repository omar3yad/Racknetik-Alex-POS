from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

CAIRO_TZ = ZoneInfo("Africa/Cairo")
UTC_TZ = timezone.utc


def cairo_now() -> datetime:
    """Returns current Cairo local time as a naive datetime, accurately observing
    Egypt Daylight Saving Time (DST: UTC+3 in summer, UTC+2 in winter).
    """
    return datetime.now(CAIRO_TZ).replace(tzinfo=None)


def utc_to_cairo(dt: datetime) -> datetime:
    """Converts a UTC datetime (naive or aware) to Cairo local time as a naive datetime,
    accurately observing Egypt Daylight Saving Time (UTC+3 in summer, UTC+2 in winter).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CAIRO_TZ).replace(tzinfo=None)


def cairo_to_utc(dt: datetime) -> datetime:
    """Converts a Cairo local datetime (naive or aware) to UTC naive datetime."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CAIRO_TZ)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def cairo_date_to_utc_start(d: date) -> datetime:
    """Converts a Cairo calendar date to the UTC datetime of Cairo midnight on that date,
    accurately observing DST for that specific date.
    """
    cairo_midnight = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=CAIRO_TZ)
    return cairo_midnight.astimezone(timezone.utc).replace(tzinfo=None)


def cairo_date_to_utc_end(d: date) -> datetime:
    """Returns the UTC datetime of Cairo midnight at the end of that date
    (start of the next calendar day in Cairo).
    """
    next_day = d + timedelta(days=1)
    cairo_midnight_next = datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=CAIRO_TZ)
    return cairo_midnight_next.astimezone(timezone.utc).replace(tzinfo=None)


def cairo_today_start() -> datetime:
    """Returns the UTC datetime corresponding to midnight Cairo time today."""
    return cairo_date_to_utc_start(cairo_now().date())


def cairo_date_str(dt: datetime) -> str:
    """Converts a UTC datetime to a Cairo local date string YYYY-MM-DD."""
    return utc_to_cairo(dt).strftime("%Y-%m-%d")


def cairo_date_str_full(dt: datetime | None) -> str:
    """Converts a UTC datetime to a Cairo local datetime string in 12-hour format: YYYY-MM-DD hh:mm AM/PM (م/ص)."""
    if dt is None:
        return ""
    c_dt = utc_to_cairo(dt)
    time_part = c_dt.strftime("%I:%M")
    ampm = "م" if c_dt.hour >= 12 else "ص"
    return f"{c_dt.strftime('%Y-%m-%d')} {time_part} {ampm}"


__all__ = [
    "CAIRO_TZ",
    "cairo_now",
    "cairo_today_start",
    "cairo_date_to_utc_start",
    "cairo_date_to_utc_end",
    "utc_to_cairo",
    "cairo_to_utc",
    "cairo_date_str",
    "cairo_date_str_full",
]
