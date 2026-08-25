from datetime import datetime
import math
from types import SimpleNamespace
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.pricing_rule import PricingRule
from services.exceptions import NoPricingRuleError
from services.pricing_calculation import PriceCalculation

class PricingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_rule(self) -> PricingRule:
        """Fetches the active pricing rule from the database."""
        result = await self.db.execute(
            select(PricingRule).where(PricingRule.is_active == True).limit(1)
        )
        rule = result.scalars().first()
        if not rule:
            raise NoPricingRuleError("No active pricing rule")
        return rule

    def calculate(
        self,
        session: Any,
        rule: PricingRule,
        exit_time: datetime,
    ) -> PriceCalculation:
        """Synchronously and purely calculates pricing for a parking session."""
        # Ensure timezone-naive datetimes for calculation
        entry = session.entry_time
        if entry.tzinfo is not None:
            entry = entry.replace(tzinfo=None)
        exit_dt = exit_time
        if exit_dt.tzinfo is not None:
            exit_dt = exit_dt.replace(tzinfo=None)

        total_seconds = (exit_dt - entry).total_seconds()
        duration_minutes = math.ceil(total_seconds / 60)
        if duration_minutes < 0:
            duration_minutes = 0

        if duration_minutes <= rule.grace_period_mins:
            is_grace_period = True
            billable_minutes = 0
            billable_hours = 0
            base_amount = rule.minimum_charge
        else:
            is_grace_period = False
            billable_minutes = duration_minutes - rule.grace_period_mins
            billable_hours = math.ceil(billable_minutes / 60)
            raw = billable_hours * rule.rate_per_hour
            base_amount = max(raw, rule.minimum_charge)

        penalty_amount = 0
        total_amount = base_amount

        return PriceCalculation(
            duration_minutes=duration_minutes,
            billable_minutes=billable_minutes,
            billable_hours=billable_hours,
            rate_per_hour=rule.rate_per_hour,
            grace_period_mins=rule.grace_period_mins,
            minimum_charge=rule.minimum_charge,
            base_amount=base_amount,
            penalty_amount=penalty_amount,
            total_amount=total_amount,
            pricing_rule_id=rule.id,
            is_grace_period=is_grace_period,
            is_lost_card=False,
        )

    def calculate_lost_card(
        self,
        session: Any,
        rule: PricingRule,
        exit_time: datetime,
    ) -> PriceCalculation:
        """Calculates pricing for a parking session when the card is lost."""
        base_calc = self.calculate(session, rule, exit_time)
        return PriceCalculation(
            duration_minutes=base_calc.duration_minutes,
            billable_minutes=base_calc.billable_minutes,
            billable_hours=base_calc.billable_hours,
            rate_per_hour=base_calc.rate_per_hour,
            grace_period_mins=base_calc.grace_period_mins,
            minimum_charge=base_calc.minimum_charge,
            base_amount=base_calc.base_amount,
            penalty_amount=rule.lost_card_penalty,
            total_amount=base_calc.base_amount + rule.lost_card_penalty,
            pricing_rule_id=rule.id,
            is_grace_period=base_calc.is_grace_period,
            is_lost_card=True,
        )

    async def preview(self, entry_time: datetime) -> PriceCalculation:
        """Fetches the active rule and previews the price for the given entry time."""
        rule = await self.get_active_rule()
        if entry_time.tzinfo is not None:
            entry_time = entry_time.replace(tzinfo=None)
        mock_session = SimpleNamespace(entry_time=entry_time)
        return self.calculate(mock_session, rule, datetime.utcnow())

__all__ = ["PricingService"]
