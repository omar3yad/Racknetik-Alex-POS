from dataclasses import dataclass

@dataclass(frozen=True)
class PriceCalculation:
    duration_minutes: int
    billable_minutes: int
    billable_hours: int
    rate_per_hour: int
    grace_period_mins: int
    minimum_charge: int
    base_amount: int
    penalty_amount: int
    total_amount: int
    pricing_rule_id: int
    is_grace_period: bool
    is_lost_card: bool

__all__ = ["PriceCalculation"]
