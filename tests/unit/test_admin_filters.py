from datetime import datetime
import pytest

from utils.jinja import (
    discrepancy_class_filter,
    session_status_label_filter,
    shift_status_label_filter,
    cairo_date_filter,
)


def test_discrepancy_class_filter_zero():
    assert discrepancy_class_filter(0) == "text-green-600"
    assert discrepancy_class_filter(0, 1000) == "text-green-600"


def test_discrepancy_class_filter_none():
    assert discrepancy_class_filter(None) == "text-gray-400"
    assert discrepancy_class_filter(None, 1000) == "text-gray-400"


def test_discrepancy_class_filter_small_within_5pct():
    # 50 / 1000 = 0.05 (5%) -> within 5%
    assert discrepancy_class_filter(50, 1000) == "text-amber-500"
    assert discrepancy_class_filter(-50, 1000) == "text-amber-500"
    assert discrepancy_class_filter(20, 1000) == "text-amber-500"


def test_discrepancy_class_filter_large():
    # 200 / 1000 = 0.20 (20%) -> > 5%
    assert discrepancy_class_filter(200, 1000) == "text-red-600"
    assert discrepancy_class_filter(-200, 1000) == "text-red-600"


def test_discrepancy_class_filter_zero_computed_total():
    # discrepancy=100, computed_total=0 -> max(0, 1)=1, 100/1=100 > 0.05
    assert discrepancy_class_filter(100, 0) == "text-red-600"


def test_session_status_label_filter():
    assert session_status_label_filter("ACTIVE") == "داخل"
    assert session_status_label_filter("COMPLETED") == "خرج"
    assert session_status_label_filter("LOST_CARD") == "كرت مفقود"
    assert session_status_label_filter("UNKNOWN") == "UNKNOWN"


def test_shift_status_label_filter():
    assert shift_status_label_filter(None) == "مفتوح"
    assert shift_status_label_filter(datetime(2024, 1, 1)) == "مغلق"


def test_cairo_date_filter():
    assert cairo_date_filter(None) == "—"
    # UTC 23:00 -> Cairo (+2 hours) is 01:00 on the next day (2024-08-16)
    utc_dt = datetime(2024, 8, 15, 23, 0, 0)
    assert cairo_date_filter(utc_dt) == "2024-08-16"
