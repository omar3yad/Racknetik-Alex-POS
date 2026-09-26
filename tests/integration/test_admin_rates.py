import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.user import User, UserRole
from models.pricing_rule import PricingRule
from services.auth_service import AuthService


async def setup_admin(
    db_session: AsyncSession, auth_service: AuthService, async_client: AsyncClient
) -> User:
    admin = User(
        username="admin_rates_tester",
        role=UserRole.ADMIN,
        hashed_password=auth_service.hash_password("adminpass"),
        full_name="Admin Rates Tester",
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)

    token = auth_service.create_access_token(admin.id, admin.role.value)
    async_client.cookies.set("pgms_token", token)
    async_client.headers["Authorization"] = f"Bearer {token}"
    return admin


@pytest.mark.asyncio
async def test_create_pricing_rule(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)

    payload = {
        "label": "Standard Hourly Rate",
        "rate_per_hour_egp": 10.0,
        "minimum_charge_egp": 10.0,
        "grace_period_mins": 15,
        "lost_card_penalty_egp": 50.0,
    }

    res = await async_client.post("/api/v1/rates/", json=payload)
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["label"] == "Standard Hourly Rate"
    assert data["rate_per_hour"] == 1000
    assert data["minimum_charge"] == 1000
    assert data["grace_period_mins"] == 15
    assert data["lost_card_penalty"] == 5000
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_create_duplicate_label_returns_409(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)

    payload = {
        "label": "Test Duplicate Label",
        "rate_per_hour_egp": 12.0,
        "grace_period_mins": 10,
    }

    res1 = await async_client.post("/api/v1/rates/", json=payload)
    assert res1.status_code == 201

    res2 = await async_client.post("/api/v1/rates/", json=payload)
    assert res2.status_code == 409
    body = res2.json()
    assert body["code"] == "RATE_LABEL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_activate_rule(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)

    # Create rule 1
    res1 = await async_client.post(
        "/api/v1/rates/",
        json={"label": "Rule 1", "rate_per_hour_egp": 10.0, "grace_period_mins": 10},
    )
    assert res1.status_code == 201

    # Create rule 2
    res2 = await async_client.post(
        "/api/v1/rates/",
        json={"label": "Rule 2", "rate_per_hour_egp": 20.0, "grace_period_mins": 10},
    )
    assert res2.status_code == 201
    rule2_id = res2.json()["data"]["id"]

    # Activate rule 2
    patch_res = await async_client.patch(f"/api/v1/rates/{rule2_id}/activate")
    assert patch_res.status_code == 200

    # Get active rule
    get_res = await async_client.get("/api/v1/rates/active")
    assert get_res.status_code == 200
    assert get_res.json()["data"]["id"] == rule2_id
    assert get_res.json()["data"]["label"] == "Rule 2"


@pytest.mark.asyncio
async def test_activate_already_active_is_idempotent(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)

    res = await async_client.post(
        "/api/v1/rates/",
        json={
            "label": "Idempotent Rate",
            "rate_per_hour_egp": 15.0,
            "grace_period_mins": 10,
        },
    )
    assert res.status_code == 201
    rule_id = res.json()["data"]["id"]

    # First activation
    act1 = await async_client.patch(f"/api/v1/rates/{rule_id}/activate")
    assert act1.status_code == 200

    # Second activation (idempotent)
    act2 = await async_client.patch(f"/api/v1/rates/{rule_id}/activate")
    assert act2.status_code == 200
    assert act2.json()["data"]["is_active"] is True

    # Active is still rule_id
    get_res = await async_client.get("/api/v1/rates/active")
    assert get_res.status_code == 200
    assert get_res.json()["data"]["id"] == rule_id


@pytest.mark.asyncio
async def test_fractional_egp_stored_as_piastres(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)

    payload = {
        "label": "Fractional Rate Test",
        "rate_per_hour_egp": 5.555,
        "grace_period_mins": 10,
    }

    res = await async_client.post("/api/v1/rates/", json=payload)
    assert res.status_code == 201
    rule_id = res.json()["data"]["id"]

    # Query DB directly to verify piastres conversion
    query = await db_session.execute(
        select(PricingRule).where(PricingRule.id == rule_id)
    )
    db_rule = query.scalars().first()
    assert db_rule is not None
    # 5.555 * 100 = 555.5 -> round = 556
    assert db_rule.rate_per_hour == 556


@pytest.mark.asyncio
async def test_create_tiered_pricing_rule(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)

    payload = {
        "label": "First 20 then 10",
        "rate_per_hour_egp": 10.0,
        "first_hour_charge_egp": 20.0,
        "subsequent_hour_charge_egp": 10.0,
        "grace_period_mins": 15,
        "minimum_charge_egp": 0.0,
        "lost_card_penalty_egp": 50.0,
    }

    res = await async_client.post("/api/v1/rates/", json=payload)
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["label"] == "First 20 then 10"
    assert data["first_hour_charge"] == 2000
    assert data["subsequent_hour_charge"] == 1000
    assert data["rate_per_hour"] == 1000

    # Activate the rule
    rule_id = data["id"]
    act = await async_client.patch(f"/api/v1/rates/{rule_id}/activate")
    assert act.status_code == 200

    active_res = await async_client.get("/api/v1/rates/active")
    assert active_res.status_code == 200
    active_data = active_res.json()["data"]
    assert active_data["id"] == rule_id
    assert active_data["first_hour_charge"] == 2000
    assert active_data["subsequent_hour_charge"] == 1000


@pytest.mark.asyncio
async def test_update_pricing_rule(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)

    # 1. Create rule
    payload = {
        "label": "Original Rate 20-15",
        "rate_per_hour_egp": 15.0,
        "first_hour_charge_egp": 20.0,
        "subsequent_hour_charge_egp": 15.0,
        "grace_period_mins": 10,
    }
    create_res = await async_client.post("/api/v1/rates/", json=payload)
    assert create_res.status_code == 201
    rule_id = create_res.json()["data"]["id"]

    # 2. Update rule directly: change subsequent hour from 15 to 10
    update_payload = {
        "label": "Updated Rate 20-10",
        "first_hour_charge_egp": 20.0,
        "subsequent_hour_charge_egp": 10.0,
        "rate_per_hour_egp": 10.0,
        "grace_period_mins": 15,
    }
    update_res = await async_client.patch(f"/api/v1/rates/{rule_id}", json=update_payload)
    assert update_res.status_code == 200
    updated_data = update_res.json()["data"]
    assert updated_data["label"] == "Updated Rate 20-10"
    assert updated_data["first_hour_charge"] == 2000
    assert updated_data["subsequent_hour_charge"] == 1000
    assert updated_data["grace_period_mins"] == 15


