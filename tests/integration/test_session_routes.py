import pytest
from datetime import datetime, timedelta
from sqlalchemy import select
from models.user import User, UserRole
from models.parking_card import ParkingCard, CardStatus
from models.parking_session import ParkingSession, SessionStatus
from models.pricing_rule import PricingRule
from models.shift import Shift

async def setup_operator(db_session, auth_service, async_client):
    hashed = auth_service.hash_password("operatorpass")
    user = User(
        full_name="Operator User",
        username="operator1",
        hashed_password=hashed,
        role=UserRole.OPERATOR,
        gate_number=1,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    token = auth_service.create_access_token(user.id, user.role.value)
    async_client.cookies.set("pgms_token", token)
    return user

async def setup_pricing_rule(db_session):
    rule = PricingRule(
        label="Standard Rule",
        rate_per_hour=1000, # 10 EGP
        minimum_charge=500, # 5 EGP
        grace_period_mins=15,
        lost_card_penalty=2000, # 20 EGP
        is_active=True,
        created_by=1,
        effective_from=datetime.utcnow()
    )
    db_session.add(rule)
    await db_session.commit()
    return rule

async def open_operator_shift(db_session, operator_id):
    shift = Shift(
        operator_id=operator_id,
        gate_number=1,
        started_at=datetime.utcnow(),
        opening_cash_egp=5000,
    )
    db_session.add(shift)
    await db_session.commit()
    return shift

@pytest.mark.asyncio
async def test_open_session_happy_path(async_client, db_session, auth_service):
    op = await setup_operator(db_session, auth_service, async_client)
    await setup_pricing_rule(db_session)
    await open_operator_shift(db_session, op.id)
    
    # Create card
    card = ParkingCard(card_code="CARD-0001", status=CardStatus.AVAILABLE)
    db_session.add(card)
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/sessions/",
        json={"card_code": "CARD-0001"}
    )
    assert response.status_code == 201
    json_data = response.json()
    assert json_data["data"]["status"] == "ACTIVE"
    assert json_data["data"]["card_code"] == "CARD-0001"

@pytest.mark.asyncio
async def test_open_session_no_shift(async_client, db_session, auth_service):
    await setup_operator(db_session, auth_service, async_client)
    await setup_pricing_rule(db_session)
    # Note: no active shift opened
    
    card = ParkingCard(card_code="CARD-0001", status=CardStatus.AVAILABLE)
    db_session.add(card)
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/sessions/",
        json={"card_code": "CARD-0001"}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "NO_ACTIVE_SHIFT"

@pytest.mark.asyncio
async def test_open_session_card_already_active(async_client, db_session, auth_service):
    op = await setup_operator(db_session, auth_service, async_client)
    await setup_pricing_rule(db_session)
    await open_operator_shift(db_session, op.id)
    
    card = ParkingCard(card_code="CARD-0001", status=CardStatus.IN_USE)
    session = ParkingSession(
        card_code="CARD-0001",
        status=SessionStatus.ACTIVE,
        entry_time=datetime.utcnow(),
        gate_number=1,
        operator_id=op.id,
    )
    db_session.add_all([card, session])
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/sessions/",
        json={"card_code": "CARD-0001"}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CARD_ALREADY_ACTIVE"

@pytest.mark.asyncio
async def test_open_session_card_not_found(async_client, db_session, auth_service):
    op = await setup_operator(db_session, auth_service, async_client)
    await setup_pricing_rule(db_session)
    await open_operator_shift(db_session, op.id)

    response = await async_client.post(
        "/api/v1/sessions/",
        json={"card_code": "CARD-NONEXISTENT"}
    )
    assert response.status_code == 404
    assert response.json()["code"] == "CARD_NOT_FOUND"

@pytest.mark.asyncio
async def test_exit_session_happy_path(async_client, db_session, auth_service):
    op = await setup_operator(db_session, auth_service, async_client)
    rule = await setup_pricing_rule(db_session)
    await open_operator_shift(db_session, op.id)
    
    card = ParkingCard(card_code="CARD-0001", status=CardStatus.IN_USE)
    session = ParkingSession(
        card_code="CARD-0001",
        status=SessionStatus.ACTIVE,
        entry_time=datetime.utcnow() - timedelta(hours=2), # 2 hours duration
        gate_number=1,
        operator_id=op.id,
    )
    db_session.add_all([card, session])
    await db_session.commit()

    response = await async_client.patch(f"/api/v1/sessions/{session.id}/exit")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["status"] == "COMPLETED"
    assert json_data["data"]["amount_charged"] == 2000 # 2 hours * 10 EGP
    assert json_data["data"]["is_paid"] is True

@pytest.mark.asyncio
async def test_exit_session_grace_period(async_client, db_session, auth_service):
    op = await setup_operator(db_session, auth_service, async_client)
    rule = await setup_pricing_rule(db_session)
    await open_operator_shift(db_session, op.id)
    
    card = ParkingCard(card_code="CARD-0001", status=CardStatus.IN_USE)
    session = ParkingSession(
        card_code="CARD-0001",
        status=SessionStatus.ACTIVE,
        entry_time=datetime.utcnow() - timedelta(minutes=5), # within grace period (15 mins)
        gate_number=1,
        operator_id=op.id,
    )
    db_session.add_all([card, session])
    await db_session.commit()

    response = await async_client.patch(f"/api/v1/sessions/{session.id}/exit")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["price_breakdown"]["is_grace_period"] is True
    assert json_data["data"]["amount_charged"] == rule.minimum_charge

@pytest.mark.asyncio
async def test_exit_session_not_active(async_client, db_session, auth_service):
    op = await setup_operator(db_session, auth_service, async_client)
    await setup_pricing_rule(db_session)
    await open_operator_shift(db_session, op.id)
    
    card = ParkingCard(card_code="CARD-0001", status=CardStatus.AVAILABLE)
    session = ParkingSession(
        card_code="CARD-0001",
        status=SessionStatus.COMPLETED,
        entry_time=datetime.utcnow() - timedelta(hours=2),
        exit_time=datetime.utcnow(),
        gate_number=1,
        operator_id=op.id,
    )
    db_session.add_all([card, session])
    await db_session.commit()

    response = await async_client.patch(f"/api/v1/sessions/{session.id}/exit")
    assert response.status_code == 409
    assert response.json()["code"] == "SESSION_NOT_ACTIVE"

@pytest.mark.asyncio
async def test_exit_no_pricing_rule(async_client, db_session, auth_service):
    op = await setup_operator(db_session, auth_service, async_client)
    await open_operator_shift(db_session, op.id)
    # Note: no active pricing rules seeded
    
    card = ParkingCard(card_code="CARD-0001", status=CardStatus.IN_USE)
    session = ParkingSession(
        card_code="CARD-0001",
        status=SessionStatus.ACTIVE,
        entry_time=datetime.utcnow() - timedelta(hours=2),
        gate_number=1,
        operator_id=op.id,
    )
    db_session.add_all([card, session])
    await db_session.commit()

    response = await async_client.patch(f"/api/v1/sessions/{session.id}/exit")
    assert response.status_code == 503
    assert response.json()["code"] == "NO_ACTIVE_PRICING_RULE"

@pytest.mark.asyncio
async def test_lost_card_happy_path(async_client, db_session, auth_service):
    op = await setup_operator(db_session, auth_service, async_client)
    rule = await setup_pricing_rule(db_session)
    await open_operator_shift(db_session, op.id)
    
    card = ParkingCard(card_code="CARD-0001", status=CardStatus.IN_USE)
    session = ParkingSession(
        card_code="CARD-0001",
        status=SessionStatus.ACTIVE,
        entry_time=datetime.utcnow() - timedelta(hours=2),
        gate_number=1,
        operator_id=op.id,
    )
    db_session.add_all([card, session])
    await db_session.commit()

    response = await async_client.patch(
        f"/api/v1/sessions/{session.id}/lost-card",
        json={"plate_number": "أ ب ج 123", "notes": "test"}
    )
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["status"] == "LOST_CARD"
    assert json_data["data"]["is_lost_card"] is True
    assert json_data["data"]["lost_card_penalty_applied"] == rule.lost_card_penalty

@pytest.mark.asyncio
async def test_amount_not_accepted_from_client(async_client, db_session, auth_service):
    op = await setup_operator(db_session, auth_service, async_client)
    await setup_pricing_rule(db_session)
    await open_operator_shift(db_session, op.id)
    
    card = ParkingCard(card_code="CARD-0001", status=CardStatus.AVAILABLE)
    db_session.add(card)
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/sessions/",
        json={"card_code": "CARD-0001", "amount_charged": 99999}
    )
    assert response.status_code == 201
    
    # Query DB to check that amount_charged is NULL
    stmt = select(ParkingSession).where(ParkingSession.id == response.json()["data"]["id"])
    res = await db_session.execute(stmt)
    db_session_obj = res.scalar()
    assert db_session_obj.amount_charged is None
