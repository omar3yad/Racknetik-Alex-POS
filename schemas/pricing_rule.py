from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator


class PricingRuleCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str = Field(max_length=100)
    rate_per_hour_egp: float = Field(ge=0)
    first_hour_charge_egp: float = Field(default=0.0, ge=0)
    subsequent_hour_charge_egp: float = Field(default=0.0, ge=0)
    minimum_charge_egp: float = Field(default=0.0, ge=0)
    grace_period_mins: int = Field(default=15, ge=0)
    lost_card_penalty_egp: float = Field(default=0.0, ge=0)
    effective_from: datetime | None = None
    effective_until: datetime | None = None

    rate_per_hour: int = 0
    first_hour_charge: int = 0
    subsequent_hour_charge: int = 0
    minimum_charge: int = 0
    lost_card_penalty: int = 0

    @model_validator(mode="after")
    def convert_egp_to_piastres(self) -> "PricingRuleCreate":
        self.rate_per_hour = round(self.rate_per_hour_egp * 100)
        self.first_hour_charge = round(self.first_hour_charge_egp * 100)
        self.subsequent_hour_charge = round(self.subsequent_hour_charge_egp * 100)
        self.minimum_charge = round(self.minimum_charge_egp * 100)
        self.lost_card_penalty = round(self.lost_card_penalty_egp * 100)
        return self


class PricingRuleUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str | None = Field(default=None, max_length=100)
    rate_per_hour_egp: float | None = Field(default=None, ge=0)
    first_hour_charge_egp: float | None = Field(default=None, ge=0)
    subsequent_hour_charge_egp: float | None = Field(default=None, ge=0)
    minimum_charge_egp: float | None = Field(default=None, ge=0)
    grace_period_mins: int | None = Field(default=None, ge=0)
    lost_card_penalty_egp: float | None = Field(default=None, ge=0)
    effective_from: datetime | None = None
    effective_until: datetime | None = None

    rate_per_hour: int | None = None
    first_hour_charge: int | None = None
    subsequent_hour_charge: int | None = None
    minimum_charge: int | None = None
    lost_card_penalty: int | None = None

    @model_validator(mode="after")
    def convert_egp_to_piastres(self) -> "PricingRuleUpdate":
        if self.rate_per_hour_egp is not None:
            self.rate_per_hour = round(self.rate_per_hour_egp * 100)
        if self.first_hour_charge_egp is not None:
            self.first_hour_charge = round(self.first_hour_charge_egp * 100)
        if self.subsequent_hour_charge_egp is not None:
            self.subsequent_hour_charge = round(self.subsequent_hour_charge_egp * 100)
        if self.minimum_charge_egp is not None:
            self.minimum_charge = round(self.minimum_charge_egp * 100)
        if self.lost_card_penalty_egp is not None:
            self.lost_card_penalty = round(self.lost_card_penalty_egp * 100)
        return self


class PricingRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    rate_per_hour: int
    first_hour_charge: int
    subsequent_hour_charge: int
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
    "PricingRuleUpdate",
    "PricingRuleResponse",
]
