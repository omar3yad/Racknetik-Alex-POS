import dataclasses
from types import SimpleNamespace
from datetime import datetime, timedelta
from services.pricing_service import PricingService
from services.pricing_calculation import PriceCalculation

def make_rule(**overrides):
    defaults = {
        "id": 1,
        "rate_per_hour": 1000,     # 10 EGP
        "minimum_charge": 0,
        "grace_period_mins": 15,
        "lost_card_penalty": 2000,  # 20 EGP
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)

def make_session(entry_time):
    return SimpleNamespace(entry_time=entry_time)

def test_zero_duration():
    service = PricingService(db=None)
    rule = make_rule(minimum_charge=500)
    now = datetime.utcnow()
    session = make_session(now)
    
    calc = service.calculate(session, rule, now)
    assert calc.duration_minutes == 0
    assert calc.is_grace_period is True
    assert calc.total_amount == 500

def test_within_grace_period():
    service = PricingService(db=None)
    rule = make_rule(minimum_charge=500)
    now = datetime.utcnow()
    session = make_session(now - timedelta(minutes=10))
    
    calc = service.calculate(session, rule, now)
    assert calc.duration_minutes == 10
    assert calc.is_grace_period is True
    assert calc.total_amount == 500

def test_exactly_grace_period():
    service = PricingService(db=None)
    rule = make_rule(minimum_charge=500)
    now = datetime.utcnow()
    session = make_session(now - timedelta(minutes=15))
    
    calc = service.calculate(session, rule, now)
    assert calc.duration_minutes == 15
    assert calc.is_grace_period is True
    assert calc.total_amount == 500

def test_one_minute_over_grace():
    service = PricingService(db=None)
    rule = make_rule(minimum_charge=500, rate_per_hour=1000)
    now = datetime.utcnow()
    session = make_session(now - timedelta(minutes=16))
    
    calc = service.calculate(session, rule, now)
    assert calc.duration_minutes == 16
    assert calc.is_grace_period is False
    assert calc.billable_hours == 1
    assert calc.base_amount == 1000

def test_ninety_minutes():
    service = PricingService(db=None)
    rule = make_rule(minimum_charge=500, rate_per_hour=1000)
    now = datetime.utcnow()
    session = make_session(now - timedelta(minutes=90))
    
    calc = service.calculate(session, rule, now)
    # 90 minutes. Grace period is 15 minutes.
    # 90 is > 15, so not grace.
    # Billable hours = ceil(90/60) = 2.
    assert calc.is_grace_period is False
    assert calc.billable_hours == 2
    assert calc.base_amount == 2000

def test_minimum_charge_applied():
    service = PricingService(db=None)
    rule = make_rule(minimum_charge=500, rate_per_hour=100)
    now = datetime.utcnow()
    session = make_session(now - timedelta(minutes=60)) # 1 hour
    
    calc = service.calculate(session, rule, now)
    # 60 mins > 15 mins grace.
    # 1 hour * 100 = 100.
    # Minimum charge is 500. So total = 500.
    assert calc.base_amount == 500

def test_no_floats_in_result():
    service = PricingService(db=None)
    rule = make_rule(minimum_charge=500, rate_per_hour=1000)
    now = datetime.utcnow()
    session = make_session(now - timedelta(minutes=75))
    
    calc = service.calculate(session, rule, now)
    for field in dataclasses.fields(PriceCalculation):
        val = getattr(calc, field.name)
        if field.type is int:
            assert isinstance(val, int)

def test_adds_penalty():
    service = PricingService(db=None)
    rule = make_rule(minimum_charge=500, lost_card_penalty=2000)
    now = datetime.utcnow()
    session = make_session(now - timedelta(hours=2))
    
    # Let's say base calculated is 1000
    calc = service.calculate_lost_card(session, rule, now)
    assert calc.is_lost_card is True
    assert calc.penalty_amount == 2000
    # 2 hours * 1000 = 2000 base. Total = 2000 + 2000 = 4000
    assert calc.total_amount == 4000

def test_penalty_on_grace_period_session():
    service = PricingService(db=None)
    rule = make_rule(minimum_charge=500, lost_card_penalty=2000)
    now = datetime.utcnow()
    session = make_session(now - timedelta(minutes=5)) # within grace
    
    calc = service.calculate_lost_card(session, rule, now)
    # base should be minimum_charge (500)
    assert calc.base_amount == 500
    assert calc.penalty_amount == 2000
    assert calc.total_amount == 2500

def test_zero_penalty():
    service = PricingService(db=None)
    rule = make_rule(minimum_charge=500, lost_card_penalty=0)
    now = datetime.utcnow()
    session = make_session(now - timedelta(hours=2))
    
    calc = service.calculate_lost_card(session, rule, now)
    assert calc.penalty_amount == 0
    assert calc.total_amount == calc.base_amount
