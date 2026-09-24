from datetime import datetime, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.parking_card import ParkingCard, CardStatus
from models.parking_session import ParkingSession, SessionStatus
from models.user import User, UserRole
from services.auth_service import AuthService


async def setup_admin(
    db: AsyncSession, auth_service: AuthService, client: AsyncClient
) -> User:
    admin = User(
        username="admin_csv_test",
        full_name="Admin CSV Tester",
        role=UserRole.ADMIN,
        is_active=True,
        hashed_password=auth_service.hash_password("adminpass123"),
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)

    token = auth_service.create_access_token(admin.id, admin.role.value)
    client.cookies.set("pgms_token", token)
    client.headers["Authorization"] = f"Bearer {token}"
    return admin


@pytest.mark.asyncio
async def test_sessions_csv_content_type(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    card1 = ParkingCard(card_code="CSV_C1", status=CardStatus.IN_USE)
    card2 = ParkingCard(card_code="CSV_C2", status=CardStatus.IN_USE)
    db_session.add_all([card1, card2])
    await db_session.flush()

    now = datetime.utcnow()
    s1 = ParkingSession(
        card_id=card1.id,
        card_code=card1.card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=now - timedelta(hours=2),
        exit_time=now - timedelta(hours=1),
        status=SessionStatus.COMPLETED,
        amount_charged=1000,
    )
    s2 = ParkingSession(
        card_id=card2.id,
        card_code=card2.card_code,
        gate_number=2,
        shift_id=1,
        operator_id=admin.id,
        entry_time=now - timedelta(hours=1),
        exit_time=now,
        status=SessionStatus.COMPLETED,
        amount_charged=1500,
    )
    db_session.add_all([s1, s2])
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/sessions/export/csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_sessions_csv_has_bom(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)

    res = await async_client.get("/api/v1/admin/sessions/export/csv")
    assert res.status_code == 200
    assert res.content[:3] == b"\xef\xbb\xbf"


@pytest.mark.asyncio
async def test_sessions_csv_header_in_arabic(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)

    res = await async_client.get("/api/v1/admin/sessions/export/csv")
    assert res.status_code == 200
    decoded = res.content[:500].decode("utf-8")
    assert "رقم الجلسة" in decoded


@pytest.mark.asyncio
async def test_sessions_csv_empty_filter_returns_header_only(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)

    res = await async_client.get(
        "/api/v1/admin/sessions/export/csv?start_date=1900-01-01&end_date=1900-01-02"
    )
    assert res.status_code == 200
    assert res.content[:3] == b"\xef\xbb\xbf"

    decoded = res.content.decode("utf-8")
    lines = [line.strip() for line in decoded.splitlines() if line.strip()]
    assert len(lines) == 1
    assert "رقم الجلسة" in lines[0]


@pytest.mark.asyncio
async def test_sessions_csv_none_values_no_null_string(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    card = ParkingCard(card_code="CSV_NULL_C", status=CardStatus.IN_USE)
    db_session.add(card)
    await db_session.flush()

    s = ParkingSession(
        card_id=card.id,
        card_code=card.card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=datetime.utcnow() - timedelta(minutes=15),
        exit_time=None,
        plate_number=None,
        duration_minutes=None,
        amount_charged=None,
        status=SessionStatus.ACTIVE,
    )
    db_session.add(s)
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/sessions/export/csv")
    assert res.status_code == 200
    decoded = res.content.decode("utf-8")
    assert "None" not in decoded
    assert "null" not in decoded


@pytest.mark.asyncio
async def test_sessions_csv_monetary_latin_digits(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    admin = await setup_admin(db_session, auth_service, async_client)

    card = ParkingCard(card_code="CSV_MONEY_C", status=CardStatus.IN_USE)
    db_session.add(card)
    await db_session.flush()

    now = datetime.utcnow()
    s = ParkingSession(
        card_id=card.id,
        card_code=card.card_code,
        gate_number=1,
        shift_id=1,
        operator_id=admin.id,
        entry_time=now - timedelta(hours=3),
        exit_time=now,
        status=SessionStatus.COMPLETED,
        amount_charged=2500,
    )
    db_session.add(s)
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/sessions/export/csv")
    assert res.status_code == 200
    decoded = res.content.decode("utf-8")
    assert "25.00" in decoded
