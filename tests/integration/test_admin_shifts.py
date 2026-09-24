import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserRole
from models.shift import Shift
from models.parking_session import ParkingSession, SessionStatus
from models.parking_card import ParkingCard, CardStatus
from models.audit_log import AuditLog
from services.auth_service import AuthService


async def setup_admin(
    db: AsyncSession, auth_service: AuthService, client: AsyncClient
) -> User:
    admin = User(
        username="admin_shifts_test",
        full_name="Admin Shifts Tester",
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


@pytest.mark.asyncio
async def test_list_shifts_paginated(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    now = datetime.utcnow()
    shifts = [
        Shift(
            operator_id=admin.id,
            gate_number=1,
            started_at=now - timedelta(hours=i),
            ended_at=now - timedelta(hours=i, minutes=-30),
            opening_cash_egp=1000,
        )
        for i in range(25)
    ]
    db_session.add_all(shifts)
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/shifts")
    assert res.status_code == 200
    json_data = res.json()
    assert json_data["total"] >= 25
    assert len(json_data["data"]) == 20


@pytest.mark.asyncio
async def test_filter_shifts_by_status_open(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    now = datetime.utcnow()
    # 2 open, 3 closed
    s_open1 = Shift(
        operator_id=admin.id,
        gate_number=1,
        started_at=now,
        ended_at=None,
        opening_cash_egp=0,
    )
    s_open2 = Shift(
        operator_id=admin.id,
        gate_number=2,
        started_at=now,
        ended_at=None,
        opening_cash_egp=0,
    )
    s_closed1 = Shift(
        operator_id=admin.id,
        gate_number=1,
        started_at=now - timedelta(hours=5),
        ended_at=now - timedelta(hours=4),
        opening_cash_egp=0,
    )
    s_closed2 = Shift(
        operator_id=admin.id,
        gate_number=1,
        started_at=now - timedelta(hours=3),
        ended_at=now - timedelta(hours=2),
        opening_cash_egp=0,
    )
    s_closed3 = Shift(
        operator_id=admin.id,
        gate_number=1,
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=1),
        opening_cash_egp=0,
    )
    db_session.add_all([s_open1, s_open2, s_closed1, s_closed2, s_closed3])
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/shifts?status=open")
    assert res.status_code == 200
    assert res.json()["total"] == 2
    for s in res.json()["data"]:
        assert s["ended_at"] is None


@pytest.mark.asyncio
async def test_filter_shifts_overdue(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    now = datetime.utcnow()
    # Overdue shift (> 12 hours ago, ended_at is None)
    s_overdue = Shift(
        operator_id=admin.id,
        gate_number=1,
        started_at=now - timedelta(hours=13),
        ended_at=None,
        opening_cash_egp=0,
    )
    # Recent shift (2 hours ago, ended_at is None)
    s_recent = Shift(
        operator_id=admin.id,
        gate_number=2,
        started_at=now - timedelta(hours=2),
        ended_at=None,
        opening_cash_egp=0,
    )
    db_session.add_all([s_overdue, s_recent])
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/shifts?overdue=true")
    assert res.status_code == 200
    data = res.json()["data"]
    ids = [item["id"] for item in data]
    assert s_overdue.id in ids
    assert s_recent.id not in ids


@pytest.mark.asyncio
async def test_force_close_shift_success(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    shift = Shift(
        operator_id=admin.id,
        gate_number=1,
        started_at=datetime.utcnow() - timedelta(hours=4),
        ended_at=None,
        opening_cash_egp=1000,
    )
    db_session.add(shift)
    await db_session.commit()
    await db_session.refresh(shift)

    res = await async_client.patch(
        f"/api/v1/admin/shifts/{shift.id}/force-close",
        json={"closing_cash_egp": 50000, "admin_note": "Admin forced shift end"},
    )
    assert res.status_code == 200

    # Query DB directly to verify ended_at is not null
    updated = await db_session.get(Shift, shift.id)
    await db_session.refresh(updated)
    assert updated.ended_at is not None
    assert updated.closing_cash_egp == 50000
    assert updated.admin_override_note == "Admin forced shift end"


@pytest.mark.asyncio
async def test_force_close_already_closed_returns_409(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    shift = Shift(
        operator_id=admin.id,
        gate_number=1,
        started_at=datetime.utcnow() - timedelta(hours=4),
        ended_at=datetime.utcnow() - timedelta(hours=1),
        opening_cash_egp=1000,
    )
    db_session.add(shift)
    await db_session.commit()
    await db_session.refresh(shift)

    res = await async_client.patch(
        f"/api/v1/admin/shifts/{shift.id}/force-close",
        json={"closing_cash_egp": 2000},
    )
    assert res.status_code == 409
    assert res.json().get("code") == "SHIFT_ALREADY_CLOSED"


@pytest.mark.asyncio
async def test_force_close_creates_audit_log(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    shift = Shift(
        operator_id=admin.id,
        gate_number=1,
        started_at=datetime.utcnow() - timedelta(hours=3),
        ended_at=None,
        opening_cash_egp=1000,
    )
    db_session.add(shift)
    await db_session.commit()
    await db_session.refresh(shift)

    res = await async_client.patch(
        f"/api/v1/admin/shifts/{shift.id}/force-close",
        json={"closing_cash_egp": 1500, "admin_note": "Audit verification"},
    )
    assert res.status_code == 200

    audit_res = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "shift",
            AuditLog.entity_id == shift.id,
            AuditLog.action == "SHIFT_FORCE_CLOSED",
        )
    )
    log_entry = audit_res.scalars().first()
    assert log_entry is not None
    assert log_entry.actor_id == admin.id


@pytest.mark.asyncio
async def test_shift_export_csv_returns_bom(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    shift = Shift(
        operator_id=admin.id,
        gate_number=1,
        started_at=datetime.utcnow() - timedelta(hours=2),
        ended_at=datetime.utcnow(),
        opening_cash_egp=1000,
    )
    db_session.add(shift)
    await db_session.commit()
    await db_session.refresh(shift)

    cards = [
        ParkingCard(card_code=f"SH_EXP_{i}", status=CardStatus.AVAILABLE)
        for i in range(3)
    ]
    db_session.add_all(cards)
    await db_session.flush()

    sessions = [
        ParkingSession(
            card_id=c.id,
            card_code=c.card_code,
            gate_number=1,
            shift_id=shift.id,
            operator_id=admin.id,
            entry_time=datetime.utcnow() - timedelta(minutes=30),
            exit_time=datetime.utcnow(),
            amount_charged=1000,
            status=SessionStatus.COMPLETED,
        )
        for c in cards
    ]
    db_session.add_all(sessions)
    await db_session.commit()

    res = await async_client.get(f"/api/v1/admin/shifts/{shift.id}/export/csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")
    assert res.content.startswith(b"\xef\xbb\xbf")
