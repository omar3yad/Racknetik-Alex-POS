import pytest
from pydantic import ValidationError

from schemas.pricing_rule import PricingRuleCreate


def test_egp_converted_to_piastres():
    rule = PricingRuleCreate(label="Test", rate_per_hour_egp=10.0)
    assert rule.rate_per_hour == 1000


def test_fractional_egp_rounded():
    rule = PricingRuleCreate(label="Test Rounding", rate_per_hour_egp=5.555)
    assert rule.rate_per_hour == 556


def test_zero_rate_valid():
    rule = PricingRuleCreate(label="Zero Rate", rate_per_hour_egp=0.0)
    assert rule.rate_per_hour == 0


def test_negative_rate_invalid():
    with pytest.raises(ValidationError):
        PricingRuleCreate(label="Negative Rate", rate_per_hour_egp=-1.0)


def test_lost_card_penalty_conversion():
    rule = PricingRuleCreate(label="Penalty Test", rate_per_hour_egp=10.0, lost_card_penalty_egp=25.50)
    assert rule.lost_card_penalty == 2550
