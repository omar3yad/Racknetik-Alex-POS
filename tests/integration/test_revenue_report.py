import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserRole
from models.parking_session import ParkingSession, SessionStatus
from models.parking_card import ParkingCard, CardStatus
from services.auth_service import AuthService
from utils.time import cairo_now


async def setup_admin(
    db: AsyncSession, auth_service: AuthService, client: AsyncClient
) -> User:
    admin = User(
        username="admin_rev_test",
        full_name="Admin Rev Tester",
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
async def test_revenue_summary_correct_totals(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    cards = [
        ParkingCard(card_code=f"REV_SESS_C_{i}", status=CardStatus.AVAILABLE)
        for i in range(1, 4)
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
            entry_time=now - timedelta(minutes=30),
            exit_time=now,
            duration_minutes=30,
            amount_charged=1000,
            status=SessionStatus.COMPLETED,
        )
        for c in cards
    ]
    db_session.add_all(sessions)
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/reports/revenue")
    assert res.status_code == 200
    summary = res.json()["data"]["summary"]
    assert summary["total_revenue_piastres"] == 3000
    assert summary["avg_duration_minutes"] == 30
    assert summary["total_sessions"] == 3


@pytest.mark.asyncio
async def test_revenue_excludes_active_sessions(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    card = ParkingCard(card_code="ACTIVE_REV_C", status=CardStatus.IN_USE)
    db_session.add(card)
    await db_session.flush()

    session = ParkingSession(
        card_id=card.id,
        card_code=card.card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=datetime.utcnow() - timedelta(minutes=10),
        amount_charged=None,
        status=SessionStatus.ACTIVE,
    )
    db_session.add(session)
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/reports/revenue")
    assert res.status_code == 200
    summary = res.json()["data"]["summary"]
    assert summary["total_revenue_piastres"] == 0
    assert summary["total_sessions"] == 0


@pytest.mark.asyncio
async def test_daily_revenue_fills_empty_days(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    today = cairo_now().date()
    day1 = today - timedelta(days=2)
    day2 = today - timedelta(days=1)
    day3 = today

    c1 = ParkingCard(card_code="D1_C", status=CardStatus.AVAILABLE)
    c3 = ParkingCard(card_code="D3_C", status=CardStatus.AVAILABLE)
    db_session.add_all([c1, c3])
    await db_session.flush()

    # Session on day 1
    s1 = ParkingSession(
        card_id=c1.id,
        card_code=c1.card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=datetime.utcnow() - timedelta(days=2, hours=1),
        exit_time=datetime.utcnow() - timedelta(days=2),
        amount_charged=1500,
        status=SessionStatus.COMPLETED,
    )
    # Session on day 3
    s3 = ParkingSession(
        card_id=c3.id,
        card_code=c3.card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=datetime.utcnow() - timedelta(hours=1),
        exit_time=datetime.utcnow(),
        amount_charged=2500,
        status=SessionStatus.COMPLETED,
    )
    db_session.add_all([s1, s3])
    await db_session.commit()

    res = await async_client.get(
        f"/api/v1/admin/reports/revenue?start_date={day1}&end_date={day3}"
    )
    assert res.status_code == 200
    daily = res.json()["data"]["daily"]
    assert len(daily) == 3

    # Day 1
    assert daily[0]["date_str"] == day1.strftime("%Y-%m-%d")
    assert daily[0]["session_count"] == 1
    assert daily[0]["total_piastres"] == 1500

    # Day 2 (empty day)
    assert daily[1]["date_str"] == day2.strftime("%Y-%m-%d")
    assert daily[1]["session_count"] == 0
    assert daily[1]["total_piastres"] == 0

    # Day 3
    assert daily[2]["date_str"] == day3.strftime("%Y-%m-%d")
    assert daily[2]["session_count"] == 1
    assert daily[2]["total_piastres"] == 2500


@pytest.mark.asyncio
async def test_revenue_by_gate_groups_correctly(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    cards = [
        ParkingCard(card_code=f"G_REV_C_{i}", status=CardStatus.AVAILABLE)
        for i in range(1, 4)
    ]
    db_session.add_all(cards)
    await db_session.flush()

    now = datetime.utcnow()
    # 2 on Gate 1, 1 on Gate 2
    s1 = ParkingSession(
        card_id=cards[0].id,
        card_code=cards[0].card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=now - timedelta(hours=1),
        exit_time=now,
        amount_charged=1000,
        status=SessionStatus.COMPLETED,
    )
    s2 = ParkingSession(
        card_id=cards[1].id,
        card_code=cards[1].card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=now - timedelta(hours=1),
        exit_time=now,
        amount_charged=2000,
        status=SessionStatus.COMPLETED,
    )
    s3 = ParkingSession(
        card_id=cards[2].id,
        card_code=cards[2].card_code,
        gate_number=2,
        shift_id=1,
        operator_id=admin.id,
        entry_time=now - timedelta(hours=1),
        exit_time=now,
        amount_charged=3000,
        status=SessionStatus.COMPLETED,
    )
    db_session.add_all([s1, s2, s3])
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/reports/revenue")
    assert res.status_code == 200
    by_gate = res.json()["data"]["by_gate"]

    g1 = next(g for g in by_gate if g["gate_number"] == 1)
    assert g1["session_count"] == 2
    assert g1["total_piastres"] == 3000

    g2 = next(g for g in by_gate if g["gate_number"] == 2)
    assert g2["session_count"] == 1
    assert g2["total_piastres"] == 3000
