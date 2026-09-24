import pytest
from datetime import date, datetime
from typing import Any

from schemas.admin_reports import ReportFilters, RevenueSummaryResponse
from services.report_service import ReportService


class MockReportRepo:
    def __init__(self):
        self.active_sessions = 3
        self.capacity = 10
        self.revenue_today = 5000
        self.open_shifts = 2
        self.long_stay = 0
        self.overdue_shifts = 0
        self.should_raise_open_shifts = False

        self.revenue_summary = {
            "total_sessions": 3,
            "total_revenue": 7777,
            "total_duration": 100,
        }
        self.daily_revenue_raw = [
            {"cairo_date": "2024-08-15", "session_count": 3, "total_piastres": 3000}
        ]
        self.gate_panel = [
            {
                "gate_number": 1,
                "operator_name": "Op 1",
                "operator_id": 10,
                "shift_start": datetime(2024, 8, 15, 8, 0),
                "active_sessions": 2,
            },
            {
                "gate_number": 3,
                "operator_name": "Op 3",
                "operator_id": 30,
                "shift_start": datetime(2024, 8, 15, 9, 0),
                "active_sessions": 1,
            },
            {
                "gate_number": 5,
                "operator_name": "Op 5",
                "operator_id": 50,
                "shift_start": datetime(2024, 8, 15, 10, 0),
                "active_sessions": 4,
            },
        ]

    async def count_active_sessions(self) -> int:
        return self.active_sessions

    async def count_total_card_capacity(self) -> int:
        return self.capacity

    async def sum_revenue_today(self, start_utc: datetime, end_utc: datetime) -> int:
        return self.revenue_today

    async def count_open_shifts(self) -> int:
        if self.should_raise_open_shifts:
            raise RuntimeError("Database connection error on shifts count")
        return self.open_shifts

    async def count_long_stay_sessions(self, threshold_utc: datetime) -> int:
        return self.long_stay

    async def count_overdue_shifts(self, threshold_utc: datetime) -> int:
        return self.overdue_shifts

    async def get_gate_panel(self) -> list[dict[str, Any]]:
        return self.gate_panel

    async def get_revenue_summary(
        self,
        start_utc: datetime | None,
        end_utc: datetime | None,
        gate_number: int | None = None,
        operator_id: int | None = None,
    ) -> dict[str, int]:
        return self.revenue_summary

    async def get_daily_revenue_raw(
        self,
        start_utc: datetime,
        end_utc: datetime,
        gate_number: int | None = None,
        operator_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return self.daily_revenue_raw


@pytest.mark.asyncio
async def test_get_live_stats_success():
    repo = MockReportRepo()
    repo.active_sessions = 3
    repo.capacity = 10
    repo.revenue_today = 5000
    repo.open_shifts = 2

    service = ReportService(db=None, report_repo=repo)
    stats = await service.get_live_stats()

    assert stats.active_sessions == 3
    assert stats.occupancy_pct == 30
    assert stats.revenue_today_piastres == 5000
    assert stats.open_shifts == 2


@pytest.mark.asyncio
async def test_get_live_stats_exception_fallback():
    repo = MockReportRepo()
    repo.should_raise_open_shifts = True

    service = ReportService(db=None, report_repo=repo)
    stats = await service.get_live_stats()

    assert stats.open_shifts == 0
    assert stats.active_sessions == 3


@pytest.mark.asyncio
async def test_get_daily_revenue_fills_missing_days():
    repo = MockReportRepo()
    repo.daily_revenue_raw = [
        {"cairo_date": "2024-08-15", "session_count": 3, "total_piastres": 3000}
    ]

    service = ReportService(db=None, report_repo=repo)
    filters = ReportFilters(start_date=date(2024, 8, 14), end_date=date(2024, 8, 16))
    result = await service.get_daily_revenue(filters)

    assert len(result) == 3

    # Day 1: 2024-08-14 (missing -> 0)
    assert result[0].date_str == "2024-08-14"
    assert result[0].session_count == 0
    assert result[0].total_piastres == 0

    # Day 2: 2024-08-15 (present -> 3, 3000)
    assert result[1].date_str == "2024-08-15"
    assert result[1].session_count == 3
    assert result[1].total_piastres == 3000

    # Day 3: 2024-08-16 (missing -> 0)
    assert result[2].date_str == "2024-08-16"
    assert result[2].session_count == 0
    assert result[2].total_piastres == 0


@pytest.mark.asyncio
async def test_revenue_summary_no_floats():
    repo = MockReportRepo()
    repo.revenue_summary = {
        "total_sessions": 3,
        "total_revenue": 7777,
        "total_duration": 100,
    }

    service = ReportService(db=None, report_repo=repo)
    filters = ReportFilters(start_date=date(2024, 8, 1), end_date=date(2024, 8, 31))
    summary = await service.get_revenue_summary(filters)

    assert isinstance(summary.total_sessions, int)
    assert isinstance(summary.total_revenue_piastres, int)
    assert isinstance(summary.avg_duration_minutes, int)
    assert isinstance(summary.avg_revenue_piastres, int)


@pytest.mark.asyncio
async def test_revenue_summary_zero_sessions_no_div_error():
    repo = MockReportRepo()
    repo.revenue_summary = {
        "total_sessions": 0,
        "total_revenue": 0,
        "total_duration": 0,
    }

    service = ReportService(db=None, report_repo=repo)
    filters = ReportFilters(start_date=date(2024, 8, 1), end_date=date(2024, 8, 31))
    summary = await service.get_revenue_summary(filters)

    assert summary.avg_duration_minutes == 0
    assert summary.avg_revenue_piastres == 0


@pytest.mark.asyncio
async def test_gate_panel_fills_missing_gates():
    repo = MockReportRepo()
    # Gates 1, 3, 5 present; 2, 4 missing
    service = ReportService(db=None, report_repo=repo)
    panel = await service.get_gate_panel()

    assert len(panel) == 5

    # Gate 1
    assert panel[0].gate_number == 1
    assert panel[0].operator_name == "Op 1"
    assert panel[0].active_sessions == 2

    # Gate 2 (missing)
    assert panel[1].gate_number == 2
    assert panel[1].operator_name is None
    assert panel[1].active_sessions == 0

    # Gate 3
    assert panel[2].gate_number == 3
    assert panel[2].operator_name == "Op 3"
    assert panel[2].active_sessions == 1

    # Gate 4 (missing)
    assert panel[3].gate_number == 4
    assert panel[3].operator_name is None
    assert panel[3].active_sessions == 0

    # Gate 5
    assert panel[4].gate_number == 5
    assert panel[4].operator_name == "Op 5"
    assert panel[4].active_sessions == 4


@pytest.mark.asyncio
async def test_get_alert_counts_both_succeed():
    repo = MockReportRepo()
    repo.long_stay = 2
    repo.overdue_shifts = 1

    service = ReportService(db=None, report_repo=repo)
    alerts = await service.get_alert_counts()

    assert alerts == {"long_stay": 2, "overdue_shifts": 1}
