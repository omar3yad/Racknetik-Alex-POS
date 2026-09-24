from datetime import date, datetime
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.subscription import Subscription, SubscriptionStatus
from models.subscription_plan import SubscriptionPlan
from models.parking_card import ParkingCard, CardStatus
from models.parking_session import ParkingSession


class SubscriptionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, subscription_id: int) -> Subscription | None:
        """Fetches a subscription by ID."""
        result = await self.db.execute(
            select(Subscription).where(Subscription.id == subscription_id).limit(1)
        )
        return result.scalars().first()

    async def get_active_for_card(
        self, card_id: int, today: date
    ) -> Subscription | None:
        """Hot path: Checks if a card is linked to an active subscription covering today."""
        result = await self.db.execute(
            select(Subscription).where(
                Subscription.card_id == card_id,
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING]),
                Subscription.start_date <= today,
                Subscription.end_date >= today,
            ).limit(1)
        )
        return result.scalars().first()

    async def get_active_for_subscriber(
        self, subscriber_id: int
    ) -> Subscription | None:
        """Gets the current active or pending subscription for a subscriber."""
        result = await self.db.execute(
            select(Subscription).where(
                Subscription.subscriber_id == subscriber_id,
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING]),
            ).order_by(Subscription.end_date.desc()).limit(1)
        )
        return result.scalars().first()

    async def create(
        self,
        subscriber_id: int,
        plan_id: int,
        card_id: int,
        plate_number: str,
        start_date: date,
        end_date: date,
        status: SubscriptionStatus,
        amount_paid_piastres: int,
        plan_price_snapshot: int,
        paid_at: datetime | None,
        collected_by: int | None,
        renewal_count: int = 0,
        previous_subscription_id: int | None = None,
        notes: str | None = None,
        cancel_reason: str | None = None,
        ended_at: datetime | None = None,
    ) -> Subscription:
        """Creates a new subscription record and flushes."""
        subscription = Subscription(
            subscriber_id=subscriber_id,
            plan_id=plan_id,
            card_id=card_id,
            plate_number=plate_number,
            start_date=start_date,
            end_date=end_date,
            status=status,
            amount_paid_piastres=amount_paid_piastres,
            plan_price_snapshot=plan_price_snapshot,
            paid_at=paid_at,
            collected_by=collected_by,
            renewal_count=renewal_count,
            previous_subscription_id=previous_subscription_id,
            cancel_reason=cancel_reason,
            ended_at=ended_at,
            notes=notes,
        )
        self.db.add(subscription)
        await self.db.flush()
        return subscription

    async def update_fields(
        self, subscription: Subscription, **fields
    ) -> Subscription:
        """Updates fields on a subscription and flushes."""
        for key, value in fields.items():
            setattr(subscription, key, value)
        await self.db.flush()
        return subscription

    async def count_daily_entries(
        self,
        subscription_id: int,
        day_start_utc: datetime,
        day_end_utc: datetime,
    ) -> int:
        """Counts how many entries were logged for this subscription today."""
        result = await self.db.execute(
            select(func.count()).select_from(ParkingSession).where(
                ParkingSession.subscription_id == subscription_id,
                ParkingSession.entry_time >= day_start_utc,
                ParkingSession.entry_time < day_end_utc,
            )
        )
        return result.scalar_one()

    async def bulk_expire_overdue(self, today_cairo: date) -> int:
        """Expires overdue active subscriptions and frees their associated cards."""
        now = datetime.utcnow()
        # Find card IDs to free
        overdue_sub_query = select(Subscription.card_id).where(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.end_date < today_cairo,
        )
        # Update subscriptions to EXPIRED
        stmt_sub = (
            update(Subscription)
            .where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.end_date < today_cairo,
            )
            .values(status=SubscriptionStatus.EXPIRED, ended_at=now, updated_at=now)
        )
        res = await self.db.execute(stmt_sub)
        affected_count = res.rowcount

        if affected_count > 0:
            stmt_card = (
                update(ParkingCard)
                .where(ParkingCard.id.in_(overdue_sub_query))
                .values(status=CardStatus.AVAILABLE, updated_at=now)
            )
            await self.db.execute(stmt_card)

        await self.db.flush()
        return affected_count

    async def bulk_activate_pending(self, today_cairo: date) -> int:
        """Activates pending subscriptions whose start date has arrived."""
        now = datetime.utcnow()
        stmt = (
            update(Subscription)
            .where(
                Subscription.status == SubscriptionStatus.PENDING,
                Subscription.start_date <= today_cairo,
            )
            .values(status=SubscriptionStatus.ACTIVE, updated_at=now)
        )
        res = await self.db.execute(stmt)
        await self.db.flush()
        return res.rowcount

    async def get_expiring_soon(
        self, threshold_date: date
    ) -> list[Subscription]:
        """Gets active subscriptions expiring on or before threshold_date."""
        result = await self.db.execute(
            select(Subscription).where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.end_date <= threshold_date,
            ).order_by(Subscription.end_date.asc())
        )
        return list(result.scalars().all())

    async def get_all_by_subscriber(
        self, subscriber_id: int
    ) -> list[Subscription]:
        """Gets all historical and current subscriptions for a subscriber."""
        result = await self.db.execute(
            select(Subscription).where(
                Subscription.subscriber_id == subscriber_id
            ).order_by(Subscription.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_filtered(
        self,
        status: SubscriptionStatus | None = None,
        plan_id: int | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Subscription], int]:
        """Returns paginated subscriptions filtered by status and/or plan_id."""
        query = select(Subscription)
        count_query = select(func.count()).select_from(Subscription)

        if status is not None:
            query = query.where(Subscription.status == status)
            count_query = count_query.where(Subscription.status == status)
        if plan_id is not None:
            query = query.where(Subscription.plan_id == plan_id)
            count_query = count_query.where(Subscription.plan_id == plan_id)

        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar_one()

        offset_val = (page - 1) * size
        query = query.order_by(Subscription.created_at.desc()).offset(offset_val).limit(size)
        result = await self.db.execute(query)
        subscriptions = list(result.scalars().all())

        return subscriptions, total_count

    async def get_revenue_by_plan(
        self,
        start_utc: datetime | None = None,
        end_utc: datetime | None = None,
        plan_id: int | None = None,
    ) -> list[dict]:
        """Calculates revenue and subscription counts grouped by plan."""
        query = (
            select(
                Subscription.plan_id,
                SubscriptionPlan.label.label("plan_label"),
                func.count(Subscription.id).label("subscription_count"),
                func.coalesce(func.sum(Subscription.amount_paid_piastres), 0).label("total_piastres"),
            )
            .join(SubscriptionPlan, Subscription.plan_id == SubscriptionPlan.id)
            .where(Subscription.status != SubscriptionStatus.CANCELLED)
        )
        if start_utc is not None:
            query = query.where(Subscription.paid_at >= start_utc)
        if end_utc is not None:
            query = query.where(Subscription.paid_at < end_utc)
        if plan_id is not None:
            query = query.where(Subscription.plan_id == plan_id)

        query = query.group_by(Subscription.plan_id, SubscriptionPlan.label).order_by(
            func.coalesce(func.sum(Subscription.amount_paid_piastres), 0).desc()
        )
        result = await self.db.execute(query)
        return [
            {
                "plan_id": row.plan_id,
                "plan_label": row.plan_label,
                "subscription_count": row.subscription_count,
                "total_piastres": row.total_piastres,
            }
            for row in result.all()
        ]


__all__ = ["SubscriptionRepository"]
