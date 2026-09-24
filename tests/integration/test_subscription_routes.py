import pytest
from datetime import date
from models import User, UserRole, ParkingCard, CardStatus, SubscriptionPlan, Subscriber, SubscriptionStatus

async def setup_admin(db_session, auth_service, async_client):
    hashed = auth_service.hash_password("adminpass")
    user = User(
        full_name="Admin User",
        username="admin1",
        hashed_password=hashed,
        role=UserRole.ADMIN,
        gate_number=None,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    token = auth_service.create_access_token(user.id, user.role.value)
    async_client.cookies.set("pgms_token", token)
    return user


async def setup_operator(db_session, auth_service, async_client):
    hashed = auth_service.hash_password("op_pass")
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


@pytest.mark.asyncio
async def test_subscription_plans_api(async_client, db_session, auth_service):
    await setup_admin(db_session, auth_service, async_client)

    # 1. Create plan
    res = await async_client.post(
        "/api/v1/subscriptions/plans",
        json={
            "label": "Monthly VIP",
            "duration_days": 30,
            "price_egp": 500.0,
            "max_entries_per_day": 2,
            "description": "VIP monthly plan",
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["label"] == "Monthly VIP"
    assert data["price_piastres"] == 50000
    plan_id = data["id"]

    # 2. Duplicate label -> 409
    res_dup = await async_client.post(
        "/api/v1/subscriptions/plans",
        json={
            "label": "Monthly VIP",
            "duration_days": 30,
            "price_egp": 600.0,
        },
    )
    assert res_dup.status_code == 409
    assert res_dup.json()["code"] == "PLAN_LABEL_ALREADY_EXISTS"

    # 3. List plans
    res_list = await async_client.get("/api/v1/subscriptions/plans")
    assert res_list.status_code == 200
    assert len(res_list.json()["data"]) == 1

    # 4. Patch plan
    res_patch = await async_client.patch(
        f"/api/v1/subscriptions/plans/{plan_id}",
        json={"label": "Monthly VIP Updated", "price_egp": 550.0},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["data"]["label"] == "Monthly VIP Updated"
    assert res_patch.json()["data"]["price_piastres"] == 55000

    # 5. Deactivate plan
    res_deact = await async_client.patch(f"/api/v1/subscriptions/plans/{plan_id}/deactivate")
    assert res_deact.status_code == 200
    assert res_deact.json()["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_subscribers_api(async_client, db_session, auth_service):
    await setup_admin(db_session, auth_service, async_client)

    # 1. Create subscriber
    res = await async_client.post(
        "/api/v1/subscriptions/subscribers",
        json={
            "full_name": "Ahmed Ali",
            "plate_number": "س ب ج 1234",
            "phone_number": "01012345678",
            "notes": "Test subscriber",
        },
    )
    assert res.status_code == 201, res.text
    subr_data = res.json()["data"]
    assert subr_data["full_name"] == "Ahmed Ali"
    subr_id = subr_data["id"]

    # 2. Duplicate plate -> 409
    res_dup = await async_client.post(
        "/api/v1/subscriptions/subscribers",
        json={
            "full_name": "Another Person",
            "plate_number": "س ب ج 1234",
        },
    )
    assert res_dup.status_code == 409
    assert res_dup.json()["code"] == "SUBSCRIBER_PLATE_ALREADY_EXISTS"

    # 3. Get subscribers list
    res_list = await async_client.get("/api/v1/subscriptions/subscribers?search=Ahmed")
    assert res_list.status_code == 200
    assert res_list.json()["total"] == 1

    # 4. Get subscriber detail
    res_detail = await async_client.get(f"/api/v1/subscriptions/subscribers/{subr_id}")
    assert res_detail.status_code == 200
    assert res_detail.json()["data"]["plate_number"] == "س ب ج 1234"

    # 5. Patch subscriber
    res_patch = await async_client.patch(
        f"/api/v1/subscriptions/subscribers/{subr_id}",
        json={"phone_number": "01299999999", "notes": "Updated notes"},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["data"]["phone_number"] == "01299999999"


@pytest.mark.asyncio
async def test_subscriptions_lifecycle_and_reporting_api(async_client, db_session, auth_service):
    admin = await setup_admin(db_session, auth_service, async_client)

    card = ParkingCard(card_code="PKG-1001", status=CardStatus.AVAILABLE)
    plan = SubscriptionPlan(
        label="Quarterly",
        duration_days=90,
        price_piastres=120000,
        is_active=True,
        created_by=admin.id,
    )
    subr = Subscriber(
        full_name="Hassan Omar",
        plate_number="ق و ر 7777",
        phone_number="01122334455",
    )
    db_session.add_all([card, plan, subr])
    await db_session.commit()

    # 1. Create subscription
    today_str = date.today().isoformat()
    res = await async_client.post(
        "/api/v1/subscriptions/",
        json={
            "subscriber_id": subr.id,
            "plan_id": plan.id,
            "card_id": card.id,
            "start_date": today_str,
            "amount_paid_egp": 1200.0,
            "notes": "Initial purchase",
        },
    )
    assert res.status_code == 201, res.text
    sub_data = res.json()["data"]
    sub_id = sub_data["id"]
    assert sub_data["status"] == "ACTIVE"
    assert sub_data["amount_paid_piastres"] == 120000

    # 2. Get subscriptions list
    res_list = await async_client.get("/api/v1/subscriptions/?status=ACTIVE")
    assert res_list.status_code == 200
    assert res_list.json()["total"] == 1

    # 3. Get subscription detail
    res_det = await async_client.get(f"/api/v1/subscriptions/{sub_id}")
    assert res_det.status_code == 200
    assert res_det.json()["data"]["id"] == sub_id

    # 4. Renew subscription
    res_renew = await async_client.post(
        f"/api/v1/subscriptions/{sub_id}/renew",
        json={
            "amount_paid_egp": 1200.0,
            "notes": "Renewed for next quarter",
        },
    )
    assert res_renew.status_code == 201, res_renew.text
    renewed_data = res_renew.json()["data"]
    assert renewed_data["renewal_count"] == 1
    new_sub_id = renewed_data["id"]

    # 5. Cancel renewed subscription
    res_cancel = await async_client.patch(
        f"/api/v1/subscriptions/{new_sub_id}/cancel",
        json={"cancel_reason": "Customer requested cancellation"},
    )
    assert res_cancel.status_code == 200, res_cancel.text
    assert res_cancel.json()["data"]["status"] == "CANCELLED"

    # 6. Reporting API
    res_rpt = await async_client.get("/api/v1/admin/reports/subscriptions")
    assert res_rpt.status_code == 200, res_rpt.text
    rpt_data = res_rpt.json()["data"]
    assert rpt_data["total_subscriptions"] >= 1
    assert rpt_data["total_revenue_piastres"] > 0

    # 7. Stats API
    res_stats = await async_client.get("/api/v1/admin/stats/subscriptions")
    assert res_stats.status_code == 200, res_stats.text
    stats_data = res_stats.json()["data"]
    assert "active_subscriptions_count" in stats_data
    assert "expiring_soon_count" in stats_data
    assert "expired_unrenewed_count" in stats_data
