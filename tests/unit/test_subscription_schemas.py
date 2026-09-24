import pytest
from datetime import date, datetime
from pydantic import ValidationError
from models.subscription import SubscriptionStatus
from schemas.subscriptions import (
    PlanCreate,
    PlanUpdate,
    PlanResponse,
    SubscriberCreate,
    SubscriberUpdate,
    SubscriberResponse,
    SubscriptionCreate,
    SubscriptionRenew,
    SubscriptionCancel,
    SubscriptionResponse,
)


def test_plan_create_price_conversion():
    plan = PlanCreate(
        label="Monthly Standard",
        duration_days=30,
        price_egp=150.0,
        max_entries_per_day=1,
        description="Standard 1 entry/day",
    )
    assert plan.price_piastres == 15000
    assert plan.duration_days == 30
    assert plan.label == "Monthly Standard"


def test_plan_create_invalid_values():
    with pytest.raises(ValidationError):
        PlanCreate(label="", duration_days=0, price_egp=-10.0)


def test_plan_update_partial():
    update = PlanUpdate(price_egp=200.0)
    assert update.price_piastres == 20000
    assert update.label is None

    update_none = PlanUpdate()
    assert update_none.price_piastres is None


def test_plan_response_computed_field():
    now = datetime.utcnow()
    data = {
        "id": 1,
        "label": "VIP",
        "duration_days": 30,
        "price_piastres": 25000,
        "max_entries_per_day": None,
        "description": "VIP plan",
        "is_active": True,
        "created_by": 1,
        "created_at": now,
        "updated_at": now,
    }
    resp = PlanResponse.model_validate(data)
    assert resp.price_egp == 250.0
    assert resp.label == "VIP"


def test_subscriber_create_valid():
    sub = SubscriberCreate(
        full_name="Mahmoud Hassan",
        phone_number="01123456789",
        plate_number="س ص ع 456",
        notes="Important client",
    )
    assert sub.full_name == "Mahmoud Hassan"
    assert sub.plate_number == "س ص ع 456"


def test_subscriber_create_invalid_plate():
    with pytest.raises(ValidationError):
        SubscriberCreate(full_name="Mahmoud Hassan", plate_number="")


def test_subscriber_update_partial():
    update = SubscriberUpdate(full_name="New Name")
    assert update.full_name == "New Name"
    assert update.phone_number is None


def test_subscription_create_conversion():
    today = date(2026, 9, 24)
    create = SubscriptionCreate(
        subscriber_id=1,
        plan_id=2,
        card_id=3,
        start_date=today,
        amount_paid_egp=500.0,
    )
    assert create.amount_paid_piastres == 50000
    assert create.start_date == today


def test_subscription_renew_conversion():
    renew = SubscriptionRenew(amount_paid_egp=450.0, notes="Discounted renewal")
    assert renew.amount_paid_piastres == 45000
    assert renew.plan_id is None


def test_subscription_cancel():
    cancel = SubscriptionCancel(cancel_reason="Customer request")
    assert cancel.cancel_reason == "Customer request"


def test_subscription_response_computed_fields():
    now = datetime.utcnow()
    today = date(2026, 9, 24)
    end = date(2026, 10, 24)
    data = {
        "id": 10,
        "subscriber_id": 1,
        "plan_id": 2,
        "card_id": 3,
        "plate_number": "س ص ع 456",
        "start_date": today,
        "end_date": end,
        "status": SubscriptionStatus.ACTIVE,
        "amount_paid_piastres": 50000,
        "plan_price_snapshot": 50000,
        "paid_at": now,
        "collected_by": 1,
        "renewal_count": 0,
        "previous_subscription_id": None,
        "cancel_reason": None,
        "ended_at": None,
        "notes": None,
        "created_at": now,
        "updated_at": now,
    }
    resp = SubscriptionResponse.model_validate(data)
    assert resp.amount_paid_egp == 500.0
    assert resp.plan_price_snapshot_egp == 500.0
    assert resp.status == SubscriptionStatus.ACTIVE
