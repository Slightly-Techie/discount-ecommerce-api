# Architectural Patterns & Design Decisions

## Model Layer Patterns

### BaseModel Inheritance
All domain models extend BaseModel for consistent audit trail:
- UUID primary keys (api/common/models.py:6)
- created_at/updated_at timestamps
- Never use auto-incrementing integers for public-facing IDs

### QuerySet & Manager Pattern
Custom querysets provide reusable filters (api/users/models.py:10):
```python
class UserQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)

UserManager.get_queryset().active()  # Usage
```

Apply to new models when you need common filtering logic.

### Soft Delete Pattern
Models use is_deleted boolean instead of hard deletes:
- Set is_deleted=True instead of calling .delete()
- Filter querysets: .filter(is_deleted=False) for user-facing queries
- Admin/staff see all records (check in get_queryset)
- Examples: api/products/models.py:45, api/users/models.py:42

### Choice Fields with TextChoices
Use Django's TextChoices for status/role enums:
- User.Role: customer, seller, vendor_admin, manager, admin (api/users/models.py:15)
- Product.Status: active, out_of_stock, draft, archived (api/products/models.py:28)
- Vendor.Status: pending, approved, rejected, suspended (api/vendors/models.py:12)
- Order.Status: pending, paid, shipped, delivered, cancelled (api/orders/models.py:78)

Provides type safety, autocompletion, and cleaner code vs string literals.

### Self-Referential Relationships
- Category.parent for hierarchical categories (api/category/models.py:12)
- Product.related_products M2M to self (api/products/models.py:63)

Use null=True, blank=True for optional parent relationships.

### Lazy Slug Generation
Auto-generate slugs from names in save() if not provided:
```python
def save(self, *args, **kwargs):
    if not self.slug:
        self.slug = slugify(self.name)
    super().save(*args, **kwargs)
```
See api/category/models.py:25, api/products/models.py:85

## View Layer Patterns

### Generic View Classes
Use DRF generic views for standard CRUD operations:
- ListCreateAPIView: GET list + POST create (api/products/views.py:20)
- RetrieveUpdateDestroyAPIView: GET/PUT/PATCH/DELETE detail (api/products/views.py:55)
- RetrieveUpdateAPIView: Profile endpoints without delete (api/users/views.py:78)
- CreateAPIView: Registration/signup only (api/users/views.py:15)

### Conditional Permission Classes
Override get_permissions() for method-specific permissions (api/products/views.py:30):
```python
def get_permissions(self):
    if self.request.method in ["PUT", "PATCH", "DELETE"]:
        return [IsAuthenticated(), IsAdminOrManager()]
    return [AllowAny()]
```

Or set per-view: permission_classes = [IsAuthenticated]

### Role-Based Queryset Filtering
Filter querysets by user role in get_queryset() (api/products/views.py:25):
```python
def get_queryset(self):
    user = self.request.user
    if user.is_staff or getattr(user, "role", None) == "admin":
        return Product.objects.all()  # Admins see all
    if getattr(user, "role", None) == "vendor_admin":
        return Product.objects.filter(vendor=user.vendor)  # Vendor sees own
    return Product.objects.filter(is_deleted=False)  # Customers see active only
```

### Conditional Serializer Classes
Use different serializers for create vs read operations (api/products/views.py:42):
```python
def get_serializer_class(self):
    if self.request.method == "POST":
        return ProductCreateSerializer  # Simplified input
    return ProductReadSerializer  # Full nested details
```

### Query Optimization
Always optimize queries with select_related/prefetch_related (api/orders/views.py:35):
```python
def get_queryset(self):
    return Order.objects.select_related("user", "address", "coupon").prefetch_related("items__product")
```

### Transaction Management
Wrap multi-step operations in atomic transactions (api/orders/views.py:120):
```python
with transaction.atomic():
    order = Order.objects.create(...)
    for item in cart_items:
        OrderItem.objects.create(order=order, ...)
        item.product.stock -= item.quantity
        item.product.save()
    cart.clear()
```

### Swagger Schema Workaround
Prevent schema generation errors with AnonymousUser (api/cart/views.py:18):
```python
def get_queryset(self):
    if getattr(self, "swagger_fake_view", False):
        return Cart.objects.none()
    return Cart.objects.filter(user=self.request.user)
```

## Serializer Layer Patterns

### Read-Only Fields
Mark audit fields as read-only in Meta.read_only_fields:
```python
class Meta:
    model = Product
    fields = ["id", "name", "price", "created_at", "updated_at"]
    read_only_fields = ["id", "created_at", "updated_at"]
```

### Nested Serializers (Read-Only)
Use nested serializers for GET responses (api/orders/serializers.py:45):
```python
items = OrderItemSerializer(many=True, read_only=True)
address = AddressSerializer(read_only=True)
```
Never use nested serializers for write operations (POST/PUT/PATCH).

### SerializerMethodField
Add computed fields with get_{field_name} methods (api/products/serializers.py:68):
```python
vendor = serializers.SerializerMethodField()

def get_vendor(self, obj):
    if not obj.vendor_id:
        return None
    v = obj.vendor
    return {"id": str(v.id), "name": v.name, "status": v.status}
```

### PrimaryKeyRelatedField for Relationships
Use PK fields for write operations (api/products/serializers.py:28):
```python
category = serializers.PrimaryKeyRelatedField(
    queryset=Category.objects.all(),
    required=False,
    allow_null=True
)
```

Client sends UUID, serializer validates and assigns related object.

### Write-Only Fields
Mark sensitive fields as write_only (api/users/serializers.py:22):
```python
password = serializers.CharField(
    write_only=True,
    required=True,
    validators=[validate_password]
)
```

### Custom Validation
Add field-level or object-level validation (api/vendors/serializers.py:35):
```python
def validate_vendor_name(self, value):
    if Vendor.objects.filter(name__iexact=value.strip()).exists():
        raise serializers.ValidationError("Vendor name already exists.")
    return value.strip()

def validate(self, attrs):
    # Cross-field validation
    if attrs.get("start_date") > attrs.get("end_date"):
        raise serializers.ValidationError("Start date must be before end date.")
    return attrs
```

## Authentication & Permissions

### JWT Token Flow
1. POST /api/auth/token/ with email/password → access + refresh tokens
2. Include access token in header: Authorization: Bearer {access_token}
3. When access expires, POST /api/auth/token/refresh/ with refresh token
4. Custom serializer returns user data with tokens (api/users/views.py:45)

### Custom Permission Classes
Located in api/common/permissions.py:
- **IsAdminOrManager**: role in ["admin", "manager"] or is_staff/is_superuser
- **IsVendorAdmin**: role == "vendor_admin"
- **IsApprovedVendorAdmin**: vendor_admin with vendor.status == "approved"
- **IsAdminManagerOrApprovedVendorAdmin**: Combined check

Usage: permission_classes = [IsAuthenticated, IsAdminOrManager]

### Role-Based Access Hierarchy
1. **admin/is_superuser**: Full access to everything
2. **manager**: Admin-level access (approve vendors, bulk upload)
3. **vendor_admin**: Access only to own vendor's products/orders
4. **seller**: Create products (future use)
5. **customer**: Browse products, manage cart/orders

Check role in views: getattr(request.user, "role", None) == "admin"

## URL & Routing Patterns

### App Namespace Pattern
Each app defines app_name for URL namespacing (api/products/urls.py:3):
```python
app_name = "products"
urlpatterns = [
    path("", ProductListView.as_view(), name="product-list-create"),
    path("<uuid:pk>/", ProductDetailView.as_view(), name="product-detail"),
]
```

Reverse URLs: reverse("products:product-detail", args=[product_id])

### UUID-Based Lookups
Use <uuid:pk> for primary key lookups (never expose auto-increment IDs):
```python
path("<uuid:pk>/", ProductDetailView.as_view(), name="product-detail")
```

### Top-Level Routes for Cross-Cutting Concerns
Place non-CRUD endpoints at root level:
- /api/products/bulk-upload/
- /api/products/fetch-discounted/
- /api/vendors/me/
- /api/orders/checkout/

## Testing Patterns

### Factory Pattern
Define factories in app/tests/factories.py (api/products/tests/factories.py:5):
```python
class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Faker("word")
    price = factory.fuzzy.FuzzyDecimal(10.00, 100.00)
    stock = factory.fuzzy.FuzzyInteger(1, 100)
```

Usage: ProductFactory.create(), ProductFactory.create_batch(5)

### Centralized Fixtures
Register factories in api/conftest.py for automatic fixture creation (api/conftest.py:10):
```python
register(UserFactory)
register(ProductFactory)
```

Now use as pytest fixtures: def test_product(product, api_client):

### Authentication in Tests
Force authenticate for protected endpoints (api/products/tests/test_views.py:25):
```python
api_client.force_authenticate(user=user)
response = api_client.get(url)
```

### Test Structure
- Use @pytest.mark.django_db for database access
- Use reverse() for URL generation
- Create test data with factories
- Assert status codes and response data structure

## Common Utilities

### Shipping Calculation
Dynamic calculation based on country/zone (api/common/utils.py:43):
- Looks up country → shipping zone → active shipping method
- Free shipping if subtotal > free_over threshold
- Returns Decimal or None if delivery unavailable

### Tax Calculation
Dynamic tax rates by country/zone (api/common/utils.py:75):
- Looks up country → tax zone → latest tax rate
- Returns Decimal (subtotal * rate)

### OTP Generation/Verification
Use pyotp for email/phone verification (api/common/utils.py:15):
- generate_otp(secret, interval=300) → 6-digit code
- verify_otp(otp, secret, interval=300) → bool
- Store secret per user, regenerate for each request

### State Machine Pattern
Order status transitions with validation (api/orders/models.py:125):
```python
TRANSITIONS = {
    "pending": ["paid", "cancelled"],
    "paid": ["shipped", "cancelled"],
    "shipped": ["delivered"],
    "delivered": [],
}

def can_transition(self, new_status):
    return new_status in TRANSITIONS[self.status]
```

Enforce valid state changes in views/serializers.

## Django Admin Customization

### List Display & Filters
Customize admin views (api/products/admin.py:5):
```python
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "price", "stock", "status", "created_at"]
    list_filter = ["status", "category", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at", "updated_at"]
```

### Inline Related Objects
Display related objects inline (api/orders/admin.py:18):
```python
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "quantity", "price"]

class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
```

## Conventions & Best Practices

1. **Model Methods**: Put business logic in models, not views (calculate_discount, is_valid_for_user)
2. **Manager Methods**: Reusable queries go in custom managers (active(), by_vendor())
3. **Serializer Separation**: Separate create/update serializers from read serializers for clarity
4. **Permission Checks**: Always check permissions in views, never trust client input
5. **Atomic Operations**: Wrap multi-model changes in transaction.atomic()
6. **Query Optimization**: Profile queries, add select_related/prefetch_related as needed
7. **Validation**: Validate at serializer level, business rules at model level
8. **Error Handling**: Return proper HTTP status codes (400 for validation, 403 for permissions, 404 for not found)
9. **UUID Primary Keys**: Never expose auto-increment IDs in APIs
10. **Soft Deletes**: Prefer is_deleted flag over hard deletes for audit trail
