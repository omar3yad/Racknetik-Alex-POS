import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserRole
from models.shift import Shift
from models.parking_session import ParkingSession, SessionStatus
from models.parking_card import ParkingCard, CardStatus
from services.auth_service import AuthService


async def setup_admin(
    db: AsyncSession, auth_service: AuthService, client: AsyncClient
) -> User:
    admin = User(
        username="admin_stats_test",
        full_name="Admin Stats Tester",
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
async def test_live_stats_empty_db(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)
    res = await async_client.get("/api/v1/admin/stats/live")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["active_sessions"] == 0
    assert data["occupancy_pct"] == 0
    assert data["revenue_today_piastres"] == 0
    assert data["open_shifts"] == 0


@pytest.mark.asyncio
async def test_live_stats_with_active_sessions(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    cards = [
        ParkingCard(card_code=f"STAT_CARD_{i}", status=CardStatus.IN_USE)
        for i in range(1, 4)
    ]
    db_session.add_all(cards)
    await db_session.flush()

    sessions = [
        ParkingSession(
            card_id=c.id,
            card_code=c.card_code,
            gate_number=1,
            shift_id=1,
            operator_id=admin.id,
            entry_time=datetime.utcnow() - timedelta(minutes=10 * i),
            status=SessionStatus.ACTIVE,
        )
        for i, c in enumerate(cards)
    ]
    db_session.add_all(sessions)
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/stats/live")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["active_sessions"] == 3


@pytest.mark.asyncio
async def test_live_stats_revenue_today(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    cards = [
        ParkingCard(card_code=f"REV_CARD_{i}", status=CardStatus.AVAILABLE)
        for i in range(1, 3)
    ]
    db_session.add_all(cards)
    await db_session.flush()

    now = datetime.utcnow()
    sessions = [
        ParkingSession(
            card_id=c.id,
            card_code=c.card_code,
            gate_number=1,
            shift_id=1,
            operator_id=admin.id,
            entry_time=now - timedelta(hours=1),
            exit_time=now,
            amount_charged=2500,
            status=SessionStatus.COMPLETED,
        )
        for c in cards
    ]
    db_session.add_all(sessions)
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/stats/live")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["revenue_today_piastres"] == 5000


@pytest.mark.asyncio
async def test_live_stats_revenue_excludes_yesterday(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    card = ParkingCard(card_code="YESTERDAY_CARD", status=CardStatus.AVAILABLE)
    db_session.add(card)
    await db_session.flush()

    yesterday_exit = datetime.utcnow() - timedelta(hours=25)
    session = ParkingSession(
        card_id=card.id,
        card_code=card.card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=yesterday_exit - timedelta(hours=2),
        exit_time=yesterday_exit,
        amount_charged=4000,
        status=SessionStatus.COMPLETED,
    )
    db_session.add(session)
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/stats/live")
    assert res.status_code == 200
    data = res.json()["data"]
    # 4000 from yesterday must NOT be counted today
    assert data["revenue_today_piastres"] == 0


@pytest.mark.asyncio
async def test_gate_panel_endpoint(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)

    op2 = User(
        username="gate2_op",
        full_name="Gate Two Operator",
        role=UserRole.OPERATOR,
        gate_number=2,
        is_active=True,
        hashed_password=auth_service.hash_password("op2pass"),
    )
    db_session.add(op2)
    await db_session.flush()

    shift2 = Shift(
        operator_id=op2.id,
        gate_number=2,
        started_at=datetime.utcnow() - timedelta(hours=1),
        opening_cash_egp=1000,
    )
    db_session.add(shift2)
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/stats/gates")
    assert res.status_code == 200
    gates = res.json()["data"]
    assert len(gates) == 5

    gate2 = next(g for g in gates if g["gate_number"] == 2)
    assert gate2["operator_name"] == "Gate Two Operator"
    assert gate2["operator_id"] == op2.id

    other_gates = [g for g in gates if g["gate_number"] != 2]
    for og in other_gates:
        assert og["operator_name"] is None
