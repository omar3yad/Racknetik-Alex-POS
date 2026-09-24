from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.subscription_plan import SubscriptionPlan


class SubscriptionPlanRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, plan_id: int) -> SubscriptionPlan | None:
        """Fetches a subscription plan by ID."""
        result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id).limit(1)
        )
        return result.scalars().first()

    async def get_by_label(self, label: str) -> SubscriptionPlan | None:
        """Fetches a subscription plan by unique label."""
        result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.label == label).limit(1)
        )
        return result.scalars().first()

    async def get_all(self, active_only: bool = False) -> list[SubscriptionPlan]:
        """Returns all subscription plans, ordered by price ascending."""
        query = select(SubscriptionPlan)
        if active_only:
            query = query.where(SubscriptionPlan.is_active.is_(True))
        query = query.order_by(SubscriptionPlan.price_piastres.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(
        self,
        label: str,
        duration_days: int,
        price_piastres: int,
        max_entries_per_day: int | None,
        description: str | None,
        created_by: int,
    ) -> SubscriptionPlan:
        """Creates a new active subscription plan and flushes."""
        plan = SubscriptionPlan(
            label=label,
            duration_days=duration_days,
            price_piastres=price_piastres,
            max_entries_per_day=max_entries_per_day,
            description=description,
            is_active=True,
            created_by=created_by,
        )
        self.db.add(plan)
        await self.db.flush()
        return plan

    async def update_fields(
        self, plan: SubscriptionPlan, **fields
    ) -> SubscriptionPlan:
        """Updates provided fields on the plan and flushes."""
        for key, value in fields.items():
            setattr(plan, key, value)
        await self.db.flush()
        return plan


__all__ = ["SubscriptionPlanRepository"]
