# Testing Guide

## Test Setup & Configuration

### Pytest Configuration (pytest.ini:1)
```ini
[pytest]
DJANGO_SETTINGS_MODULE = core.settings
python_files = tests/test_*.py tests/*/test_*.py
addopts = --reuse-db
```

**Key Settings**:
- `DJANGO_SETTINGS_MODULE`: Uses production settings for tests
- `python_files`: Test discovery pattern
- `--reuse-db`: Faster test runs by reusing database between sessions

### Running Tests

**All tests**:
```bash
pytest
```

**Specific app**:
```bash
pytest api/products/tests/
pytest api/users/tests/test_views.py
```

**By test name pattern**:
```bash
pytest -k "test_product_list"
pytest -k "test_user"
```

**With verbose output**:
```bash
pytest -v
pytest -vv  # Extra verbose
```

**With coverage**:
```bash
pytest --cov=api --cov-report=html
```

**Reuse database** (faster for repeated runs):
```bash
pytest --reuse-db
```

**Create fresh database**:
```bash
pytest --create-db
```

## IMPORTANT: Use Fixtures, NOT Factory Imports

**CRITICAL RULE**: Always use fixtures instead of importing factories directly.

### ❌ WRONG - Don't Do This:
```python
from api.users.tests.factories import UserFactory
from api.vendors.tests.factories import VendorFactory

def test_something(api_client):
    admin = UserFactory(role="admin", is_staff=True)
    vendor = VendorFactory()
```

### ✅ CORRECT - Do This:
```python
# No imports needed! Fixtures are auto-available from conftest.py

def test_something(api_client, user_factory, vendor_factory):
    admin = user_factory(role="admin", is_staff=True)
    vendor = vendor_factory()
```

### Why Use Fixtures?

1. **No imports needed** - Factories are registered in conftest.py
2. **Cleaner code** - Less boilerplate
3. **Project convention** - All apps follow this pattern
4. **Better isolation** - pytest-factoryboy manages lifecycle
5. **Auto-available** - Just add fixture name to function parameters

### Available Auto-Generated Fixtures

When a factory is registered in conftest.py (e.g., `register(VendorFactory)`), you automatically get:

- `vendor` - Returns a single created instance
- `vendor_factory` - Returns the factory class for creating custom instances

Examples:
```python
def test_with_default_vendor(api_client, vendor):
    # 'vendor' is automatically created with default values
    assert vendor.status == "approved"

def test_with_custom_vendor(api_client, vendor_factory):
    # Use vendor_factory() to create custom instances
    pending_vendor = vendor_factory(status="pending")
    approved_vendor = vendor_factory(status="approved")

    # Create multiple instances
    vendors = vendor_factory.create_batch(5, status="approved")
```

### Common Fixtures Available

From conftest.py registration:
- `user` / `user_factory` - User instances
- `vendor` / `vendor_factory` - Vendor instances
- `product` / `product_factory` - Product instances
- `category` / `category_factory` - Category instances
- `cart` / `cart_factory` - Cart instances
- `cart_item` / `cart_item_factory` - Cart item instances
- `order` / `order_factory` - Order instances
- `address` / `address_factory` - Address instances
- `api_client` - DRF APIClient for making requests

**Always check api/conftest.py to see all registered factories!**

## Factory Pattern

### Factory Boy Setup
Each app has `tests/factories.py` defining model factories.

### Example Factories (api/users/tests/factories.py:5)
```python
import factory
from factory.django import DjangoModelFactory
from api.users.models import User

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    phonenumber = factory.Sequence(lambda n: f"+233200000{n:03d}")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True
    role = "customer"

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        if extracted:
            obj.set_password(extracted)
        else:
            obj.set_password("testpass123")
        if create:
            obj.save()
```

### Product Factory (api/products/tests/factories.py:5)
```python
class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Faker("word")
    description = factory.Faker("text")
    price = factory.fuzzy.FuzzyDecimal(10.00, 1000.00, 2)
    stock = factory.fuzzy.FuzzyInteger(1, 100)
    status = "active"
    category = factory.SubFactory(CategoryFactory)
```

### Using Factories

**Create single instance**:
```python
user = UserFactory()
product = ProductFactory(price=50.00)
```

**Create batch**:
```python
users = UserFactory.create_batch(5)
products = ProductFactory.create_batch(10, status="active")
```

**Build without saving to DB**:
```python
user = UserFactory.build()  # Not saved
user.email = "custom@example.com"
user.save()
```

**Override defaults**:
```python
admin = UserFactory(role="admin", is_staff=True)
vendor_user = UserFactory(role="vendor_admin", vendor=vendor)
```

### SubFactory for Relationships
```python
class OrderFactory(DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    address = factory.SubFactory(AddressFactory)
```

Creates related objects automatically.

### Faker Providers
Common Faker methods:
- `factory.Faker("first_name")` → Random first name
- `factory.Faker("email")` → Random email
- `factory.Faker("text")` → Random paragraph
- `factory.Faker("word")` → Random word
- `factory.Faker("date")` → Random date

### Fuzzy Attributes
For numeric fields:
- `factory.fuzzy.FuzzyInteger(1, 100)` → Random integer
- `factory.fuzzy.FuzzyDecimal(10.00, 100.00, 2)` → Random decimal with 2 places

### Sequences
For unique values:
```python
email = factory.Sequence(lambda n: f"user{n}@example.com")
# Generates: user1@example.com, user2@example.com, ...
```

## Pytest Fixtures

### Centralized Fixtures (api/conftest.py:5)
```python
from pytest_factoryboy import register
from api.users.tests.factories import UserFactory
from api.products.tests.factories import ProductFactory

# Register factories as fixtures
register(UserFactory)
register(ProductFactory)
register(CategoryFactory)
register(CartFactory)
```

**Auto-generated fixtures**:
- `user` → UserFactory()
- `user_factory` → UserFactory class
- `product` → ProductFactory()
- `product_factory` → ProductFactory class

### Using Auto-Generated Fixtures
```python
@pytest.mark.django_db
def test_product_detail(api_client, product):
    # 'product' fixture automatically created from ProductFactory
    url = reverse("products:product-detail", args=[product.id])
    response = api_client.get(url)
    assert response.status_code == 200
```

### API Client Fixture (api/conftest.py:20)
```python
@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()
```

**Usage**:
```python
def test_endpoint(api_client):
    response = api_client.get("/api/products/")
    assert response.status_code == 200
```

### Authenticated API Client
```python
def test_protected_endpoint(api_client, user):
    api_client.force_authenticate(user=user)
    response = api_client.get("/api/users/me/")
    assert response.status_code == 200
```

### Custom Fixtures
```python
@pytest.fixture
def admin_user():
    return UserFactory(role="admin", is_staff=True)

@pytest.fixture
def vendor_with_products(vendor_factory, product_factory):
    vendor = vendor_factory()
    products = product_factory.create_batch(5, vendor=vendor)
    return vendor, products
```

## Test Structure & Patterns

### Basic Test Example (api/products/tests/test_views.py:10)
```python
import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_product_list(api_client, product_factory):
    # Arrange
    product_factory.create_batch(3)

    # Act
    url = reverse("products:product-list-create")
    response = api_client.get(url)

    # Assert
    assert response.status_code == 200
    assert len(response.data["results"]) >= 3
```

**Structure**: Arrange-Act-Assert pattern for clarity.

### Testing Authentication (api/users/tests/test_views.py:15)
```python
@pytest.mark.django_db
def test_login(api_client, user):
    url = reverse("users:login")
    data = {"email": user.email, "password": "testpass123"}
    response = api_client.post(url, data)

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data
    assert response.data["user"]["email"] == user.email
```

### Testing Permissions (api/products/tests/test_views.py:45)
```python
@pytest.mark.django_db
def test_product_create_requires_auth(api_client):
    url = reverse("products:product-list-create")
    data = {"name": "Test Product", "price": "50.00"}

    # Unauthenticated should fail
    response = api_client.post(url, data)
    assert response.status_code == 403

@pytest.mark.django_db
def test_product_create_vendor_admin(api_client, user, vendor):
    user.role = "vendor_admin"
    user.vendor = vendor
    user.save()
    vendor.status = "approved"
    vendor.save()

    api_client.force_authenticate(user=user)
    url = reverse("products:product-list-create")
    data = {"name": "Test Product", "price": "50.00"}

    response = api_client.post(url, data)
    assert response.status_code in [200, 201]
```

### Testing CRUD Operations (api/products/tests/test_views.py:70)
```python
@pytest.mark.django_db
class TestProductCRUD:
    def test_create(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        url = reverse("products:product-list-create")
        data = {"name": "New Product", "price": "99.99"}
        response = api_client.post(url, data)
        assert response.status_code in [200, 201]

    def test_read(self, api_client, product):
        url = reverse("products:product-detail", args=[product.id])
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data["name"] == product.name

    def test_update(self, api_client, admin_user, product):
        api_client.force_authenticate(user=admin_user)
        url = reverse("products:product-detail", args=[product.id])
        data = {"name": "Updated Name"}
        response = api_client.patch(url, data)
        assert response.status_code == 200

    def test_delete(self, api_client, admin_user, product):
        api_client.force_authenticate(user=admin_user)
        url = reverse("products:product-detail", args=[product.id])
        response = api_client.delete(url)
        assert response.status_code == 204
```

### Testing Filters & Search (api/products/tests/test_views.py:110)
```python
@pytest.mark.django_db
def test_product_filter_by_category(api_client, category, product_factory):
    product_factory.create_batch(3, category=category)
    product_factory.create_batch(2)  # Different category

    url = reverse("products:product-list-create")
    response = api_client.get(url, {"category": category.id})

    assert response.status_code == 200
    assert len(response.data["results"]) == 3

@pytest.mark.django_db
def test_product_search(api_client, product_factory):
    product_factory(name="Red Shirt")
    product_factory(name="Blue Jeans")
    product_factory(name="Red Hat")

    url = reverse("products:product-list-create")
    response = api_client.get(url, {"search": "red"})

    assert response.status_code == 200
    assert len(response.data["results"]) == 2
```

### Testing Validation (api/products/tests/test_views.py:135)
```python
@pytest.mark.django_db
def test_product_create_validation(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    url = reverse("products:product-list-create")

    # Missing required fields
    response = api_client.post(url, {})
    assert response.status_code == 400
    assert "name" in response.data or "price" in response.data

    # Invalid price
    response = api_client.post(url, {"name": "Test", "price": "-10"})
    assert response.status_code == 400
```

### Testing Business Logic (api/orders/tests/test_views.py:50)
```python
@pytest.mark.django_db
def test_checkout_reduces_stock(api_client, user, cart, cart_item):
    initial_stock = cart_item.product.stock

    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    data = {"address": address.id}
    response = api_client.post(url, data)

    assert response.status_code in [200, 201]

    cart_item.product.refresh_from_db()
    assert cart_item.product.stock == initial_stock - cart_item.quantity
```

## Common Test Scenarios

### Scenario 1: List Endpoint
```python
@pytest.mark.django_db
def test_list_endpoint(api_client, product_factory):
    products = product_factory.create_batch(5)
    url = reverse("products:product-list-create")
    response = api_client.get(url)

    assert response.status_code == 200
    assert "results" in response.data  # Paginated response
    assert len(response.data["results"]) == 5
```

### Scenario 2: Detail Endpoint
```python
@pytest.mark.django_db
def test_detail_endpoint(api_client, product):
    url = reverse("products:product-detail", args=[product.id])
    response = api_client.get(url)

    assert response.status_code == 200
    assert response.data["id"] == str(product.id)
    assert response.data["name"] == product.name
```

### Scenario 3: Create with Relations
```python
@pytest.mark.django_db
def test_create_with_category(api_client, admin_user, category):
    api_client.force_authenticate(user=admin_user)
    url = reverse("products:product-list-create")
    data = {
        "name": "Test Product",
        "price": "50.00",
        "category": str(category.id)  # UUID as string
    }
    response = api_client.post(url, data)

    assert response.status_code in [200, 201]
    assert response.data["category"] == str(category.id)
```

### Scenario 4: Role-Based Access
```python
@pytest.mark.django_db
def test_vendor_sees_own_products(api_client, vendor_factory, product_factory):
    vendor1 = vendor_factory()
    vendor2 = vendor_factory()
    user1 = UserFactory(role="vendor_admin", vendor=vendor1)

    product_factory.create_batch(3, vendor=vendor1)
    product_factory.create_batch(2, vendor=vendor2)

    api_client.force_authenticate(user=user1)
    url = reverse("products:product-list-create")
    response = api_client.get(url)

    assert response.status_code == 200
    assert len(response.data["results"]) == 3  # Only vendor1's products
```

### Scenario 5: Error Handling
```python
@pytest.mark.django_db
def test_not_found(api_client):
    url = reverse("products:product-detail", args=["00000000-0000-0000-0000-000000000000"])
    response = api_client.get(url)
    assert response.status_code == 404

@pytest.mark.django_db
def test_unauthorized(api_client):
    url = reverse("users:me")
    response = api_client.get(url)
    assert response.status_code == 401

@pytest.mark.django_db
def test_forbidden(api_client, user):
    api_client.force_authenticate(user=user)
    url = reverse("products:bulk-upload")
    response = api_client.post(url, {})
    assert response.status_code == 403
```

## Test Data Best Practices

1. **Use factories for all test data**: Never manually create model instances
2. **Keep tests isolated**: Each test should create its own data
3. **Use descriptive names**: `test_admin_can_approve_vendor` better than `test_approve`
4. **Test edge cases**: Empty lists, null values, invalid inputs
5. **Test permissions thoroughly**: Unauthenticated, wrong role, correct role
6. **Use fixtures for repeated setup**: Create custom fixtures for common scenarios
7. **Assert specific values**: Check actual data, not just status codes
8. **Test business rules**: Stock reduction, price calculations, status transitions
9. **Use parametrize for similar tests**:
```python
@pytest.mark.parametrize("role,expected", [
    ("customer", 403),
    ("vendor_admin", 403),
    ("admin", 200),
])
def test_bulk_upload_permissions(api_client, user, role, expected):
    user.role = role
    user.save()
    api_client.force_authenticate(user=user)
    response = api_client.post("/api/products/bulk-upload/", {})
    assert response.status_code == expected
```

10. **Use transactions for complex scenarios**:
```python
@pytest.mark.django_db
def test_checkout_atomicity(api_client, user, cart_with_items):
    # Simulate failure mid-checkout
    with pytest.raises(Exception):
        # Checkout logic that fails
        pass
    # Verify rollback - cart still has items
    assert cart_with_items.items.count() > 0
```

## Coverage & Quality

### Check Test Coverage
```bash
pytest --cov=api --cov-report=html
open htmlcov/index.html
```

**Target**: Aim for 80%+ coverage on business logic, 100% on critical paths.

### Running Specific Test Types
```bash
# Only fast tests (no external calls)
pytest -m "not slow"

# Only integration tests
pytest -m integration

# Mark tests with decorators
@pytest.mark.slow
@pytest.mark.integration
```

### Continuous Integration
Add to CI pipeline:
```bash
pytest --cov=api --cov-fail-under=80
```

Fails if coverage drops below 80%.
