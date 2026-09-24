import pytest
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserRole
from models.parking_card import ParkingCard, CardStatus
from models.subscription import SubscriptionStatus
from models.subscription_plan import SubscriptionPlan
from models.subscriber import Subscriber
from repositories.subscription_plan_repo import SubscriptionPlanRepository
from repositories.subscriber_repo import SubscriberRepository
from repositories.subscription_repo import SubscriptionRepository


@pytest.mark.asyncio
async def test_plan_repo_crud(db_session: AsyncSession):
    # Setup creator user
    user = User(
        full_name="Admin User",
        username="admin1",
        hashed_password="hash",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    await db_session.flush()

    repo = SubscriptionPlanRepository(db_session)

    # 1. Create plan
    plan = await repo.create(
        label="Monthly Standard",
        duration_days=30,
        price_piastres=15000,
        max_entries_per_day=2,
        description="Standard 30-day plan",
        created_by=user.id,
    )
    assert plan.id is not None
    assert plan.label == "Monthly Standard"
    assert plan.is_active is True

    # 2. Get by ID & label
    fetched_by_id = await repo.get_by_id(plan.id)
    assert fetched_by_id is not None
    assert fetched_by_id.label == "Monthly Standard"

    fetched_by_label = await repo.get_by_label("Monthly Standard")
    assert fetched_by_label is not None
    assert fetched_by_label.id == plan.id

    # 3. Update fields
    await repo.update_fields(plan, price_piastres=18000, is_active=False)
    updated = await repo.get_by_id(plan.id)
    assert updated.price_piastres == 18000
    assert updated.is_active is False

    # 4. Get all (active vs all)
    all_plans = await repo.get_all(active_only=False)
    assert len(all_plans) == 1
    active_plans = await repo.get_all(active_only=True)
    assert len(active_plans) == 0


@pytest.mark.asyncio
async def test_subscriber_repo_crud_and_filtered(db_session: AsyncSession):
    repo = SubscriberRepository(db_session)

    # 1. Create subscriber
    sub = await repo.create(
        full_name="Ali Mohamed",
        plate_number="أ ب ج 123",
        phone_number="01012345678",
        notes="VIP client",
    )
    assert sub.id is not None
    assert sub.full_name == "Ali Mohamed"

    # 2. Get by ID & plate
    fetched_by_id = await repo.get_by_id(sub.id)
    assert fetched_by_id is not None
    assert fetched_by_id.plate_number == "أ ب ج 123"

    fetched_by_plate = await repo.get_by_plate("أ ب ج 123")
    assert fetched_by_plate is not None
    assert fetched_by_plate.id == sub.id

    # 3. Update fields
    await repo.update_fields(sub, full_name="Ali M. Hassan")
    updated = await repo.get_by_id(sub.id)
    assert updated.full_name == "Ali M. Hassan"

    # 4. Filtered search
    results, total = await repo.get_filtered(search="Ali", page=1, size=10)
    assert total == 1
    assert len(results) == 1
    assert results[0].id == sub.id

    # Non-matching search
    results_empty, total_empty = await repo.get_filtered(search="Unknown", page=1, size=10)
    assert total_empty == 0
    assert len(results_empty) == 0


@pytest.mark.asyncio
async def test_subscription_repo_full_lifecycle(db_session: AsyncSession):
    # Setup dependencies: User, Card, Plan, Subscriber
    user = User(
        full_name="Admin", username="admin_sub", hashed_password="pw", role=UserRole.ADMIN
    )
    db_session.add(user)
    await db_session.flush()

    card = ParkingCard(card_code="CARD-100", status=CardStatus.IN_USE)
    db_session.add(card)
    await db_session.flush()

    plan_repo = SubscriptionPlanRepository(db_session)
    plan = await plan_repo.create(
        label="Monthly VIP",
        duration_days=30,
        price_piastres=20000,
        max_entries_per_day=None,
        description=None,
        created_by=user.id,
    )

    sub_repo = SubscriberRepository(db_session)
    subscriber = await sub_repo.create(
        full_name="Kareem Tarek",
        plate_number="س ص ع 999",
        phone_number=None,
        notes=None,
    )

    repo = SubscriptionRepository(db_session)

    today = date(2026, 9, 24)
    end = today + timedelta(days=30)
    now = datetime.utcnow()

    # 1. Create subscription
    sub = await repo.create(
        subscriber_id=subscriber.id,
        plan_id=plan.id,
        card_id=card.id,
        plate_number="س ص ع 999",
        start_date=today,
        end_date=end,
        status=SubscriptionStatus.ACTIVE,
        amount_paid_piastres=20000,
        plan_price_snapshot=20000,
        paid_at=now,
        collected_by=user.id,
    )
    assert sub.id is not None
    assert sub.status == SubscriptionStatus.ACTIVE

    # 2. Get active for card & subscriber
    active_card_sub = await repo.get_active_for_card(card.id, today)
    assert active_card_sub is not None
    assert active_card_sub.id == sub.id

    active_sub = await repo.get_active_for_subscriber(subscriber.id)
    assert active_sub is not None
    assert active_sub.id == sub.id

    # 3. Get expiring soon
    expiring = await repo.get_expiring_soon(end + timedelta(days=5))
    assert len(expiring) == 1
    assert expiring[0].id == sub.id

    # 4. Get all by subscriber
    all_subs = await repo.get_all_by_subscriber(subscriber.id)
    assert len(all_subs) == 1

    # 5. Get filtered
    filtered, count = await repo.get_filtered(status=SubscriptionStatus.ACTIVE, plan_id=plan.id)
    assert count == 1
    assert len(filtered) == 1

    # 6. Get revenue by plan
    revenue = await repo.get_revenue_by_plan(start_utc=now - timedelta(days=1), end_utc=now + timedelta(days=1))
    assert len(revenue) == 1
    assert revenue[0]["plan_id"] == plan.id
    assert revenue[0]["subscription_count"] == 1
    assert revenue[0]["total_piastres"] == 20000


@pytest.mark.asyncio
async def test_subscription_repo_bulk_expire_and_activate(db_session: AsyncSession):
    user = User(
        full_name="Admin", username="admin_bulk", hashed_password="pw", role=UserRole.ADMIN
    )
    card = ParkingCard(card_code="CARD-200", status=CardStatus.IN_USE)
    db_session.add_all([user, card])
    await db_session.flush()

    plan = SubscriptionPlan(
        label="Plan A", duration_days=30, price_piastres=10000, created_by=user.id
    )
    sub = Subscriber(full_name="Sub A", plate_number="ق ر ش 111")
    db_session.add_all([plan, sub])
    await db_session.flush()

    repo = SubscriptionRepository(db_session)
    yesterday = date(2026, 9, 23)
    past_start = yesterday - timedelta(days=30)

    # Create an overdue active subscription
    overdue_sub = await repo.create(
        subscriber_id=sub.id,
        plan_id=plan.id,
        card_id=card.id,
        plate_number="ق ر ش 111",
        start_date=past_start,
        end_date=yesterday,
        status=SubscriptionStatus.ACTIVE,
        amount_paid_piastres=10000,
        plan_price_snapshot=10000,
        paid_at=datetime.utcnow(),
        collected_by=user.id,
    )

    # Bulk expire overdue
    cairo_today = date(2026, 9, 24)
    expired_count = await repo.bulk_expire_overdue(cairo_today)
    assert expired_count == 1

    # Verify subscription is now EXPIRED
    refreshed_sub = await repo.get_by_id(overdue_sub.id)
    assert refreshed_sub.status == SubscriptionStatus.EXPIRED

    # Create pending subscription for today
    pending_sub = await repo.create(
        subscriber_id=sub.id,
        plan_id=plan.id,
        card_id=card.id,
        plate_number="ق ر ش 111",
        start_date=cairo_today,
        end_date=cairo_today + timedelta(days=30),
        status=SubscriptionStatus.PENDING,
        amount_paid_piastres=10000,
        plan_price_snapshot=10000,
        paid_at=datetime.utcnow(),
        collected_by=user.id,
    )

    # Bulk activate pending
    activated_count = await repo.bulk_activate_pending(cairo_today)
    assert activated_count == 1

    refreshed_pending = await repo.get_by_id(pending_sub.id)
    assert refreshed_pending.status == SubscriptionStatus.ACTIVE
