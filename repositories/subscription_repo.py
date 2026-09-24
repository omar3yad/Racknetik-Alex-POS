from datetime import date, datetime
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.subscription import Subscription, SubscriptionStatus
from models.parking_card import ParkingCard, CardStatus
from models.parking_session import ParkingSession


class SubscriptionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, subscription_id: int) -> Subscription | None:
        result = await self.db.execute(
            select(Subscription)
            .where(Subscription.id == subscription_id)
            .options(
                selectinload(Subscription.plan),
                selectinload(Subscription.subscriber),
                selectinload(Subscription.card),
            )
        )
        return result.scalars().first()

    async def get_active_for_card(
        self, card_id: int, today: date
    ) -> Subscription | None:
        result = await self.db.execute(
            select(Subscription)
            .where(
                Subscription.card_id == card_id,
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING]),
                Subscription.start_date <= today,
                Subscription.end_date >= today,
            )
            .options(
                selectinload(Subscription.plan),
                selectinload(Subscription.subscriber),
                selectinload(Subscription.card),
            )
            .limit(1)
        )
        return result.scalars().first()

    async def get_active_for_subscriber(
        self, subscriber_id: int
    ) -> Subscription | None:
        result = await self.db.execute(
            select(Subscription)
            .where(
                Subscription.subscriber_id == subscriber_id,
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING]),
            )
            .options(
                selectinload(Subscription.plan),
                selectinload(Subscription.subscriber),
                selectinload(Subscription.card),
            )
            .limit(1)
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
        paid_at: datetime | None = None,
        collected_by: int | None = None,
        notes: str | None = None,
        previous_subscription_id: int | None = None,
        renewal_count: int = 0,
    ) -> Subscription:
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
            notes=notes,
            previous_subscription_id=previous_subscription_id,
            renewal_count=renewal_count,
        )
        self.db.add(subscription)
        await self.db.flush()
        return subscription

    async def count_daily_entries(
        self,
        subscription_id: int,
        day_start_utc: datetime,
        day_end_utc: datetime,
    ) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(ParkingSession).where(
                ParkingSession.subscription_id == subscription_id,
                ParkingSession.entry_time >= day_start_utc,
                ParkingSession.entry_time < day_end_utc,
            )
        )
        return result.scalar_one()

    async def bulk_expire_overdue(self, today: date) -> int:
        expired_subs_res = await self.db.execute(
            select(Subscription).where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.end_date < today,
            )
        )
        expired_subs = expired_subs_res.scalars().all()
        if not expired_subs:
            return 0

        now = datetime.utcnow()
        expired_ids = [s.id for s in expired_subs]
        card_ids = [s.card_id for s in expired_subs]

        await self.db.execute(
            update(Subscription)
            .where(Subscription.id.in_(expired_ids))
            .values(status=SubscriptionStatus.EXPIRED, ended_at=now)
        )

        await self.db.execute(
            update(ParkingCard)
            .where(ParkingCard.id.in_(card_ids))
            .values(status=CardStatus.AVAILABLE)
        )

        return len(expired_ids)

    async def bulk_activate_pending(self, today: date) -> int:
        pending_subs_res = await self.db.execute(
            select(Subscription).where(
                Subscription.status == SubscriptionStatus.PENDING,
                Subscription.start_date <= today,
                Subscription.end_date >= today,
            )
        )
        pending_subs = pending_subs_res.scalars().all()
        if not pending_subs:
            return 0

        pending_ids = [s.id for s in pending_subs]
        card_ids = [s.card_id for s in pending_subs]

        await self.db.execute(
            update(Subscription)
            .where(Subscription.id.in_(pending_ids))
            .values(status=SubscriptionStatus.ACTIVE)
        )

        await self.db.execute(
            update(ParkingCard)
            .where(ParkingCard.id.in_(card_ids))
            .values(status=CardStatus.IN_USE)
        )

        return len(pending_ids)

    async def get_expiring_soon(self, threshold_date: date) -> list[Subscription]:
        result = await self.db.execute(
            select(Subscription)
            .where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.end_date <= threshold_date,
            )
            .options(
                selectinload(Subscription.plan),
                selectinload(Subscription.subscriber),
                selectinload(Subscription.card),
            )
            .order_by(Subscription.end_date.asc())
        )
        return list(result.scalars().all())

    async def list_all(
        self,
        status: SubscriptionStatus | None = None,
        plan_id: int | None = None,
        subscriber_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Subscription]:
        query = select(Subscription).options(
            selectinload(Subscription.plan),
            selectinload(Subscription.subscriber),
            selectinload(Subscription.card),
        )
        if status is not None:
            query = query.where(Subscription.status == status)
        if plan_id is not None:
            query = query.where(Subscription.plan_id == plan_id)
        if subscriber_id is not None:
            query = query.where(Subscription.subscriber_id == subscriber_id)
        query = query.order_by(Subscription.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_fields(self, subscription: Subscription, **kwargs) -> Subscription:
        for key, value in kwargs.items():
            setattr(subscription, key, value)
        await self.db.flush()
        return subscription
