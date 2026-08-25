import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from models.user import User, UserRole
from models.parking_card import ParkingCard, CardStatus
from models.parking_session import ParkingSession, SessionStatus
from models.pricing_rule import PricingRule
from models.shift import Shift

async def setup_user(db_session, auth_service, async_client):
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
        rate_per_hour=1000,
        minimum_charge=500,
        grace_period_mins=15,
        lost_card_penalty=2000,
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
async def test_complete_entry_to_exit_flow(async_client, db_session, auth_service):
    op = await setup_user(db_session, auth_service, async_client)
    rule = await setup_pricing_rule(db_session)
    await open_operator_shift(db_session, op.id)
    
    # 1. Create card
    card = ParkingCard(card_code="CARD-FLOW-001", status=CardStatus.AVAILABLE)
    db_session.add(card)
    await db_session.commit()

    # 2. Entry
    entry_resp = await async_client.post("/api/v1/sessions/", json={"card_code": "CARD-FLOW-001"})
    assert entry_resp.status_code == 201
    sess_id = entry_resp.json()["data"]["id"]
    
    # Check status IN_USE
    await db_session.refresh(card)
    assert card.status == CardStatus.IN_USE

    # Manually adjust entry time to 2 hours ago
    sess = await db_session.get(ParkingSession, sess_id)
    sess.entry_time = datetime.utcnow() - timedelta(hours=2)
    await db_session.commit()

    # 3. Exit
    exit_resp = await async_client.patch(f"/api/v1/sessions/{sess_id}/exit")
    assert exit_resp.status_code == 200
    assert exit_resp.json()["data"]["status"] == "COMPLETED"
    assert exit_resp.json()["data"]["amount_charged"] == 2000
    
    # Check status AVAILABLE
    await db_session.refresh(card)
    assert card.status == CardStatus.AVAILABLE

    # 4. Receipt
    receipt_resp = await async_client.get(f"/api/v1/sessions/{sess_id}/receipt")
    assert receipt_resp.status_code == 200
    receipt_data = receipt_resp.json()["data"]
    assert receipt_data["session_id"] == sess_id
    assert receipt_data["card_code"] == "CARD-FLOW-001"
    assert receipt_data["total_amount"] == 2000
    assert receipt_data["is_lost_card"] is False

@pytest.mark.asyncio
async def test_complete_lost_card_flow(async_client, db_session, auth_service):
    op = await setup_user(db_session, auth_service, async_client)
    rule = await setup_pricing_rule(db_session)
    await open_operator_shift(db_session, op.id)
    
    # 1. Create card & open session
    card = ParkingCard(card_code="CARD-FLOW-002", status=CardStatus.AVAILABLE)
    db_session.add(card)
    await db_session.commit()
    
    entry_resp = await async_client.post("/api/v1/sessions/", json={"card_code": "CARD-FLOW-002"})
    sess_id = entry_resp.json()["data"]["id"]

    # 2. Resolve lost card
    lost_resp = await async_client.patch(
        f"/api/v1/sessions/{sess_id}/lost-card",
        json={"plate_number": "أ ب ج 123", "notes": "lost"}
    )
    assert lost_resp.status_code == 200
    assert lost_resp.json()["data"]["status"] == "LOST_CARD"
    
    await db_session.refresh(card)
    assert card.status == CardStatus.LOST

    # 3. Receipt
    receipt_resp = await async_client.get(f"/api/v1/sessions/{sess_id}/receipt")
    assert receipt_resp.status_code == 200
    receipt_data = receipt_resp.json()["data"]
    assert receipt_data["is_lost_card"] is True
    assert receipt_data["penalty_amount"] == rule.lost_card_penalty

@pytest.mark.asyncio
async def test_race_condition_double_exit(async_client, db_session, auth_service):
    op = await setup_user(db_session, auth_service, async_client)
    rule = await setup_pricing_rule(db_session)
    shift = await open_operator_shift(db_session, op.id)
    
    card = ParkingCard(card_code="CARD-RACE-EXIT", status=CardStatus.IN_USE)
    db_session.add(card)
    await db_session.commit()
    
    session = ParkingSession(
        card_id=card.id,
        card_code="CARD-RACE-EXIT",
        status=SessionStatus.ACTIVE,
        entry_time=datetime.utcnow() - timedelta(hours=2),
        gate_number=1,
        operator_id=op.id,
        shift_id=shift.id,
    )
    db_session.add(session)
    await db_session.commit()

    # Call concurrently
    resps = await asyncio.gather(
        async_client.patch(f"/api/v1/sessions/{session.id}/exit"),
        async_client.patch(f"/api/v1/sessions/{session.id}/exit"),
        return_exceptions=True
    )
    
    status_codes = [r.status_code for r in resps if not isinstance(r, Exception) and hasattr(r, "status_code")]
    assert 200 in status_codes
    assert 409 in status_codes

    # Verify database state: exactly one completed session
    stmt = select(ParkingSession).where(ParkingSession.id == session.id)
    res = await db_session.execute(stmt)
    sess_obj = res.scalar()
    assert sess_obj.status == SessionStatus.COMPLETED

@pytest.mark.asyncio
async def test_race_condition_double_entry_same_card(async_client, db_session, auth_service):
    op = await setup_user(db_session, auth_service, async_client)
    rule = await setup_pricing_rule(db_session)
    await open_operator_shift(db_session, op.id)
    
    card = ParkingCard(card_code="CARD-RACE-ENTRY", status=CardStatus.AVAILABLE)
    db_session.add(card)
    await db_session.commit()

    # Call concurrently
    resps = await asyncio.gather(
        async_client.post("/api/v1/sessions/", json={"card_code": "CARD-RACE-ENTRY"}),
        async_client.post("/api/v1/sessions/", json={"card_code": "CARD-RACE-ENTRY"}),
        return_exceptions=True
    )
    
    status_codes = [r.status_code for r in resps if not isinstance(r, Exception) and hasattr(r, "status_code")]
    assert 201 in status_codes
    assert 409 in status_codes

    # Verify only one active session in DB
    stmt = select(ParkingSession).where(
        ParkingSession.card_code == "CARD-RACE-ENTRY",
        ParkingSession.status == SessionStatus.ACTIVE
    )
    res = await db_session.execute(stmt)
    sessions = res.scalars().all()
    assert len(sessions) == 1
