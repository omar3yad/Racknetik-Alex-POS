from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator


class PricingRuleCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str = Field(max_length=100)
    rate_per_hour_egp: float = Field(ge=0)
    minimum_charge_egp: float = Field(default=0.0, ge=0)
    grace_period_mins: int = Field(default=15, ge=0)
    lost_card_penalty_egp: float = Field(default=0.0, ge=0)
    effective_from: datetime | None = None
    effective_until: datetime | None = None

    rate_per_hour: int = 0
    minimum_charge: int = 0
    lost_card_penalty: int = 0

    @model_validator(mode="after")
    def convert_egp_to_piastres(self) -> "PricingRuleCreate":
        self.rate_per_hour = round(self.rate_per_hour_egp * 100)
        self.minimum_charge = round(self.minimum_charge_egp * 100)
        self.lost_card_penalty = round(self.lost_card_penalty_egp * 100)
        return self


class PricingRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    rate_per_hour: int
    minimum_charge: int
    grace_period_mins: int
    lost_card_penalty: int
    is_active: bool
    created_by: int
    effective_from: datetime
    effective_until: datetime | None
    created_at: datetime
    updated_at: datetime


__all__ = [
    "PricingRuleCreate",
    "PricingRuleResponse",
]
