import pytest
from datetime import date
from pydantic import ValidationError

from schemas.admin_reports import ReportFilters


def test_valid_filters():
    f = ReportFilters(start_date=date(2024, 1, 1), end_date=date(2024, 1, 31))
    assert f.start_date == date(2024, 1, 1)
    assert f.end_date == date(2024, 1, 31)


def test_invalid_date_range_raises():
    with pytest.raises(ValidationError):
        ReportFilters(start_date=date(2024, 2, 1), end_date=date(2024, 1, 1))


def test_same_start_end_date_valid():
    d = date(2024, 5, 10)
    f = ReportFilters(start_date=d, end_date=d)
    assert f.start_date == d
    assert f.end_date == d


def test_gate_number_out_of_range():
    with pytest.raises(ValidationError):
        ReportFilters(gate_number=6)


def test_gate_number_zero():
    with pytest.raises(ValidationError):
        ReportFilters(gate_number=0)


def test_card_code_too_long():
    with pytest.raises(ValidationError):
        ReportFilters(card_code="A" * 51)


def test_all_none_is_valid():
    f = ReportFilters()
    assert f.start_date is None
    assert f.end_date is None
    assert f.gate_number is None
    assert f.card_code is None
    assert f.plate_number is None
    assert f.long_stay is False
