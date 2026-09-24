import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.subscription import Subscription, SubscriptionStatus
from models.subscriber import Subscriber
from models.parking_card import ParkingCard, CardStatus
from repositories.subscription_plan_repo import SubscriptionPlanRepository
from repositories.subscription_repo import SubscriptionRepository
from schemas.subscriptions import (
    SubscriptionCreate,
    SubscriptionRenew,
    SubscriptionDashboardStats,
)
from services.audit_service import AuditService
from services.card_service import CardService
from services.exceptions import (
    PlanNotFoundError,
    PlanNotActiveError,
    CardNotFoundError,
    CardNotAvailableError,
    SubscriberNotFoundError,
    SubscriptionNotFoundError,
    SubscriptionNotActiveError,
    SubscriberAlreadyHasActiveSubscriptionError,
)
from utils.time import cairo_now, cairo_today_start


class SubscriptionService:
    def __init__(
        self,
        db: AsyncSession,
        subscription_repo: SubscriptionRepository,
        plan_repo: SubscriptionPlanRepository,
        card_service: CardService,
        audit_service: AuditService,
    ):
        self.db = db
        self.subscription_repo = subscription_repo
        self.plan_repo = plan_repo
        self.card_service = card_service
        self.audit_service = audit_service

    async def get_active_for_card(self, card_id: int) -> Subscription | None:
        """Silently fetches active subscription for a card without raising exceptions."""
        try:
            today = cairo_now().date()
            return await self.subscription_repo.get_active_for_card(card_id, today)
        except Exception:
            return None

    async def check_daily_limit(self, subscription: Subscription) -> bool:
        """Returns True if the vehicle has not yet exceeded max daily entries for its plan."""
        plan = await self.plan_repo.get_by_id(subscription.plan_id)
        if not plan or plan.max_entries_per_day is None:
            return True

        day_start_utc = cairo_today_start()
        day_end_utc = day_start_utc + timedelta(days=1)
        count = await self.subscription_repo.count_daily_entries(
            subscription.id, day_start_utc, day_end_utc
        )
        return count < plan.max_entries_per_day

    async def create_subscription(
        self, data: SubscriptionCreate, admin_id: int
    ) -> Subscription:
        """Creates and activates a new subscription, linking a card to a subscriber."""
        plan = await self.plan_repo.get_by_id(data.plan_id)
        if plan is None:
            raise PlanNotFoundError("Subscription plan not found")
        if not plan.is_active:
            raise PlanNotActiveError("Subscription plan is not active")

        # Fetch card directly by ID
        result = await self.db.execute(
            select(ParkingCard).where(ParkingCard.id == data.card_id).limit(1)
        )
        card = result.scalars().first()
        if card is None:
            raise CardNotFoundError("Card not found")
        if card.status != CardStatus.AVAILABLE:
            raise CardNotAvailableError("Card is not available for subscription")

        # Check subscriber existence
        sub_res = await self.db.execute(
            select(Subscriber).where(Subscriber.id == data.subscriber_id).limit(1)
        )
        subscriber = sub_res.scalars().first()
        if subscriber is None:
            raise SubscriberNotFoundError("Subscriber not found")

        # Check active subscription uniqueness
        existing_sub = await self.subscription_repo.get_active_for_subscriber(data.subscriber_id)
        if existing_sub is not None:
            raise SubscriberAlreadyHasActiveSubscriptionError(
                "Subscriber already has an active or pending subscription"
            )

        today = cairo_now().date()
        end_date = data.start_date + timedelta(days=plan.duration_days)
        status = SubscriptionStatus.ACTIVE if data.start_date <= today else SubscriptionStatus.PENDING

        subscription = await self.subscription_repo.create(
            subscriber_id=data.subscriber_id,
            plan_id=data.plan_id,
            card_id=data.card_id,
            plate_number=subscriber.plate_number,
            start_date=data.start_date,
            end_date=end_date,
            status=status,
            amount_paid_piastres=data.amount_paid_piastres,
            plan_price_snapshot=plan.price_piastres,
            paid_at=datetime.utcnow(),
            collected_by=admin_id,
            renewal_count=0,
            previous_subscription_id=None,
            notes=data.notes,
        )

        if status == SubscriptionStatus.ACTIVE and self.card_service:
            await self.card_service.set_status(card, CardStatus.IN_USE)

        await self.db.commit()
        await self.db.refresh(subscription)

        if self.audit_service:
            await self.audit_service.log(
                actor_id=admin_id,
                action="SUBSCRIPTION_CREATED",
                entity_type="subscription",
                entity_id=subscription.id,
                before=None,
                after={
                    "subscriber_id": subscription.subscriber_id,
                    "plan_id": subscription.plan_id,
                    "card_id": subscription.card_id,
                    "start_date": subscription.start_date.isoformat(),
                    "end_date": subscription.end_date.isoformat(),
                    "amount_paid_piastres": subscription.amount_paid_piastres,
                },
            )
        return subscription

    async def renew_subscription(
        self, subscription_id: int, data: SubscriptionRenew, admin_id: int
    ) -> Subscription:
        """Renews an existing subscription, creating a new continuation record."""
        old_sub = await self.subscription_repo.get_by_id(subscription_id)
        if old_sub is None:
            raise SubscriptionNotFoundError("Subscription not found")
        if old_sub.status != SubscriptionStatus.ACTIVE:
            raise SubscriptionNotActiveError("Only ACTIVE subscriptions can be renewed")

        plan_id = data.plan_id if data.plan_id is not None else old_sub.plan_id
        plan = await self.plan_repo.get_by_id(plan_id)
        if plan is None:
            raise PlanNotFoundError("Subscription plan not found")
        if not plan.is_active:
            raise PlanNotActiveError("Subscription plan is not active")

        today = cairo_now().date()
        if old_sub.end_date >= today:
            new_start = old_sub.end_date
        else:
            new_start = today

        new_end = new_start + timedelta(days=plan.duration_days)
        new_status = SubscriptionStatus.ACTIVE if new_start <= today else SubscriptionStatus.PENDING

        new_sub = await self.subscription_repo.create(
            subscriber_id=old_sub.subscriber_id,
            plan_id=plan.id,
            card_id=old_sub.card_id,
            plate_number=old_sub.plate_number,
            start_date=new_start,
            end_date=new_end,
            status=new_status,
            amount_paid_piastres=data.amount_paid_piastres,
            plan_price_snapshot=plan.price_piastres,
            paid_at=datetime.utcnow(),
            collected_by=admin_id,
            renewal_count=old_sub.renewal_count + 1,
            previous_subscription_id=old_sub.id,
            notes=data.notes,
        )

        if new_status == SubscriptionStatus.ACTIVE:
            await self.subscription_repo.update_fields(
                old_sub,
                status=SubscriptionStatus.EXPIRED,
                ended_at=datetime.utcnow(),
            )

        await self.db.commit()
        await self.db.refresh(new_sub)

        if self.audit_service:
            await self.audit_service.log(
                actor_id=admin_id,
                action="SUBSCRIPTION_RENEWED",
                entity_type="subscription",
                entity_id=new_sub.id,
                before={"old_id": old_sub.id},
                after={"old_id": old_sub.id, "new_id": new_sub.id},
            )
        return new_sub

    async def cancel_subscription(
        self,
        subscription_id: int,
        cancel_reason: str | None,
        admin_id: int,
    ) -> Subscription:
        """Cancels an active or pending subscription and frees the card."""
        subscription = await self.subscription_repo.get_by_id(subscription_id)
        if subscription is None:
            raise SubscriptionNotFoundError("Subscription not found")
        if subscription.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING):
            raise SubscriptionNotActiveError("Subscription is not active or pending")

        result = await self.db.execute(
            select(ParkingCard).where(ParkingCard.id == subscription.card_id).limit(1)
        )
        card = result.scalars().first()

        now = datetime.utcnow()
        await self.subscription_repo.update_fields(
            subscription,
            status=SubscriptionStatus.CANCELLED,
            ended_at=now,
            cancel_reason=cancel_reason,
        )

        if card and self.card_service:
            await self.card_service.set_status(card, CardStatus.AVAILABLE)

        await self.db.commit()
        await self.db.refresh(subscription)

        if self.audit_service:
            await self.audit_service.log(
                actor_id=admin_id,
                action="SUBSCRIPTION_CANCELLED",
                entity_type="subscription",
                entity_id=subscription.id,
                before={"status": "ACTIVE"},
                after={"status": "CANCELLED", "cancel_reason": cancel_reason},
            )
        return subscription

    async def expire_overdue_subscriptions(self) -> int:
        """Marks active subscriptions past their end date as EXPIRED and frees cards."""
        today = cairo_now().date()
        count = await self.subscription_repo.bulk_expire_overdue(today)
        await self.db.commit()
        return count

    async def activate_pending_subscriptions(self) -> int:
        """Activates pending subscriptions whose start date has arrived."""
        today = cairo_now().date()
        count = await self.subscription_repo.bulk_activate_pending(today)
        await self.db.commit()
        return count

    async def get_dashboard_stats(self) -> SubscriptionDashboardStats:
        """Returns concurrent dashboard counts for active, expiring, and unrenewed subscriptions."""
        today = cairo_now().date()
        threshold = today + timedelta(days=7)

        async def get_active_count():
            try:
                res = await self.db.execute(
                    select(func.count()).select_from(Subscription).where(
                        Subscription.status == SubscriptionStatus.ACTIVE
                    )
                )
                return res.scalar_one()
            except Exception:
                return 0

        async def get_expiring_count():
            try:
                subs = await self.subscription_repo.get_expiring_soon(threshold)
                return len(subs)
            except Exception:
                return 0

        async def get_expired_unrenewed_count():
            try:
                # Expired subscriptions that have not been renewed
                subquery = select(Subscription.previous_subscription_id).where(
                    Subscription.previous_subscription_id.is_not(None)
                )
                res = await self.db.execute(
                    select(func.count()).select_from(Subscription).where(
                        Subscription.status == SubscriptionStatus.EXPIRED,
                        Subscription.id.not_in(subquery),
                    )
                )
                return res.scalar_one()
            except Exception:
                return 0

        active_cnt, expiring_cnt, unrenewed_cnt = await asyncio.gather(
            get_active_count(),
            get_expiring_count(),
            get_expired_unrenewed_count(),
        )

        return SubscriptionDashboardStats(
            active_subscriptions_count=active_cnt,
            expiring_soon_count=expiring_cnt,
            expired_unrenewed_count=unrenewed_cnt,
        )


__all__ = ["SubscriptionService"]
