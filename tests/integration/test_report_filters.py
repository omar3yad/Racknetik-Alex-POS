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
        username="admin_filters_test",
        full_name="Admin Filters Tester",
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
async def test_session_filter_by_date_range(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)
    today = cairo_now().date()

    # Yesterday, today, tomorrow
    c_yest = ParkingCard(card_code="C_YEST", status=CardStatus.IN_USE)
    c_today = ParkingCard(card_code="C_TODAY", status=CardStatus.IN_USE)
    c_tom = ParkingCard(card_code="C_TOM", status=CardStatus.IN_USE)
    db_session.add_all([c_yest, c_today, c_tom])
    await db_session.flush()

    now_utc = datetime.utcnow()
    s_yest = ParkingSession(
        card_id=c_yest.id,
        card_code=c_yest.card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=now_utc - timedelta(days=2, hours=1),
        exit_time=now_utc - timedelta(days=2),
        status=SessionStatus.COMPLETED,
    )
    s_today = ParkingSession(
        card_id=c_today.id,
        card_code=c_today.card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=now_utc - timedelta(hours=1),
        exit_time=now_utc,
        status=SessionStatus.COMPLETED,
    )
    s_tom = ParkingSession(
        card_id=c_tom.id,
        card_code=c_tom.card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=now_utc + timedelta(days=2),
        exit_time=now_utc + timedelta(days=2, hours=1),
        status=SessionStatus.COMPLETED,
    )
    db_session.add_all([s_yest, s_today, s_tom])
    await db_session.commit()

    res = await async_client.get(
        f"/api/v1/admin/sessions?start_date={today}&end_date={today}"
    )
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["data"][0]["card_code"] == "C_TODAY"


@pytest.mark.asyncio
async def test_session_filter_by_gate(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    c1 = ParkingCard(card_code="GATE1_C", status=CardStatus.IN_USE)
    c2 = ParkingCard(card_code="GATE2_C", status=CardStatus.IN_USE)
    db_session.add_all([c1, c2])
    await db_session.flush()

    s1 = ParkingSession(
        card_id=c1.id,
        card_code=c1.card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=datetime.utcnow(),
        status=SessionStatus.ACTIVE,
    )
    s2 = ParkingSession(
        card_id=c2.id,
        card_code=c2.card_code,
        gate_number=2,
        shift_id=1,
        operator_id=admin.id,
        entry_time=datetime.utcnow(),
        status=SessionStatus.ACTIVE,
    )
    db_session.add_all([s1, s2])
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/sessions?gate_number=1")
    assert res.status_code == 200
    data = res.json()["data"]
    assert all(item["gate_number"] == 1 for item in data)
    assert any(item["card_code"] == "GATE1_C" for item in data)


@pytest.mark.asyncio
async def test_session_filter_by_status_active(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    cards = [
        ParkingCard(card_code=f"STAT_FLT_{i}", status=CardStatus.IN_USE)
        for i in range(1, 4)
    ]
    db_session.add_all(cards)
    await db_session.flush()

    s1 = ParkingSession(
        card_id=cards[0].id,
        card_code=cards[0].card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=datetime.utcnow(),
        status=SessionStatus.ACTIVE,
    )
    s2 = ParkingSession(
        card_id=cards[1].id,
        card_code=cards[1].card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=datetime.utcnow(),
        status=SessionStatus.ACTIVE,
    )
    s3 = ParkingSession(
        card_id=cards[2].id,
        card_code=cards[2].card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=datetime.utcnow() - timedelta(hours=1),
        exit_time=datetime.utcnow(),
        amount_charged=1000,
        status=SessionStatus.COMPLETED,
    )
    db_session.add_all([s1, s2, s3])
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/sessions?status=ACTIVE")
    assert res.status_code == 200
    assert res.json()["total"] == 2
    for item in res.json()["data"]:
        assert item["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_session_filter_by_card_code_partial(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    card = ParkingCard(card_code="CARD-0042", status=CardStatus.IN_USE)
    db_session.add(card)
    await db_session.flush()

    session = ParkingSession(
        card_id=card.id,
        card_code=card.card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=datetime.utcnow(),
        status=SessionStatus.ACTIVE,
    )
    db_session.add(session)
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/sessions?card_code=0042")
    assert res.status_code == 200
    assert res.json()["total"] >= 1
    codes = [item["card_code"] for item in res.json()["data"]]
    assert "CARD-0042" in codes


@pytest.mark.asyncio
async def test_session_filter_card_code_sql_injection_safe(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)

    # Searching with literal '%' should be escaped and not match
    # non-literal percent signs
    res = await async_client.get("/api/v1/admin/sessions?card_code=%")
    assert res.status_code == 200
    # No SQL error, and since no card has literal '%' in code, returns 0
    assert res.json()["total"] == 0


@pytest.mark.asyncio
async def test_session_filter_long_stay(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    c_old = ParkingCard(card_code="C_OLD_LS", status=CardStatus.IN_USE)
    c_new = ParkingCard(card_code="C_NEW_LS", status=CardStatus.IN_USE)
    db_session.add_all([c_old, c_new])
    await db_session.flush()

    s_old = ParkingSession(
        card_id=c_old.id,
        card_code=c_old.card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=datetime.utcnow() - timedelta(hours=25),
        status=SessionStatus.ACTIVE,
    )
    s_new = ParkingSession(
        card_id=c_new.id,
        card_code=c_new.card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=datetime.utcnow() - timedelta(hours=2),
        status=SessionStatus.ACTIVE,
    )
    db_session.add_all([s_old, s_new])
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/sessions?long_stay=true")
    assert res.status_code == 200
    codes = [item["card_code"] for item in res.json()["data"]]
    assert "C_OLD_LS" in codes
    assert "C_NEW_LS" not in codes


@pytest.mark.asyncio
async def test_invalid_date_range_returns_422(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)

    res = await async_client.get(
        "/api/v1/admin/sessions?start_date=2024-08-31&end_date=2024-08-01"
    )
    assert res.status_code == 422
    assert res.json().get("code") == "INVALID_DATE_RANGE"
