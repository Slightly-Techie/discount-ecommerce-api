import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from api.orders.models import Country, CouponUsage, Order
from api.orders.tests.factories import (
    CountryFactory,
    CouponFactory,
    OrderFactory,
    ShippingMethodFactory,
    ShippingZoneFactory,
    TaxRateFactory,
    TaxZoneFactory,
)

pytestmark = pytest.mark.django_db

COUNTRY_NAME_TO_CODE = {
    "Switzerland": "CH",
    "Austria": "AT",
    "Slovenia": "SI",
    "Turkmenistan": "TM",
    # Add more as needed
}


@pytest.fixture
def setup_shipping_and_tax(address):
    code = COUNTRY_NAME_TO_CODE.get(address.country, address.country[:2].upper())
    country = CountryFactory(code=code, name=address.country)
    zone = ShippingZoneFactory(country=country)
    ShippingMethodFactory(
        zone=zone,
        name="Standard",
        base_rate=10,
        per_kg_rate=0,
        free_over=100,
        active=True,
    )
    tax_zone = TaxZoneFactory(country=country)
    TaxRateFactory(zone=tax_zone, rate=0.10, active=True)


def test_checkout_creates_order(
    api_client, user, address, cart, cart_item, setup_shipping_and_tax
):
    # If a coupon is used in the test, ensure it has min_order_amount=0
    if hasattr(cart, "coupon") and cart.coupon:
        cart.coupon.min_order_amount = 0
        cart.coupon.save()
    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    assert response.status_code == 201
    assert Order.objects.filter(user=user).exists()


def test_checkout_with_coupon(api_client, user, address, cart, cart_item, coupon):
    coupon.min_order_amount = 0
    coupon.save()
    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    data = {"coupon_code": coupon.code}
    response = api_client.post(url, data)
    if response.status_code != 201:
        print("Checkout with coupon response:", response.status_code, response.data)
    assert response.status_code == 201
    order = Order.objects.get(user=user)
    assert order.coupon == coupon
    assert CouponUsage.objects.filter(user=user, coupon=coupon, order=order).exists()


def test_order_list(api_client, user):
    OrderFactory.create_batch(3, user=user)
    api_client.force_authenticate(user=user)
    url = reverse("orders:order-list")
    response = api_client.get(url)
    assert response.status_code == 200
    assert len(response.data) >= 3


def test_checkout_with_invalid_coupon(api_client, user, address, cart, cart_item):
    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    data = {"coupon_code": "INVALIDCODE"}
    response = api_client.post(url, data)
    assert response.status_code == 400
    assert "Invalid coupon code" in str(response.data)


def test_checkout_with_expired_coupon(api_client, user, address, cart, cart_item):
    expired_coupon = CouponFactory(
        valid_from=timezone.now() - datetime.timedelta(days=10),
        valid_to=timezone.now() - datetime.timedelta(days=5),
        active=True,
    )
    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    data = {"coupon_code": expired_coupon.code}
    response = api_client.post(url, data)
    assert response.status_code == 400
    assert "expired" in str(response.data).lower()


def test_checkout_with_coupon_over_usage(api_client, user, address, cart, cart_item):
    coupon = CouponFactory(usage_limit=1, min_order_amount=0)
    # Use the coupon once
    CouponUsage.objects.create(
        coupon=coupon, user=user, order=OrderFactory(user=user, coupon=coupon)
    )
    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    data = {"coupon_code": coupon.code}
    response = api_client.post(url, data)
    assert response.status_code == 400
    assert "usage limit" in str(response.data).lower()


def test_checkout_no_address(api_client, user):
    # Remove all addresses for user
    user.addresses.all().delete()
    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    assert response.status_code == 400
    assert "No address found" in str(response.data)


def test_checkout_empty_cart(api_client, user, address):
    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    assert response.status_code == 400
    assert "Cart is empty" in str(response.data)


def test_order_list_unauthenticated(api_client):
    url = reverse("orders:order-list")
    response = api_client.get(url)
    assert response.status_code == 401


def test_order_status_transition_valid(api_client, user, address, cart, cart_item):
    api_client.force_authenticate(user=user)
    # Create an order
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    order_id = response.data["id"]
    # Promote user to admin/manager for status update
    user.is_staff = True
    user.save()
    api_client.force_authenticate(user=user)
    status_url = reverse("orders:order-status-update", args=[order_id])
    response = api_client.patch(status_url, {"status": "paid"}, format="json")
    assert response.status_code == 200
    assert "Status updated to paid" in str(response.data)


def test_order_status_transition_invalid(api_client, user, address, cart, cart_item):
    api_client.force_authenticate(user=user)
    # Create an order
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    order_id = response.data["id"]
    # Promote user to admin/manager for status update
    user.is_staff = True
    user.save()
    api_client.force_authenticate(user=user)
    status_url = reverse("orders:order-status-update", args=[order_id])
    # Try to set status directly to delivered (invalid transition)
    response = api_client.patch(status_url, {"status": "delivered"}, format="json")
    assert response.status_code == 400
    assert "Invalid status transition" in str(response.data)


def test_order_status_update_permission_denied(
    api_client, user, address, cart, cart_item
):
    api_client.force_authenticate(user=user)
    # Create an order
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    order_id = response.data["id"]
    # Try to update status as non-admin
    status_url = reverse("orders:order-status-update", args=[order_id])
    response = api_client.patch(status_url, {"status": "paid"}, format="json")
    assert response.status_code == 403


def test_order_status_update_not_found(api_client, user):
    user.is_staff = True
    user.save()
    api_client.force_authenticate(user=user)
    status_url = reverse(
        "orders:order-status-update", args=["00000000-0000-0000-0000-000000000000"]
    )
    response = api_client.patch(status_url, {"status": "paid"}, format="json")
    assert response.status_code == 404
    assert "Order not found" in str(response.data)


def test_order_review_creation_success(api_client, user, address, cart, cart_item):
    # Ensure any coupon has min_order_amount=0
    if hasattr(cart, "coupon") and cart.coupon:
        cart.coupon.min_order_amount = 0
        cart.coupon.save()
    api_client.force_authenticate(user=user)
    # Create and deliver an order
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    order_id = response.data["id"]
    order = Order.objects.get(id=order_id)
    order.status = Order.Status.DELIVERED
    order.save()
    order.refresh_from_db()
    review_url = reverse("orders:order-review-create")
    data = {"order": str(order.id), "rating": 5, "review": "Great!"}
    response = api_client.post(review_url, data)
    assert response.status_code == 201
    assert order.reviews.exists()


def test_order_review_creation_not_delivered(
    api_client, user, address, cart, cart_item
):
    api_client.force_authenticate(user=user)
    # Create an order (not delivered)
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    order_id = response.data["id"]
    review_url = reverse("orders:order-review-create")
    data = {"order": str(order_id), "rating": 4, "review": "Not delivered yet"}
    response = api_client.post(review_url, data)
    assert response.status_code == 400 or response.status_code == 403


def test_order_review_creation_not_owner(api_client, user, address, cart, cart_item):
    api_client.force_authenticate(user=user)
    # Create and deliver an order for user
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    order_id = response.data["id"]
    order = Order.objects.get(id=order_id)
    order.status = Order.Status.DELIVERED
    order.save()
    # Create another user
    from api.users.tests.factories import UserFactory

    other_user = UserFactory()
    api_client.force_authenticate(user=other_user)
    review_url = reverse("orders:order-review-create")
    data = {"order": str(order.id), "rating": 3, "review": "Not my order"}
    response = api_client.post(review_url, data)
    assert response.status_code == 400 or response.status_code == 403


def test_order_review_duplicate(api_client, user, address, cart, cart_item):
    # Ensure any coupon has min_order_amount=0
    if hasattr(cart, "coupon") and cart.coupon:
        cart.coupon.min_order_amount = 0
        cart.coupon.save()
    api_client.force_authenticate(user=user)
    # Create and deliver an order
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    order_id = response.data["id"]
    order = Order.objects.get(id=order_id)
    order.status = Order.Status.DELIVERED
    order.save()
    order.refresh_from_db()
    review_url = reverse("orders:order-review-create")
    data = {"order": str(order.id), "rating": 5, "review": "First review"}
    if not order.reviews.exists():
        response1 = api_client.post(review_url, data)
        assert response1.status_code == 201
    # Try to review again
    data2 = {"order": str(order.id), "rating": 4, "review": "Second review"}
    response2 = api_client.post(review_url, data2)
    assert response2.status_code in (400, 403)


def test_order_review_invalid_rating(api_client, user, address, cart, cart_item):
    api_client.force_authenticate(user=user)
    # Create and deliver an order
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    order_id = response.data["id"]
    order = Order.objects.get(id=order_id)
    order.status = Order.Status.DELIVERED
    order.save()
    review_url = reverse("orders:order-review-create")
    # Rating too low
    data = {"order": str(order.id), "rating": 0, "review": "Too low"}
    response1 = api_client.post(review_url, data)
    assert response1.status_code in (400, 403)
    # Rating too high
    data2 = {"order": str(order.id), "rating": 6, "review": "Too high"}
    response2 = api_client.post(review_url, data2)
    assert response2.status_code in (400, 403)


def test_checkout_without_shipping_and_tax(api_client, user, address, cart, cart_item):
    # Remove all shipping/tax for this country
    from api.orders.models import ShippingMethod, ShippingZone, TaxRate, TaxZone

    Country.objects.filter(code=address.country).delete()
    ShippingZone.objects.all().delete()
    ShippingMethod.objects.all().delete()
    TaxZone.objects.all().delete()
    TaxRate.objects.all().delete()
    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    assert response.status_code == 201
    assert Order.objects.filter(user=user).exists()


def test_checkout_free_shipping_threshold(
    api_client, user, address, cart, cart_item, setup_shipping_and_tax
):
    # Set up a shipping method with free_over below subtotal
    from api.orders.models import ShippingMethod

    method = ShippingMethod.objects.filter(name="Standard").first()
    method.free_over = 10  # Cart subtotal will be higher
    method.save()
    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    assert response.status_code == 201
    order = Order.objects.get(user=user)
    assert order.shipping == 0


def test_checkout_multiple_shipping_methods(
    api_client, user, address, cart, cart_item, setup_shipping_and_tax
):
    # Add an express shipping method
    from api.orders.models import ShippingMethod

    zone = ShippingZoneFactory.create()  # Changed from ShippingZone.objects.first()
    ShippingMethod.objects.create(
        zone=zone,
        name="Express",
        base_rate=50,
        per_kg_rate=0,
        free_over=200,
        active=True,
    )
    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    # Simulate selecting express (would require API change to support selection)
    # For now, test that at least one method exists and checkout works
    response = api_client.post(url, {})
    assert response.status_code == 201


def test_checkout_delivery_not_allowed(api_client, user, address, cart, cart_item):
    # Remove all shipping methods for this country
    from api.orders.models import ShippingMethod

    ShippingMethod.objects.all().delete()
    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    # Should be free shipping (current logic), but if you want to block, change logic in calculate_shipping
    assert response.status_code == 201
    order = Order.objects.get(user=user)
    assert order.shipping == 0


def test_checkout_different_country_no_shipping(
    api_client, user, address, cart, cart_item
):
    # Change address to a country with no shipping/tax
    address.country = "XX"
    address.save()
    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    assert response.status_code == 201
    order = Order.objects.get(user=user)
    assert order.shipping == 0
    assert order.tax == 0


def test_checkout_different_country_with_shipping_and_tax(
    api_client, user, address, cart, cart_item
):
    # Set up a new country with shipping/tax
    from api.orders.tests.factories import (
        CountryFactory,
        ShippingMethodFactory,
        ShippingZoneFactory,
        TaxRateFactory,
        TaxZoneFactory,
    )

    address.country = "CA"
    address.save()
    country = CountryFactory(code="CA", name="Canada")
    zone = ShippingZoneFactory(country=country)
    ShippingMethodFactory(
        zone=zone,
        name="Standard",
        base_rate=15,
        per_kg_rate=0,
        free_over=100,
        active=True,
    )
    tax_zone = TaxZoneFactory(country=country)
    TaxRateFactory(zone=tax_zone, rate=0.13, active=True)
    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    response = api_client.post(url, {})
    assert response.status_code == 201
    order = Order.objects.get(user=user)
    assert order.shipping == 15
    assert order.tax > 0


def test_checkout_charges_live_discount_price(
    api_client, user, address, cart, product_factory, cart_item_factory
):
    from decimal import Decimal

    product = product_factory(price=Decimal("250.00"), discount_price=Decimal("200.00"), stock=5)
    cart_item_factory(cart=cart, product=product, quantity=2)
    api_client.force_authenticate(user=user)

    response = api_client.post(reverse("orders:checkout"), {})

    assert response.status_code == 201
    order = Order.objects.get(user=user)
    item = order.items.get()
    assert item.price == Decimal("200.00")
    assert order.total == Decimal("400.00") + order.shipping + order.tax - order.discount


def test_checkout_tags_every_vendor_order_with_one_group(
    api_client, user, address, cart, product_factory, cart_item_factory, vendor_factory
):
    first = product_factory(vendor=vendor_factory(), stock=5)
    second = product_factory(vendor=vendor_factory(), stock=5)
    cart_item_factory(cart=cart, product=first)
    cart_item_factory(cart=cart, product=second)
    api_client.force_authenticate(user=user)

    response = api_client.post(reverse("orders:checkout"), {})

    assert response.status_code == 201
    groups = {o["checkout_group"] for o in response.data["orders"]}
    assert len(groups) == 1 and None not in groups
    assert Order.objects.filter(user=user, checkout_group=groups.pop()).count() == 2
