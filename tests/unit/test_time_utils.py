from datetime import date, datetime
from freezegun import freeze_time
from utils.time import (
    cairo_now,
    cairo_today_start,
    cairo_date_to_utc_start,
    cairo_date_to_utc_end,
    utc_to_cairo,
    cairo_date_str,
    cairo_date_str_full,
)


def test_cairo_now_observes_dst() -> None:
    # Summer (August): UTC+3
    with freeze_time("2024-08-15 21:00:00"):
        assert cairo_now() == datetime(2024, 8, 16, 0, 0, 0)
    # Winter (January): UTC+2
    with freeze_time("2024-01-15 22:00:00"):
        assert cairo_now() == datetime(2024, 1, 16, 0, 0, 0)


def test_cairo_today_start_returns_utc() -> None:
    # Summer (August): UTC+3
    with freeze_time("2024-08-15 21:00:00"):
        assert cairo_today_start() == datetime(2024, 8, 15, 21, 0, 0)
    # Winter (January): UTC+2
    with freeze_time("2024-01-15 22:00:00"):
        assert cairo_today_start() == datetime(2024, 1, 15, 22, 0, 0)


def test_cairo_date_to_utc_start() -> None:
    # Summer: 2024-08-15 midnight Cairo -> 2024-08-14 21:00:00 UTC
    assert cairo_date_to_utc_start(date(2024, 8, 15)) == datetime(2024, 8, 14, 21, 0, 0)
    # Winter: 2024-01-15 midnight Cairo -> 2024-01-14 22:00:00 UTC
    assert cairo_date_to_utc_start(date(2024, 1, 15)) == datetime(2024, 1, 14, 22, 0, 0)


def test_cairo_date_to_utc_end() -> None:
    # Summer: 2024-08-15 end date -> 2024-08-15 21:00:00 UTC
    assert cairo_date_to_utc_end(date(2024, 8, 15)) == datetime(2024, 8, 15, 21, 0, 0)
    # Winter: 2024-01-15 end date -> 2024-01-15 22:00:00 UTC
    assert cairo_date_to_utc_end(date(2024, 1, 15)) == datetime(2024, 1, 15, 22, 0, 0)


def test_cairo_date_str() -> None:
    # Summer: UTC 2024-08-15 21:30 -> Cairo 2024-08-16 00:30 -> "2024-08-16"
    assert cairo_date_str(datetime(2024, 8, 15, 21, 30)) == "2024-08-16"


def test_utc_to_cairo_dst() -> None:
    # Summer (+3 hours): UTC 10:00 -> Cairo 13:00
    assert utc_to_cairo(datetime(2024, 8, 15, 10, 0, 0)) == datetime(2024, 8, 15, 13, 0, 0)
    # Winter (+2 hours): UTC 10:00 -> Cairo 12:00
    assert utc_to_cairo(datetime(2024, 1, 15, 10, 0, 0)) == datetime(2024, 1, 15, 12, 0, 0)


def test_cairo_date_to_utc_end_is_next_midnight() -> None:
    assert cairo_date_to_utc_end(date(2024, 8, 15)) == cairo_date_to_utc_start(date(2024, 8, 16))


def test_cairo_date_str_full_12h() -> None:
    assert cairo_date_str_full(None) == ""
    # Summer: UTC 2024-08-15 21:30 -> Cairo 2024-08-16 00:30 (12:30 ص)
    assert cairo_date_str_full(datetime(2024, 8, 15, 21, 30)) == "2024-08-16 12:30 ص"
    # Winter PM: UTC 2024-01-15 13:45 -> Cairo 2024-01-15 15:45 (03:45 م)
    assert cairo_date_str_full(datetime(2024, 1, 15, 13, 45)) == "2024-01-15 03:45 م"
