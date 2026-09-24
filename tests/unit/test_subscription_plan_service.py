import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import User, UserRole
from repositories.subscription_plan_repo import SubscriptionPlanRepository
from schemas.subscriptions import PlanCreate, PlanUpdate
from services.subscription_plan_service import SubscriptionPlanService
from services.exceptions import PlanLabelAlreadyExistsError, PlanNotFoundError


@pytest.mark.asyncio
async def test_create_plan_success(db_session: AsyncSession, audit_service):
    admin = User(
        username="admin_plan_svc",
        full_name="Admin Plan",
        role=UserRole.ADMIN,
        is_active=True,
        hashed_password="hash",
    )
    db_session.add(admin)
    await db_session.flush()

    repo = SubscriptionPlanRepository(db_session)
    service = SubscriptionPlanService(db_session, repo, audit_service)

    plan_in = PlanCreate(
        label="شهري",
        duration_days=30,
        price_egp=150.0,
    )
    plan = await service.create_plan(plan_in, admin_id=admin.id)
    assert plan.price_piastres == 15000
    assert plan.is_active is True
    assert plan.label == "شهري"


@pytest.mark.asyncio
async def test_create_plan_duplicate_label_raises(db_session: AsyncSession, audit_service):
    admin = User(
        username="admin_dup_plan",
        full_name="Admin Dup",
        role=UserRole.ADMIN,
        is_active=True,
        hashed_password="hash",
    )
    db_session.add(admin)
    await db_session.flush()

    repo = SubscriptionPlanRepository(db_session)
    service = SubscriptionPlanService(db_session, repo, audit_service)

    plan_in = PlanCreate(label="شهري مكرر", duration_days=30, price_egp=100.0)
    await service.create_plan(plan_in, admin_id=admin.id)

    with pytest.raises(PlanLabelAlreadyExistsError):
        await service.create_plan(plan_in, admin_id=admin.id)


@pytest.mark.asyncio
async def test_deactivate_plan_success(db_session: AsyncSession, audit_service):
    admin = User(
        username="admin_deact_plan",
        full_name="Admin Deact",
        role=UserRole.ADMIN,
        is_active=True,
        hashed_password="hash",
    )
    db_session.add(admin)
    await db_session.flush()

    repo = SubscriptionPlanRepository(db_session)
    service = SubscriptionPlanService(db_session, repo, audit_service)

    plan = await service.create_plan(
        PlanCreate(label="خطة للإلغاء", duration_days=15, price_egp=50.0),
        admin_id=admin.id,
    )
    updated = await service.deactivate_plan(plan.id, admin_id=admin.id)
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_update_plan_price(db_session: AsyncSession, audit_service):
    admin = User(
        username="admin_upd_plan",
        full_name="Admin Upd",
        role=UserRole.ADMIN,
        is_active=True,
        hashed_password="hash",
    )
    db_session.add(admin)
    await db_session.flush()

    repo = SubscriptionPlanRepository(db_session)
    service = SubscriptionPlanService(db_session, repo, audit_service)

    plan = await service.create_plan(
        PlanCreate(label="خطة السعر", duration_days=30, price_egp=100.0),
        admin_id=admin.id,
    )
    updated = await service.update_plan(
        plan.id,
        PlanUpdate(price_egp=200.0),
        admin_id=admin.id,
    )
    assert updated.price_piastres == 20000


def test_update_plan_duration_not_possible():
    # Asserts duration_days is not a field in PlanUpdate
    assert "duration_days" not in PlanUpdate.model_fields
