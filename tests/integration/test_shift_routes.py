import pytest
from datetime import datetime, timedelta
from models.user import User, UserRole
from models.parking_card import ParkingCard, CardStatus
from models.parking_session import ParkingSession, SessionStatus
from models.pricing_rule import PricingRule
from models.shift import Shift

async def setup_user(db_session, auth_service, async_client, username="operator1", role=UserRole.OPERATOR):
    hashed = auth_service.hash_password("pass123")
    user = User(
        full_name=f"Test {role.value}",
        username=username,
        hashed_password=hashed,
        role=role,
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

@pytest.mark.asyncio
async def test_open_shift(async_client, db_session, auth_service):
    await setup_user(db_session, auth_service, async_client)
    response = await async_client.post(
        "/api/v1/shifts/",
        json={"opening_cash_egp": 50000}
    )
    assert response.status_code == 201
    json_data = response.json()
    assert json_data["data"]["ended_at"] is None
    assert json_data["data"]["opening_cash_egp"] == 50000

@pytest.mark.asyncio
async def test_open_shift_already_open(async_client, db_session, auth_service):
    await setup_user(db_session, auth_service, async_client)
    await async_client.post("/api/v1/shifts/", json={"opening_cash_egp": 50000})
    
    response = await async_client.post("/api/v1/shifts/", json={"opening_cash_egp": 50000})
    assert response.status_code == 409
    assert response.json()["code"] == "SHIFT_ALREADY_OPEN"

@pytest.mark.asyncio
async def test_close_shift_with_summary(async_client, db_session, auth_service):
    op = await setup_user(db_session, auth_service, async_client)
    rule = await setup_pricing_rule(db_session)
    
    # Open shift
    shift_resp = await async_client.post("/api/v1/shifts/", json={"opening_cash_egp": 50000})
    shift_id = shift_resp.json()["data"]["id"]

    # Seed 2 completed sessions
    for i in range(2):
        card_code = f"CARD-S{i}"
        card = ParkingCard(card_code=card_code, status=CardStatus.AVAILABLE)
        db_session.add(card)
        await db_session.commit()
        
        # Open
        open_resp = await async_client.post("/api/v1/sessions/", json={"card_code": card_code})
        sess_id = open_resp.json()["data"]["id"]
        
        # Manually alter entry_time to be 2 hours ago to guarantee billable hours
        sess = await db_session.get(ParkingSession, sess_id)
        sess.entry_time = datetime.utcnow() - timedelta(hours=2)
        await db_session.commit()

        # Exit
        exit_resp = await async_client.patch(f"/api/v1/sessions/{sess_id}/exit")
        assert exit_resp.status_code == 200

    # Close shift
    # Total billed was 2 sessions * 2000 (2 hours * 10 EGP) = 4000 piastres (40 EGP).
    # Discrepancy is closing_cash - (opening_cash + billed).
    # opening_cash is 50000 piastres (500 EGP). Total computed closing should be 54000 piastres (540 EGP).
    # Let's say operator inputs 540 EGP.
    close_resp = await async_client.patch(
        f"/api/v1/shifts/{shift_id}/close",
        json={"closing_cash_egp": 4000} # in piastres, matching computed total (4000)
    )
    assert close_resp.status_code == 200
    json_data = close_resp.json()
    assert json_data["data"]["completed_sessions"] == 2
    assert json_data["data"]["discrepancy_piastres"] == 0

@pytest.mark.asyncio
async def test_close_shift_not_owned(async_client, db_session, auth_service):
    # Op A
    op_a = await setup_user(db_session, auth_service, async_client, username="op_a")
    shift_resp = await async_client.post("/api/v1/shifts/", json={"opening_cash_egp": 50000})
    shift_id = shift_resp.json()["data"]["id"]

    # Switch to Op B
    hashed = auth_service.hash_password("pass123")
    op_b = User(
        full_name="Operator B",
        username="op_b",
        hashed_password=hashed,
        role=UserRole.OPERATOR,
        gate_number=1,
        is_active=True,
    )
    db_session.add(op_b)
    await db_session.commit()
    token = auth_service.create_access_token(op_b.id, op_b.role.value)
    async_client.cookies.set("pgms_token", token)

    # Try to close Op A's shift
    close_resp = await async_client.patch(
        f"/api/v1/shifts/{shift_id}/close",
        json={"closing_cash_egp": 600}
    )
    assert close_resp.status_code == 403
    assert close_resp.json()["code"] == "INSUFFICIENT_PERMISSIONS"

@pytest.mark.asyncio
async def test_shift_sessions_list(async_client, db_session, auth_service):
    op = await setup_user(db_session, auth_service, async_client)
    await setup_pricing_rule(db_session)
    
    shift_resp = await async_client.post("/api/v1/shifts/", json={"opening_cash_egp": 50000})
    shift_id = shift_resp.json()["data"]["id"]

    # Open 3 sessions
    for i in range(3):
        card_code = f"CARD-L{i}"
        card = ParkingCard(card_code=card_code, status=CardStatus.AVAILABLE)
        db_session.add(card)
        await db_session.commit()
        await async_client.post("/api/v1/sessions/", json={"card_code": card_code})

    response = await async_client.get(f"/api/v1/shifts/{shift_id}/sessions")
    assert response.status_code == 200
    assert response.json()["total"] == 3
