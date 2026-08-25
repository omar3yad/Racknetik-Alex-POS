from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class PricingRuleCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    label: str = Field(max_length=100)
    rate_per_hour: int = Field(gt=0)
    minimum_charge: int = Field(ge=0)
    grace_period_mins: int = Field(ge=0)
    lost_card_penalty: int = Field(ge=0)
    effective_from: datetime
    effective_until: datetime | None = None

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
