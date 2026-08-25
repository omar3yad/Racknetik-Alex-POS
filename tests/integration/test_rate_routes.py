import pytest
from datetime import datetime, timedelta
from models.user import User, UserRole
from models.pricing_rule import PricingRule

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
async def test_get_active_rule(async_client, db_session, auth_service):
    await setup_operator(db_session, auth_service, async_client)
    await setup_pricing_rule(db_session)
    
    response = await async_client.get("/api/v1/rates/active")
    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is True
    assert response.json()["data"]["label"] == "Standard Rule"

@pytest.mark.asyncio
async def test_get_active_rule_none(async_client, db_session, auth_service):
    await setup_operator(db_session, auth_service, async_client)
    # No pricing rules seeded
    
    response = await async_client.get("/api/v1/rates/active")
    assert response.status_code == 503
    assert response.json()["code"] == "NO_ACTIVE_PRICING_RULE"

@pytest.mark.asyncio
async def test_preview_price(async_client, db_session, auth_service):
    await setup_operator(db_session, auth_service, async_client)
    await setup_pricing_rule(db_session)
    
    entry_time = (datetime.utcnow() - timedelta(minutes=80)).isoformat()
    response = await async_client.get(f"/api/v1/rates/preview?entry_time={entry_time}")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["duration_minutes"] >= 60
    assert json_data["data"]["billable_hours"] == 2
    assert json_data["data"]["total_amount"] == 2000 # 2 hours * 10 EGP
