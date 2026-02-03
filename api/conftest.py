import pytest
from pytest_factoryboy import register
from rest_framework.test import APIClient

# Cart
from api.cart.tests.factories import CartFactory, CartItemFactory

# Category
from api.category.tests.factories import CategoryFactory, TagFactory

# Orders
from api.orders.tests.factories import (
    CouponFactory,
    CouponUsageFactory,
    OrderFactory,
    OrderItemFactory,
    OrderReviewFactory,
)

# Products
from api.products.tests.factories import (
    ProductFactory,
    ProductImageFactory,
    ProductReviewFactory,
    ProductVariantFactory,
)

# Users
from api.users.tests.factories import AddressFactory, ProfileFactory, UserFactory

# Vendors
from api.vendors.tests.factories import VendorFactory

register(CouponFactory)
register(CouponUsageFactory)
register(OrderFactory)
register(OrderItemFactory)
register(OrderReviewFactory)
register(UserFactory)
register(ProfileFactory)
register(AddressFactory)
register(ProductFactory)
register(ProductImageFactory)
register(ProductVariantFactory)
register(ProductReviewFactory)
register(CategoryFactory)
register(TagFactory)
register(CartFactory)
register(CartItemFactory)
register(VendorFactory)
# BaseModelFactory is abstract, not registered as a fixture


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def address(user):
    return AddressFactory(user=user, is_default=True)


@pytest.fixture
def product():
    return ProductFactory()


@pytest.fixture
def coupon():
    return CouponFactory()


@pytest.fixture
def cart(user):
    cart = CartFactory(user=user, is_active=True, checked_out=False)
    return cart


@pytest.fixture
def cart_item(cart, product):
    item = CartItemFactory(cart=cart, product=product)
    # Ensure the cart has at least one item
    cart.items.add(item)
    return item
