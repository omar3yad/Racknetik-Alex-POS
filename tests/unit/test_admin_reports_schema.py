from datetime import date, datetime
import pytest
from pydantic import ValidationError
from models import SessionStatus, PaymentMethod
from schemas.admin_reports import (
    LiveStatsResponse,
    GateStatusResponse,
    RevenueSummaryResponse,
    GateRevenueResponse,
    OperatorRevenueResponse,
    DailyRevenueResponse,
    ReportFilters,
    ShiftFilters,
    ForceCloseShiftRequest,
    AdminSessionDetail,
)


def test_live_stats_response() -> None:
    data = {
        "active_sessions": 5,
        "total_capacity": 50,
        "occupancy_pct": 10,
        "revenue_today_piastres": 12500,
        "open_shifts": 2,
    }
    obj = LiveStatsResponse(**data)
    assert obj.active_sessions == 5
    assert obj.occupancy_pct == 10


def test_gate_status_response() -> None:
    obj = GateStatusResponse(
        gate_number=1,
        operator_name="أحمد",
        operator_id=3,
        shift_start=datetime(2024, 8, 15, 8, 0),
        active_sessions=4,
    )
    assert obj.gate_number == 1
    assert obj.operator_name == "أحمد"


def test_revenue_responses() -> None:
    rev_sum = RevenueSummaryResponse(
        total_sessions=10,
        total_revenue_piastres=5000,
        avg_duration_minutes=30,
        avg_revenue_piastres=500,
    )
    assert rev_sum.total_sessions == 10

    gate_rev = GateRevenueResponse(
        gate_number=2,
        session_count=7,
        total_piastres=3500,
    )
    assert gate_rev.gate_number == 2

    op_rev = OperatorRevenueResponse(
        operator_id=4,
        operator_name="محمد",
        session_count=8,
        total_piastres=4000,
    )
    assert op_rev.operator_id == 4

    daily_rev = DailyRevenueResponse(
        date_str="2024-08-15",
        session_count=15,
        total_piastres=7500,
    )
    assert daily_rev.date_str == "2024-08-15"


def test_report_filters_date_range_validation() -> None:
    # Valid
    f = ReportFilters(start_date=date(2024, 8, 1), end_date=date(2024, 8, 15))
    assert f.start_date == date(2024, 8, 1)

    # Inverted date range should raise ValidationError
    with pytest.raises(ValidationError):
        ReportFilters(start_date=date(2024, 8, 15), end_date=date(2024, 8, 1))


def test_shift_filters_date_range_validation() -> None:
    # Valid
    f = ShiftFilters(start_date=date(2024, 8, 1), end_date=date(2024, 8, 15), status="open")
    assert f.status == "open"

    # Inverted date range
    with pytest.raises(ValidationError):
        ShiftFilters(start_date=date(2024, 8, 20), end_date=date(2024, 8, 10))


def test_force_close_shift_request() -> None:
    req = ForceCloseShiftRequest(closing_cash_egp=5000, admin_note="إغلاق إداري")
    assert req.closing_cash_egp == 5000

    # Negative closing cash
    with pytest.raises(ValidationError):
        ForceCloseShiftRequest(closing_cash_egp=-10)


def test_admin_session_detail() -> None:
    now = datetime(2024, 8, 15, 10, 0)
    detail = AdminSessionDetail(
        id=1,
        card_id=10,
        card_code="CARD10",
        status=SessionStatus.ACTIVE,
        gate_number=1,
        shift_id=2,
        operator_id=3,
        entry_time=now,
        created_at=now,
    )
    assert detail.id == 1
    assert detail.status == SessionStatus.ACTIVE
    assert detail.audit_logs == []
