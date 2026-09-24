import json
from datetime import date, datetime, timedelta
import pytest
from utils.jinja import (
    days_remaining_filter,
    subscription_status_label_filter,
    subscription_status_class_filter,
    cairo_date_filter,
)
from utils.time import cairo_now
from models.subscription import SubscriptionStatus


def test_days_remaining_filter():
    today = cairo_now().date()
    assert days_remaining_filter(None) == 0
    assert days_remaining_filter(today + timedelta(days=5)) == 5
    assert days_remaining_filter(today) == 0
    assert days_remaining_filter(today - timedelta(days=2)) == 0


def test_subscription_status_label_filter():
    assert subscription_status_label_filter('ACTIVE') == 'نشط'
    assert subscription_status_label_filter('EXPIRED') == 'منتهي'
    assert subscription_status_label_filter('CANCELLED') == 'ملغي'
    assert subscription_status_label_filter('PENDING') == 'معلق'
    assert subscription_status_label_filter(SubscriptionStatus.ACTIVE) == 'نشط'
    assert subscription_status_label_filter('UNKNOWN') == 'UNKNOWN'


def test_subscription_status_class_filter():
    assert 'green' in subscription_status_class_filter('ACTIVE')
    assert 'gray' in subscription_status_class_filter('EXPIRED')
    assert 'red' in subscription_status_class_filter('CANCELLED')
    assert 'amber' in subscription_status_class_filter('PENDING')
    assert subscription_status_class_filter(SubscriptionStatus.ACTIVE) == 'bg-green-100 text-green-800'
    assert subscription_status_class_filter('UNKNOWN') == 'bg-gray-100 text-gray-500'


def test_cairo_date_filter():
    assert cairo_date_filter(None) == '—'
    d = date(2026, 9, 24)
    assert cairo_date_filter(d) == '2026-09-24'
    dt = datetime(2026, 9, 24, 10, 0, 0)
    assert cairo_date_filter(dt) == '2026-09-24'


def test_translations_ar_json_validity_and_keys():
    with open('/srv/pgms/app/translations/ar.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert isinstance(data, dict)
    required_keys = [
        'subscriptions.plan.title',
        'subscriptions.plan.create',
        'subscriptions.plan.label',
        'subscriptions.plan.duration',
        'subscriptions.plan.price',
        'subscriptions.plan.max_entries',
        'subscriptions.plan.unlimited',
        'subscriptions.subscriber.title',
        'subscriptions.subscriber.new',
        'subscriptions.subscriber.plate',
        'subscriptions.subscriber.phone',
        'subscriptions.subscription.title',
        'subscriptions.subscription.start',
        'subscriptions.subscription.end',
        'subscriptions.subscription.days_remaining',
        'subscriptions.subscription.renew',
        'subscriptions.subscription.cancel',
        'subscriptions.subscription.amount_paid',
        'operator.entry.subscribed_banner',
        'operator.entry.subscription_expires',
        'operator.entry.subscription_expired_warning',
        'operator.exit.subscription_confirm_button',
        'receipt.subscription_title',
        'receipt.subscription_plan',
        'receipt.subscription_end_date',
        'admin.dashboard.expiring_soon',
        'admin.dashboard.expired_unrenewed',
        'errors.plan_label_exists',
        'errors.plan_not_active',
        'errors.subscriber_plate_exists',
        'errors.subscriber_already_subscribed',
        'errors.subscription_not_active',
        'errors.subscription_daily_limit',
    ]
    for k in required_keys:
        assert k in data, f'Missing translation key: {k}'
