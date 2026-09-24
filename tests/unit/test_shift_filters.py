import pytest
from datetime import date
from pydantic import ValidationError

from schemas.admin_reports import ShiftFilters


def test_valid_shift_filters():
    f = ShiftFilters(status="open", gate_number=3)
    assert f.status == "open"
    assert f.gate_number == 3


def test_invalid_status():
    with pytest.raises(ValidationError):
        ShiftFilters(status="pending")


def test_invalid_date_range():
    with pytest.raises(ValidationError):
        ShiftFilters(start_date=date(2024, 8, 20), end_date=date(2024, 8, 10))


def test_overdue_default_false():
    f = ShiftFilters()
    assert f.overdue is False
