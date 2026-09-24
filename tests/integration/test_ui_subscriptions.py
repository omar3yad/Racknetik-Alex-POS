import pytest
from datetime import datetime, date, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserRole
from models.parking_card import ParkingCard, CardStatus
from models.parking_session import ParkingSession, SessionStatus
from models.subscription_plan import SubscriptionPlan
from models.subscriber import Subscriber
from models.subscription import Subscription, SubscriptionStatus
from services.auth_service import AuthService


async def setup_admin(db: AsyncSession, auth_service: AuthService, client: AsyncClient) -> User:
    admin = User(
        username="test_admin_ui",
        full_name="Admin UI Test",
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
async def test_admin_dashboard_with_sub_stats(async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService):
    admin = await setup_admin(db_session, auth_service, async_client)

    plan = SubscriptionPlan(
        label="Monthly VIP",
        duration_days=30,
        price_piastres=60000,
        is_active=True,
        created_by=admin.id,
    )
    db_session.add(plan)
    await db_session.flush()

    sub = Subscriber(
        full_name="Dashboard Test User",
        plate_number="س ص ع ١ ٢ ٣ ٤",
        phone_number="01011111111",
    )
    db_session.add(sub)
    await db_session.flush()

    card = ParkingCard(card_code="CARD-DASH-1", status=CardStatus.IN_USE)
    db_session.add(card)
    await db_session.flush()

    # Expiring subscription within 3 days
    subscription = Subscription(
        subscriber_id=sub.id,
        plan_id=plan.id,
        card_id=card.id,
        plate_number=sub.plate_number,
        status=SubscriptionStatus.ACTIVE,
        start_date=date.today() - timedelta(days=27),
        end_date=date.today() + timedelta(days=3),
        amount_paid_piastres=60000,
        plan_price_snapshot=60000,
    )
    db_session.add(subscription)
    await db_session.commit()

    response = await async_client.get("/ui/admin/dashboard")
    assert response.status_code == 200
    assert "لوحة التحكم الرئيسية" in response.text
    assert "اشتراكات تنتهي قريباً" in response.text


@pytest.mark.asyncio
async def test_admin_plans_page(async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService):
    admin = await setup_admin(db_session, auth_service, async_client)

    plan = SubscriptionPlan(
        label="Standard Annual",
        duration_days=365,
        price_piastres=500000,
        is_active=True,
        created_by=admin.id,
    )
    db_session.add(plan)
    await db_session.commit()

    response = await async_client.get("/ui/admin/plans")
    assert response.status_code == 200
    assert "Standard Annual" in response.text
    assert "إنشاء خطة جديدة" in response.text


@pytest.mark.asyncio
async def test_admin_subscribers_list_and_filter(async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService):
    admin = await setup_admin(db_session, auth_service, async_client)

    sub = Subscriber(
        full_name="Mahmoud Hassan",
        plate_number="ق ر ش ٩ ٨ ٧",
        phone_number="01234567890",
    )
    db_session.add(sub)
    await db_session.commit()

    response = await async_client.get("/ui/admin/subscribers")
    assert response.status_code == 200
    assert "Mahmoud Hassan" in response.text
    assert "ق ر ش ٩ ٨ ٧" in response.text


@pytest.mark.asyncio
async def test_admin_subscriber_new_page(async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService):
    await setup_admin(db_session, auth_service, async_client)

    response = await async_client.get("/ui/admin/subscribers/new")
    assert response.status_code == 200
    assert "إضافة مشترك" in response.text
    assert "رقم اللوحة" in response.text


@pytest.mark.asyncio
async def test_admin_subscriber_detail_page(async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService):
    admin = await setup_admin(db_session, auth_service, async_client)

    plan = SubscriptionPlan(
        label="Quarterly Business",
        duration_days=90,
        price_piastres=150000,
        is_active=True,
        created_by=admin.id,
    )
    db_session.add(plan)
    await db_session.flush()

    sub = Subscriber(
        full_name="Sara Ibrahim",
        plate_number="أ ب ج ١ ١ ١",
        phone_number="01122334455",
    )
    db_session.add(sub)
    await db_session.flush()

    card = ParkingCard(card_code="CARD-SARA-1", status=CardStatus.IN_USE)
    db_session.add(card)
    await db_session.flush()

    subscription = Subscription(
        subscriber_id=sub.id,
        plan_id=plan.id,
        card_id=card.id,
        plate_number=sub.plate_number,
        status=SubscriptionStatus.ACTIVE,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=90),
        amount_paid_piastres=150000,
        plan_price_snapshot=150000,
    )
    db_session.add(subscription)
    await db_session.commit()

    response = await async_client.get(f"/ui/admin/subscribers/{sub.id}")
    assert response.status_code == 200
    assert "Sara Ibrahim" in response.text
    assert "Quarterly Business" in response.text
    assert "CARD-SARA-1" in response.text


@pytest.mark.asyncio
async def test_admin_subscriber_subscribe_page(async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService):
    admin = await setup_admin(db_session, auth_service, async_client)

    sub = Subscriber(
        full_name="Tarek Zaki",
        plate_number="ط ر ق ٥ ٥ ٥",
    )
    card = ParkingCard(card_code="CARD-AVAIL-1", status=CardStatus.AVAILABLE)
    plan = SubscriptionPlan(
        label="Monthly Basic",
        duration_days=30,
        price_piastres=30000,
        is_active=True,
        created_by=admin.id,
    )
    db_session.add_all([sub, card, plan])
    await db_session.commit()

    response = await async_client.get(f"/ui/admin/subscribers/{sub.id}/subscribe")
    assert response.status_code == 200
    assert "إنشاء اشتراك جديد" in response.text
    assert "CARD-AVAIL-1" in response.text
    assert "Monthly Basic" in response.text


@pytest.mark.asyncio
async def test_admin_subscriber_renew_page(async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService):
    admin = await setup_admin(db_session, auth_service, async_client)

    plan = SubscriptionPlan(
        label="Monthly Standard",
        duration_days=30,
        price_piastres=40000,
        is_active=True,
        created_by=admin.id,
    )
    db_session.add(plan)
    await db_session.flush()

    sub = Subscriber(
        full_name="Kareem Adel",
        plate_number="ك ر م ٧ ٧ ٧",
    )
    db_session.add(sub)
    await db_session.flush()

    card = ParkingCard(card_code="CARD-KRM-1", status=CardStatus.IN_USE)
    db_session.add(card)
    await db_session.flush()

    subscription = Subscription(
        subscriber_id=sub.id,
        plan_id=plan.id,
        card_id=card.id,
        plate_number=sub.plate_number,
        status=SubscriptionStatus.ACTIVE,
        start_date=date.today() - timedelta(days=28),
        end_date=date.today() + timedelta(days=2),
        amount_paid_piastres=40000,
        plan_price_snapshot=40000,
    )
    db_session.add(subscription)
    await db_session.commit()

    response = await async_client.get(f"/ui/admin/subscribers/{sub.id}/renew")
    assert response.status_code == 200
    assert "تجديد الاشتراك" in response.text
    assert "Kareem Adel" in response.text


@pytest.mark.asyncio
async def test_admin_subscriptions_log_page(async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService):
    admin = await setup_admin(db_session, auth_service, async_client)

    plan = SubscriptionPlan(
        label="Log Plan",
        duration_days=30,
        price_piastres=45000,
        is_active=True,
        created_by=admin.id,
    )
    db_session.add(plan)
    await db_session.flush()

    sub = Subscriber(
        full_name="Log Subscriber",
        plate_number="ل و ج ١ ٢ ٣",
    )
    db_session.add(sub)
    await db_session.flush()

    card = ParkingCard(card_code="CARD-LOG-1", status=CardStatus.IN_USE)
    db_session.add(card)
    await db_session.flush()

    subscription = Subscription(
        subscriber_id=sub.id,
        plan_id=plan.id,
        card_id=card.id,
        plate_number=sub.plate_number,
        status=SubscriptionStatus.ACTIVE,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=30),
        amount_paid_piastres=45000,
        plan_price_snapshot=45000,
    )
    db_session.add(subscription)
    await db_session.commit()

    response = await async_client.get("/ui/admin/subscriptions")
    assert response.status_code == 200
    assert "Log Subscriber" in response.text
    assert "Log Plan" in response.text
