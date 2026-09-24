from datetime import date, datetime
from freezegun import freeze_time
from utils.time import (
    cairo_now,
    cairo_today_start,
    cairo_date_to_utc_start,
    cairo_date_to_utc_end,
    utc_to_cairo,
    cairo_date_str,
)


def test_cairo_now_is_utc_plus_2() -> None:
    with freeze_time("2024-08-15 22:00:00"):
        assert cairo_now() == datetime(2024, 8, 16, 0, 0, 0)


def test_cairo_today_start_returns_utc() -> None:
    # Freezes Cairo time at midnight (UTC 22:00 previous day)
    with freeze_time("2024-08-15 22:00:00"):
        # Cairo now is 2024-08-16 00:00:00. Midnight today in Cairo is 2024-08-16 00:00:00.
        # UTC corresponding to Cairo midnight is 2024-08-15 22:00:00.
        assert cairo_today_start() == datetime(2024, 8, 15, 22, 0, 0)


def test_cairo_date_to_utc_start() -> None:
    assert cairo_date_to_utc_start(date(2024, 8, 15)) == datetime(2024, 8, 14, 22, 0, 0)


def test_cairo_date_to_utc_end() -> None:
    assert cairo_date_to_utc_end(date(2024, 8, 15)) == datetime(2024, 8, 15, 22, 0, 0)


def test_cairo_date_str() -> None:
    # UTC 2024-08-15 23:30 -> Cairo 2024-08-16 01:30 -> "2024-08-16"
    assert cairo_date_str(datetime(2024, 8, 15, 23, 30)) == "2024-08-16"


def test_utc_to_cairo_adds_two_hours() -> None:
    assert utc_to_cairo(datetime(2024, 8, 15, 10, 0, 0)) == datetime(2024, 8, 15, 12, 0, 0)


def test_cairo_date_to_utc_end_is_next_midnight() -> None:
    assert cairo_date_to_utc_end(date(2024, 8, 15)) == cairo_date_to_utc_start(date(2024, 8, 16))


def test_utc_to_cairo_midnight_crossing() -> None:
    # UTC 2024-08-15 23:30 -> Cairo 2024-08-16 01:30 (next calendar day)
    assert utc_to_cairo(datetime(2024, 8, 15, 23, 30)) == datetime(2024, 8, 16, 1, 30)


def test_cairo_date_str_midnight_utc() -> None:
    # UTC 2024-08-15 22:00:00 -> Cairo 2024-08-16 00:00:00 -> "2024-08-16"
    assert cairo_date_str(datetime(2024, 8, 15, 22, 0, 0)) == "2024-08-16"
