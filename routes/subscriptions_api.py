from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import require_admin, require_any_role
from models.user import User
from models.subscription import SubscriptionStatus
from repositories.subscription_plan_repo import SubscriptionPlanRepository
from repositories.subscriber_repo import SubscriberRepository
from repositories.subscription_repo import SubscriptionRepository
from repositories.card_repo import ParkingCardRepository
from services.subscription_plan_service import SubscriptionPlanService
from services.subscriber_service import SubscriberService
from services.subscription_service import SubscriptionService
from services.card_service import CardService
from services.audit_service import AuditService
from services.plate_service import PlateService
from services.report_service import ReportService
from schemas.common import PaginatedResponse
from schemas.subscriptions import (
    PlanCreate,
    PlanUpdate,
    PlanResponse,
    SubscriberCreate,
    SubscriberUpdate,
    SubscriberResponse,
    SubscriptionCreate,
    SubscriptionRenew,
    SubscriptionRenewRequest,
    SubscriptionCancel,
    SubscriptionCancelRequest,
    SubscriptionResponse,
    SubscriptionRevenueSummary,
    SubscriptionDashboardStats,
)
from services.exceptions import (
    PlanNotFoundError,
    PlanNotActiveError,
    PlanLabelAlreadyExistsError,
    SubscriberNotFoundError,
    SubscriberPlateAlreadyExistsError,
    SubscriptionNotFoundError,
    SubscriptionNotActiveError,
    SubscriberAlreadyHasActiveSubscriptionError,
    CardNotAvailableError,
    CardNotFoundError,
)

router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])


# ----------------------------------------------------
# 8a — Subscription Plans API
# ----------------------------------------------------

@router.post("/plans", status_code=status.HTTP_201_CREATED)
async def create_plan(
    data: PlanCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    plan_repo = SubscriptionPlanRepository(db)
    audit_service = AuditService(db)
    plan_service = SubscriptionPlanService(db, plan_repo, audit_service)

    try:
        plan = await plan_service.create_plan(data, current_user.id)
    except PlanLabelAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
            headers={"X-Error-Code": "PLAN_LABEL_ALREADY_EXISTS"},
        )

    return {"data": PlanResponse.model_validate(plan).model_dump(mode="json")}


@router.get("/plans")
async def get_plans(
    active_only: bool = False,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    plan_repo = SubscriptionPlanRepository(db)
    plans = await plan_repo.get_all(active_only=active_only)
    return {"data": [PlanResponse.model_validate(p).model_dump(mode="json") for p in plans]}


@router.get("/plans/active")
async def get_active_plans(
    current_user: User = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    plan_repo = SubscriptionPlanRepository(db)
    plans = await plan_repo.get_all(active_only=True)
    return {"data": [PlanResponse.model_validate(p).model_dump(mode="json") for p in plans]}


@router.patch("/plans/{plan_id}")
async def update_plan(
    plan_id: int,
    data: PlanUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    plan_repo = SubscriptionPlanRepository(db)
    audit_service = AuditService(db)
    plan_service = SubscriptionPlanService(db, plan_repo, audit_service)

    try:
        plan = await plan_service.update_plan(plan_id, data, current_user.id)
    except PlanNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
            headers={"X-Error-Code": "PLAN_NOT_FOUND"},
        )
    except PlanLabelAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
            headers={"X-Error-Code": "PLAN_LABEL_ALREADY_EXISTS"},
        )

    return {"data": PlanResponse.model_validate(plan).model_dump(mode="json")}


@router.patch("/plans/{plan_id}/deactivate")
async def deactivate_plan(
    plan_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    plan_repo = SubscriptionPlanRepository(db)
    audit_service = AuditService(db)
    plan_service = SubscriptionPlanService(db, plan_repo, audit_service)

    try:
        plan = await plan_service.deactivate_plan(plan_id, current_user.id)
    except PlanNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
            headers={"X-Error-Code": "PLAN_NOT_FOUND"},
        )

    return {"data": PlanResponse.model_validate(plan).model_dump(mode="json")}


# ----------------------------------------------------
# 8b — Subscribers API
# ----------------------------------------------------

@router.post("/subscribers", status_code=status.HTTP_201_CREATED)
async def create_subscriber(
    data: SubscriberCreate,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    subscriber_repo = SubscriberRepository(db)
    audit_service = AuditService(db)
    subscriber_service = SubscriberService(db, subscriber_repo, PlateService(), audit_service)

    try:
        subscriber = await subscriber_service.create_subscriber(data, current_user.id)
    except SubscriberPlateAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
            headers={"X-Error-Code": "SUBSCRIBER_PLATE_ALREADY_EXISTS"},
        )

    return {"data": SubscriberResponse.model_validate(subscriber).model_dump(mode="json")}


@router.get("/subscribers", response_model=PaginatedResponse[SubscriberResponse])
async def get_subscribers(
    search: str | None = None,
    status: str | None = None,
    plan_id: int | None = None,
    expiring_days: int | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    subscriber_repo = SubscriberRepository(db)
    audit_service = AuditService(db)
    subscriber_service = SubscriberService(db, subscriber_repo, PlateService(), audit_service)

    sub_repo = SubscriptionRepository(db)
    subscribers, total = await subscriber_service.get_filtered(
        search=search,
        status_filter=status,
        plan_id=plan_id,
        expiring_days=expiring_days,
        subscription_repo=sub_repo,
        page=page,
        size=size,
    )

    sub_repo = SubscriptionRepository(db)
    responses: list[SubscriberResponse] = []
    for subr in subscribers:
        active_sub = await sub_repo.get_active_for_subscriber(subr.id)
        active_sub_resp = SubscriptionResponse.model_validate(active_sub) if active_sub else None
        resp = SubscriberResponse.model_validate(subr)
        resp.active_subscription = active_sub_resp
        responses.append(resp)

    return PaginatedResponse[SubscriberResponse](
        data=responses,
        total=total,
        page=page,
        size=size,
    )


@router.get("/subscribers/{subscriber_id}")
async def get_subscriber_detail(
    subscriber_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    subscriber_repo = SubscriberRepository(db)
    sub_repo = SubscriptionRepository(db)

    subscriber = await subscriber_repo.get_by_id(subscriber_id)
    if not subscriber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscriber {subscriber_id} not found",
            headers={"X-Error-Code": "SUBSCRIBER_NOT_FOUND"},
        )

    active_sub = await sub_repo.get_active_for_subscriber(subscriber_id)
    active_sub_resp = SubscriptionResponse.model_validate(active_sub) if active_sub else None
    resp = SubscriberResponse.model_validate(subscriber)
    resp.active_subscription = active_sub_resp

    return {"data": resp.model_dump(mode="json")}


@router.patch("/subscribers/{subscriber_id}")
async def update_subscriber(
    subscriber_id: int,
    data: SubscriberUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    subscriber_repo = SubscriberRepository(db)
    audit_service = AuditService(db)
    subscriber_service = SubscriberService(db, subscriber_repo, PlateService(), audit_service)

    try:
        subscriber = await subscriber_service.update_subscriber(subscriber_id, data, current_user.id)
    except SubscriberNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
            headers={"X-Error-Code": "SUBSCRIBER_NOT_FOUND"},
        )

    return {"data": SubscriberResponse.model_validate(subscriber).model_dump(mode="json")}


# ----------------------------------------------------
# 8c — Subscriptions API
# ----------------------------------------------------

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_subscription(
    data: SubscriptionCreate,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    sub_repo = SubscriptionRepository(db)
    plan_repo = SubscriptionPlanRepository(db)
    card_service = CardService(db)
    audit_service = AuditService(db)
    sub_service = SubscriptionService(db, sub_repo, plan_repo, card_service, audit_service)

    try:
        sub = await sub_service.create_subscription(data, current_user.id)
    except PlanNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
            headers={"X-Error-Code": "PLAN_NOT_FOUND"},
        )
    except PlanNotActiveError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
            headers={"X-Error-Code": "PLAN_NOT_ACTIVE"},
        )
    except CardNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
            headers={"X-Error-Code": "CARD_NOT_FOUND"},
        )
    except CardNotAvailableError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
            headers={"X-Error-Code": "CARD_NOT_AVAILABLE"},
        )
    except SubscriberNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
            headers={"X-Error-Code": "SUBSCRIBER_NOT_FOUND"},
        )
    except SubscriberAlreadyHasActiveSubscriptionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
            headers={"X-Error-Code": "SUBSCRIBER_ALREADY_HAS_ACTIVE_SUBSCRIPTION"},
        )

    return {"data": SubscriptionResponse.model_validate(sub).model_dump(mode="json")}


@router.get("/", response_model=PaginatedResponse[SubscriptionResponse])
async def get_subscriptions(
    status_filter: SubscriptionStatus | None = Query(None, alias="status"),
    plan_id: int | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    sub_repo = SubscriptionRepository(db)
    subs, total = await sub_repo.get_filtered(
        status=status_filter,
        plan_id=plan_id,
        page=page,
        size=size,
    )
    responses = [SubscriptionResponse.model_validate(s) for s in subs]
    return PaginatedResponse[SubscriptionResponse](
        data=responses,
        total=total,
        page=page,
        size=size,
    )


@router.get("/{subscription_id}")
async def get_subscription_detail(
    subscription_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    sub_repo = SubscriptionRepository(db)
    sub = await sub_repo.get_by_id(subscription_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription {subscription_id} not found",
            headers={"X-Error-Code": "SUBSCRIPTION_NOT_FOUND"},
        )
    return {"data": SubscriptionResponse.model_validate(sub).model_dump(mode="json")}


@router.post("/{subscription_id}/renew", status_code=status.HTTP_201_CREATED)
async def renew_subscription(
    subscription_id: int,
    data: SubscriptionRenew,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    sub_repo = SubscriptionRepository(db)
    plan_repo = SubscriptionPlanRepository(db)
    card_service = CardService(db)
    audit_service = AuditService(db)
    sub_service = SubscriptionService(db, sub_repo, plan_repo, card_service, audit_service)

    try:
        new_sub = await sub_service.renew_subscription(subscription_id, data, current_user.id)
    except SubscriptionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
            headers={"X-Error-Code": "SUBSCRIPTION_NOT_FOUND"},
        )
    except SubscriptionNotActiveError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
            headers={"X-Error-Code": "SUBSCRIPTION_NOT_ACTIVE"},
        )

    return {"data": SubscriptionResponse.model_validate(new_sub).model_dump(mode="json")}


@router.patch("/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: int,
    data: SubscriptionCancel,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    sub_repo = SubscriptionRepository(db)
    plan_repo = SubscriptionPlanRepository(db)
    card_service = CardService(db)
    audit_service = AuditService(db)
    sub_service = SubscriptionService(db, sub_repo, plan_repo, card_service, audit_service)

    try:
        sub = await sub_service.cancel_subscription(
            subscription_id=subscription_id,
            cancel_reason=data.cancel_reason,
            admin_id=current_user.id,
        )
    except SubscriptionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
            headers={"X-Error-Code": "SUBSCRIPTION_NOT_FOUND"},
        )
    except SubscriptionNotActiveError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
            headers={"X-Error-Code": "SUBSCRIPTION_NOT_ACTIVE"},
        )

    return {"data": SubscriptionResponse.model_validate(sub).model_dump(mode="json")}
