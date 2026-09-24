import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserRole
from models.shift import Shift
from models.parking_session import ParkingSession, SessionStatus, PaymentMethod
from models.parking_card import ParkingCard, CardStatus
from services.auth_service import AuthService


async def setup_admin(
    db: AsyncSession, auth_service: AuthService, client: AsyncClient
) -> User:
    admin = User(
        username="admin_api_test",
        full_name="Admin API Tester",
        role=UserRole.ADMIN,
        is_active=True,
        hashed_password=auth_service.hash_password("adminpass123"),
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)

    token = auth_service.create_access_token(admin.id, admin.role.value)
    client.cookies.set("pgms_token", token)
    return admin


async def setup_operator(
    db: AsyncSession, auth_service: AuthService, client: AsyncClient
) -> User:
    op = User(
        username="operator_api_test",
        full_name="Operator API Tester",
        role=UserRole.OPERATOR,
        gate_number=1,
        is_active=True,
        hashed_password=auth_service.hash_password("oppass123"),
    )
    db.add(op)
    await db.commit()
    await db.refresh(op)

    token = auth_service.create_access_token(op.id, op.role.value)
    client.cookies.set("pgms_token", token)
    return op


@pytest.mark.asyncio
async def test_admin_api_require_admin(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    # 1. No token -> 401
    res = await async_client.get("/api/v1/admin/stats/live")
    assert res.status_code == 401

    # 2. Operator token -> 403
    await setup_operator(db_session, auth_service, async_client)
    res_op = await async_client.get("/api/v1/admin/stats/live")
    assert res_op.status_code == 403
    assert res_op.json()["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_stats_live_and_gates(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)

    # Live stats
    res = await async_client.get("/api/v1/admin/stats/live")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "active_sessions" in data
    assert "total_capacity" in data
    assert "occupancy_pct" in data
    assert "revenue_today_piastres" in data
    assert "open_shifts" in data

    # Gates panel (always 5 gates)
    res_gates = await async_client.get("/api/v1/admin/stats/gates")
    assert res_gates.status_code == 200
    gates = res_gates.json()["data"]
    assert len(gates) == 5
    assert [g["gate_number"] for g in gates] == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_sessions_list_and_date_validation(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)

    # Invalid date range (start > end) -> 422
    res_invalid = await async_client.get(
        "/api/v1/admin/sessions?start_date=2026-09-25&end_date=2026-09-20"
    )
    assert res_invalid.status_code == 422
    assert res_invalid.json()["code"] == "INVALID_DATE_RANGE"

    # Valid query
    res = await async_client.get("/api/v1/admin/sessions?page=1&size=10")
    assert res.status_code == 200
    body = res.json()
    assert "data" in body
    assert "total" in body
    assert body["page"] == 1
    assert body["size"] == 10


@pytest.mark.asyncio
async def test_session_detail_and_404(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    # 404 for non-existent session
    res_404 = await async_client.get("/api/v1/admin/sessions/999999")
    assert res_404.status_code == 404
    assert res_404.json()["code"] == "SESSION_NOT_FOUND"

    # Create dummy card and session
    card = ParkingCard(card_code="CARD-TEST-001", status=CardStatus.IN_USE)
    db_session.add(card)
    await db_session.flush()

    shift = Shift(
        operator_id=admin.id,
        gate_number=1,
        started_at=datetime.utcnow() - timedelta(hours=2),
        opening_cash_egp=1000,
    )
    db_session.add(shift)
    await db_session.flush()

    session = ParkingSession(
        card_id=card.id,
        card_code=card.card_code,
        status=SessionStatus.ACTIVE,
        gate_number=1,
        shift_id=shift.id,
        operator_id=admin.id,
        entry_time=datetime.utcnow() - timedelta(hours=1),
        payment_method=PaymentMethod.CASH,
        is_paid=False,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    res = await async_client.get(f"/api/v1/admin/sessions/{session.id}")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["id"] == session.id
    assert data["card_code"] == "CARD-TEST-001"
    assert data["status"] == "ACTIVE"
    assert "audit_logs" in data


@pytest.mark.asyncio
async def test_shifts_list_detail_and_force_close(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    shift = Shift(
        operator_id=admin.id,
        gate_number=2,
        started_at=datetime.utcnow() - timedelta(hours=3),
        opening_cash_egp=500,
    )
    db_session.add(shift)
    await db_session.commit()
    await db_session.refresh(shift)

    # 1. Shifts list
    res_list = await async_client.get("/api/v1/admin/shifts")
    assert res_list.status_code == 200
    assert res_list.json()["total"] >= 1

    # 2. Shift detail
    res_detail = await async_client.get(f"/api/v1/admin/shifts/{shift.id}")
    assert res_detail.status_code == 200
    data = res_detail.json()["data"]
    assert data["shift"]["id"] == shift.id
    assert "summary" in data
    assert "sessions" in data

    # 3. Force close
    res_close = await async_client.patch(
        f"/api/v1/admin/shifts/{shift.id}/force-close",
        json={"closing_cash_egp": 3500, "admin_note": "Admin forced shift closure"},
    )
    assert res_close.status_code == 200
    summary = res_close.json()["data"]
    assert summary["shift_id"] == shift.id
    assert summary["ended_at"] is not None
    assert summary["closing_cash_piastres"] == 3500

    # 4. Force close already closed -> 409
    res_close_again = await async_client.patch(
        f"/api/v1/admin/shifts/{shift.id}/force-close",
        json={"closing_cash_egp": 3500},
    )
    assert res_close_again.status_code == 409
    assert res_close_again.json()["code"] == "SHIFT_ALREADY_CLOSED"


@pytest.mark.asyncio
async def test_reports_revenue_and_csv_exports(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    # 1. Revenue report
    res_rev = await async_client.get("/api/v1/admin/reports/revenue")
    assert res_rev.status_code == 200
    rev_data = res_rev.json()["data"]
    assert "summary" in rev_data
    assert "by_gate" in rev_data
    assert "by_operator" in rev_data
    assert "daily" in rev_data

    # 2. Sessions CSV export
    res_sess_csv = await async_client.get("/api/v1/admin/sessions/export/csv")
    assert res_sess_csv.status_code == 200
    assert "text/csv" in res_sess_csv.headers["content-type"]
    assert "attachment; filename=" in res_sess_csv.headers["content-disposition"]
    csv_text = res_sess_csv.text
    assert "رقم الجلسة" in csv_text

    # 3. Reports CSV export
    res_rep_csv = await async_client.get("/api/v1/admin/reports/export/csv")
    assert res_rep_csv.status_code == 200
    assert "text/csv" in res_rep_csv.headers["content-type"]
    assert "attachment; filename=" in res_rep_csv.headers["content-disposition"]

    # 4. Shift CSV export
    shift = Shift(
        operator_id=admin.id,
        gate_number=1,
        started_at=datetime.utcnow() - timedelta(hours=2),
        opening_cash_egp=1000,
    )
    db_session.add(shift)
    await db_session.commit()
    await db_session.refresh(shift)

    res_shift_csv = await async_client.get(
        f"/api/v1/admin/shifts/{shift.id}/export/csv"
    )
    assert res_shift_csv.status_code == 200
    assert "text/csv" in res_shift_csv.headers["content-type"]
    assert f"pgms_shift_{shift.id}_" in res_shift_csv.headers["content-disposition"]
