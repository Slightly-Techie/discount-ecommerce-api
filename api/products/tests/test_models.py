import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

pytestmark = pytest.mark.django_db

NOW = timezone.make_aware(datetime.datetime(2026, 10, 16, 12, 0))


def test_current_price_uses_live_discount(product_factory):
    p = product_factory(price=Decimal("250.00"), discount_price=Decimal("200.00"))
    assert p.current_price(NOW) == Decimal("200.00")


def test_current_price_ignores_discount_outside_window(product_factory):
    future = product_factory(
        price=Decimal("250.00"), discount_price=Decimal("200.00"),
        discount_start=NOW + datetime.timedelta(days=1),
    )
    expired = product_factory(
        price=Decimal("250.00"), discount_price=Decimal("200.00"),
        discount_end=NOW - datetime.timedelta(minutes=1),
    )
    assert future.current_price(NOW) == Decimal("250.00")
    assert expired.current_price(NOW) == Decimal("250.00")


def test_current_price_ignores_discount_not_lower_than_price(product_factory):
    p = product_factory(price=Decimal("100.00"), discount_price=Decimal("120.00"))
    assert p.current_price(NOW) == Decimal("100.00")
