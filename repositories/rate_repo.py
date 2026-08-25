from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.pricing_rule import PricingRule

class PricingRuleRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active(self) -> PricingRule | None:
        """Fetches the current active pricing rule, returning None if not found."""
        result = await self.db.execute(
            select(PricingRule).where(PricingRule.is_active == True).limit(1)
        )
        return result.scalars().first()

    async def get_by_id(self, rule_id: int) -> PricingRule | None:
        """Fetches a pricing rule by its id."""
        result = await self.db.execute(
            select(PricingRule).where(PricingRule.id == rule_id).limit(1)
        )
        return result.scalars().first()

    async def get_all(
        self, page: int = 1, size: int = 20
    ) -> tuple[list[PricingRule], int]:
        """Returns a paginated list of pricing rules and the total count."""
        query = select(PricingRule)
        count_query = select(func.count()).select_from(PricingRule)

        # Count total
        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar_one()

        # Paginated query
        offset_val = (page - 1) * size
        query = query.offset(offset_val).limit(size)
        result = await self.db.execute(query)
        rules = list(result.scalars().all())

        return rules, total_count

    async def create(self, **kwargs) -> PricingRule:
        """Creates a pricing rule, flushing changes."""
        rule = PricingRule(**kwargs)
        self.db.add(rule)
        await self.db.flush()
        return rule

    async def set_active(self, rule_id: int) -> PricingRule:
        """Sets the pricing rule as active, deactivating all other rules."""
        # Check that the rule exists first
        result = await self.db.execute(
            select(PricingRule).where(PricingRule.id == rule_id).limit(1)
        )
        rule = result.scalars().first()
        if not rule:
            raise ValueError(f"PricingRule with id {rule_id} not found")

        # Deactivate all rules
        await self.db.execute(
            update(PricingRule).values(is_active=False)
        )
        
        # Activate the targeted rule
        rule.is_active = True
        await self.db.flush()
        return rule

__all__ = ["PricingRuleRepository"]
