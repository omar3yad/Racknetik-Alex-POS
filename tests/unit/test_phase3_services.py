from datetime import datetime, timedelta, date
from unittest.mock import AsyncMock, MagicMock
import pytest

from models.shift import Shift
from models.pricing_rule import PricingRule
from schemas.admin_reports import ReportFilters
from schemas.pricing_rule import PricingRuleCreate
from services.exceptions import (
    ShiftNotFoundError,
    ShiftAlreadyClosedError,
    RateLabelAlreadyExistsError,
)
from services.pricing_service import PricingService
from services.report_service import ReportService
from services.shift_service import ShiftService


@pytest.mark.asyncio
async def test_report_service_live_stats_and_gate_panel() -> None:
    mock_repo = MagicMock()
    mock_repo.count_active_sessions = AsyncMock(return_value=10)
    mock_repo.count_total_card_capacity = AsyncMock(return_value=100)
    mock_repo.sum_revenue_today = AsyncMock(return_value=25000)
    mock_repo.count_open_shifts = AsyncMock(return_value=2)
    mock_repo.count_long_stay_sessions = AsyncMock(return_value=1)
    mock_repo.count_overdue_shifts = AsyncMock(return_value=0)
    mock_repo.get_gate_panel = AsyncMock(
        return_value=[
            {
                "gate_number": 2,
                "operator_name": "علي",
                "operator_id": 5,
                "shift_start": datetime(2024, 8, 15, 8, 0),
                "active_sessions": 3,
            }
        ]
    )

    svc = ReportService(db=MagicMock(), report_repo=mock_repo)

    # 1. Live stats
    stats = await svc.get_live_stats()
    assert stats.active_sessions == 10
    assert stats.total_capacity == 100
    assert stats.occupancy_pct == 10
    assert stats.revenue_today_piastres == 25000
    assert stats.open_shifts == 2

    # 2. Gate panel (1..5)
    panel = await svc.get_gate_panel()
    assert len(panel) == 5
    assert panel[0].gate_number == 1
    assert panel[0].operator_name is None
    assert panel[1].gate_number == 2
    assert panel[1].operator_name == "علي"
    assert panel[1].active_sessions == 3

    # 3. Alert counts
    alerts = await svc.get_alert_counts()
    assert alerts["long_stay"] == 1
    assert alerts["overdue_shifts"] == 0


@pytest.mark.asyncio
async def test_report_service_daily_revenue_fills_missing_days() -> None:
    mock_repo = MagicMock()
    # Mock returns only 2024-08-15
    mock_repo.get_daily_revenue_raw = AsyncMock(
        return_value=[
            {"cairo_date": "2024-08-15", "session_count": 5, "total_piastres": 5000}
        ]
    )

    svc = ReportService(db=MagicMock(), report_repo=mock_repo)
    filters = ReportFilters(start_date=date(2024, 8, 14), end_date=date(2024, 8, 16))
    daily = await svc.get_daily_revenue(filters)

    assert len(daily) == 3
    assert daily[0].date_str == "2024-08-14"
    assert daily[0].session_count == 0
    assert daily[1].date_str == "2024-08-15"
    assert daily[1].session_count == 5
    assert daily[2].date_str == "2024-08-16"
    assert daily[2].session_count == 0


@pytest.mark.asyncio
async def test_force_close_shift() -> None:
    mock_db = AsyncMock()
    mock_audit = AsyncMock()

    shift = Shift(
        id=1,
        operator_id=2,
        gate_number=1,
        started_at=datetime.utcnow() - timedelta(hours=3),
        ended_at=None,
        opening_cash_egp=0,
        closing_cash_egp=None,
    )

    mock_db.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=shift), all=MagicMock(return_value=[])))
        )
    )

    svc = ShiftService(db=mock_db, audit_service=mock_audit)

    summary = await svc.force_close_shift(
        shift_id=1,
        admin_id=99,
        closing_cash_piastres=7500,
        admin_note="إغلاق إداري من المدير",
    )

    assert shift.ended_at is not None
    assert shift.closing_cash_egp == 7500
    assert shift.admin_override_note == "إغلاق إداري من المدير"
    assert mock_audit.log.called


@pytest.mark.asyncio
async def test_force_close_shift_already_closed() -> None:
    mock_db = AsyncMock()
    mock_audit = AsyncMock()

    shift = Shift(
        id=2,
        operator_id=2,
        gate_number=1,
        started_at=datetime.utcnow() - timedelta(hours=5),
        ended_at=datetime.utcnow() - timedelta(hours=1),
        opening_cash_egp=0,
    )

    mock_db.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=shift)))
        )
    )

    svc = ShiftService(db=mock_db, audit_service=mock_audit)
    with pytest.raises(ShiftAlreadyClosedError):
        await svc.force_close_shift(2, 99, 5000, "note")


@pytest.mark.asyncio
async def test_pricing_service_create_rule() -> None:
    mock_db = AsyncMock()
    mock_rate_repo = AsyncMock()
    mock_audit = AsyncMock()

    mock_rate_repo.get_by_label.return_value = None
    created_rule = PricingRule(
        id=10,
        label="Night Rate",
        rate_per_hour=1500,
        minimum_charge=1500,
        grace_period_mins=15,
        lost_card_penalty=5000,
        created_by=1,
        effective_from=datetime.utcnow(),
    )
    mock_rate_repo.create.return_value = created_rule

    svc = PricingService(db=mock_db)
    data = PricingRuleCreate(
        label="Night Rate",
        rate_per_hour_egp=15.0,
        minimum_charge_egp=15.0,
        lost_card_penalty_egp=50.0,
    )

    rule = await svc.create_rule(data, 1, mock_rate_repo, mock_audit)
    assert rule.id == 10
    assert mock_audit.log.called

    # Duplicate label raises
    mock_rate_repo.get_by_label.return_value = created_rule
    with pytest.raises(RateLabelAlreadyExistsError):
        await svc.create_rule(data, 1, mock_rate_repo, mock_audit)
