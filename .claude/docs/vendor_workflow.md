# Vendor Workflow & Management

## Vendor Overview

The vendor system enables multi-vendor marketplace functionality where multiple independent sellers can:
- Create vendor profiles and await admin approval
- Manage their own product catalogs
- Process orders for their products
- Access vendor-specific analytics and reports

## Vendor Model Structure (api/vendors/models.py:8)

```python
class Vendor(BaseModel):
    name = CharField(max_length=255, unique=True)
    slug = SlugField(unique=True, blank=True)
    description = TextField(blank=True)
    email = EmailField(unique=True)
    phone = CharField(max_length=20)
    address = TextField(blank=True)
    logo = ImageField(upload_to="vendor_logos/", blank=True, null=True)
    banner = ImageField(upload_to="vendor_banners/", blank=True, null=True)
    website = URLField(blank=True)
    status = CharField(choices=Status.choices, default=Status.PENDING)

    # Business details
    business_license = CharField(max_length=255, blank=True)
    tax_id = CharField(max_length=255, blank=True)

    # Settings
    is_active = BooleanField(default=True)
    is_deleted = BooleanField(default=False)
```

### Vendor Status Options
- **pending**: Initial state after signup, awaiting admin review
- **approved**: Admin approved, can create products and process orders
- **rejected**: Admin rejected application
- **suspended**: Admin suspended vendor (temporary or permanent ban)

## Vendor Registration Workflow

### Step 1: User Registration
User must first create account with `vendor_admin` role:

```
POST /api/users/register/
Body: {
    "email": "vendor@example.com",
    "password": "securepass123",
    "first_name": "John",
    "last_name": "Doe",
    "phonenumber": "+233200000000",
    "role": "vendor_admin"
}
```

### Step 2: Vendor Signup (api/vendors/views.py:15)
Create vendor profile linked to user:

```
POST /api/vendors/signup/
Headers: Authorization: Bearer {access_token}
Body: {
    "name": "My Store",
    "email": "store@example.com",
    "phone": "+233200000001",
    "description": "We sell quality products",
    "address": "123 Main St, Accra",
    "website": "https://mystore.com",
    "business_license": "BL12345",
    "tax_id": "TAX67890"
}
Response: 201 Created with vendor data (status="pending")
```

**Important**:
- `name` and `email` must be unique across all vendors
- `slug` auto-generated from name if not provided
- User is automatically associated via `request.user`
- Vendor created with `status="pending"` by default

### Step 3: Admin Review & Approval
Admin reviews vendor application and approves:

```
PATCH /api/vendors/{vendor_id}/approve/
Headers: Authorization: Bearer {admin_access_token}
Response: 200, vendor.status = "approved"
```

Or rejects:

```
PATCH /api/vendors/{vendor_id}/reject/
Headers: Authorization: Bearer {admin_access_token}
Response: 200, vendor.status = "rejected"
```

### Step 4: Vendor Can Now Operate
Once approved, vendor can:
- Create/edit products
- View vendor-specific orders
- Update vendor profile

## Vendor User Relationship (api/users/models.py:52)

```python
class User(AbstractBaseUser):
    ...
    vendor = ForeignKey(
        "vendors.Vendor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users"
    )
```

**Key Points**:
- One-to-many: One vendor can have multiple users (future: team members)
- Currently: One user per vendor (vendor admin)
- Link established during vendor signup (api/vendors/views.py:35)
- Used for filtering products/orders by vendor

## Vendor Permissions

### IsVendorAdmin (api/common/permissions.py:25)
Checks if user has `role="vendor_admin"`:
```python
return request.user.is_authenticated and request.user.role == "vendor_admin"
```

### IsApprovedVendorAdmin (api/common/permissions.py:35)
Checks if user is vendor admin AND vendor is approved:
```python
vendor = getattr(request.user, "vendor", None)
return vendor and vendor.status == "approved"
```

**Usage in Views**:
```python
class ProductCreateView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated, IsApprovedVendorAdmin]
```

Only approved vendors can create products.

## Vendor-Specific Data Access

### Products Filtered by Vendor (api/products/views.py:25)
```python
def get_queryset(self):
    user = self.request.user

    # Admins see all products
    if user.is_staff or user.role in ["admin", "manager"]:
        return Product.objects.all()

    # Vendor admins see only their products
    if user.role == "vendor_admin":
        vendor = getattr(user, "vendor", None)
        if vendor:
            return Product.objects.filter(vendor=vendor)
        return Product.objects.none()

    # Customers see active products
    return Product.objects.filter(is_deleted=False, status="active")
```

### Orders Filtered by Vendor (api/orders/views.py:45)
```python
def get_queryset(self):
    user = self.request.user

    # Admins see all orders
    if user.is_staff or user.role in ["admin", "manager"]:
        return Order.objects.all()

    # Vendor admins see orders containing their products
    if user.role == "vendor_admin":
        vendor = getattr(user, "vendor", None)
        if vendor:
            return Order.objects.filter(vendor=vendor)
        return Order.objects.none()

    # Customers see own orders
    return Order.objects.filter(user=user)
```

## Vendor Management Endpoints

### List All Vendors
```
GET /api/vendors/
Query Params: ?status=approved, ?search=store_name
Response: Paginated list of vendors
```

Accessible to all users (public vendor directory).

### Get Vendor Detail
```
GET /api/vendors/{vendor_id}/
Response: Full vendor details including products
```

### Get Own Vendor Profile
```
GET /api/vendors/me/
Headers: Authorization: Bearer {vendor_access_token}
Response: Current user's vendor profile
```

### Update Vendor Profile (api/vendors/views.py:55)
```
PATCH /api/vendors/{vendor_id}/
Headers: Authorization: Bearer {vendor_access_token}
Body: {
    "description": "Updated description",
    "phone": "+233200000002",
    "website": "https://newurl.com"
}
Response: 200 with updated vendor data
```

Only vendor owner or admin can update.

### Approve Vendor (api/vendors/views.py:80)
```
PATCH /api/vendors/{vendor_id}/approve/
Headers: Authorization: Bearer {admin_access_token}
Response: 200, sets status="approved"
```

**Permission**: IsAdminOrManager only.

### Reject Vendor (api/vendors/views.py:95)
```
PATCH /api/vendors/{vendor_id}/reject/
Headers: Authorization: Bearer {admin_access_token}
Response: 200, sets status="rejected"
```

**Permission**: IsAdminOrManager only.

### Suspend Vendor (api/vendors/views.py:110)
```
PATCH /api/vendors/{vendor_id}/suspend/
Headers: Authorization: Bearer {admin_access_token}
Response: 200, sets status="suspended"
```

**Permission**: IsAdminOrManager only.
Suspended vendors cannot create products or process orders.

## Vendor Product Management

### Creating Products as Vendor (api/products/views.py:80)
```
POST /api/products/
Headers: Authorization: Bearer {vendor_access_token}
Body: {
    "name": "Product Name",
    "price": "99.99",
    "stock": 50,
    "description": "Product description",
    "category": "category_uuid"
}
Response: 201 Created
```

**Automatic Vendor Assignment**:
Product automatically assigned to `request.user.vendor` (api/products/serializers.py:45):
```python
def create(self, validated_data):
    user = self.context["request"].user
    if user.role == "vendor_admin" and hasattr(user, "vendor"):
        validated_data["vendor"] = user.vendor
    return super().create(validated_data)
```

### Listing Vendor Products
```
GET /api/products/
Headers: Authorization: Bearer {vendor_access_token}
Response: Only products belonging to vendor's store
```

### Updating Vendor Products
```
PATCH /api/products/{product_id}/
Headers: Authorization: Bearer {vendor_access_token}
Body: {"price": "79.99"}
Response: 200 if product belongs to vendor, 404 otherwise
```

## Multi-Vendor Order Processing

### Order Splitting by Vendor (api/orders/views.py:120)
During checkout, cart items are grouped by vendor and separate orders created:

```python
from collections import defaultdict

# Group cart items by vendor
items_by_vendor = defaultdict(list)
for item in cart_items:
    vendor = item.product.vendor
    items_by_vendor[vendor].append(item)

# Create separate order for each vendor
orders = []
for vendor, items in items_by_vendor.items():
    order = Order.objects.create(
        user=user,
        vendor=vendor,
        total=calculate_total(items),
        ...
    )
    for item in items:
        OrderItem.objects.create(order=order, ...)
    orders.append(order)
```

**Result**: Customer makes one checkout, but multiple orders created (one per vendor).

### Vendor Order View (api/orders/views.py:180)
```
GET /api/orders/vendor-orders/
Headers: Authorization: Bearer {vendor_access_token}
Response: All orders containing vendor's products
```

**Permission**: IsVendorAdmin only.

### Order Status Updates
Vendor can update order status for their orders:

```
PATCH /api/orders/{order_id}/
Headers: Authorization: Bearer {vendor_access_token}
Body: {"status": "shipped"}
Response: 200 if order belongs to vendor
```

Status progression: pending → paid → shipped → delivered

## Vendor Analytics & Reporting

### Vendor Dashboard Data
Custom endpoint for vendor analytics (implement as needed):

```python
class VendorDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendorAdmin]

    def get(self, request):
        vendor = request.user.vendor

        # Total products
        total_products = Product.objects.filter(vendor=vendor).count()

        # Total orders
        total_orders = Order.objects.filter(vendor=vendor).count()

        # Total revenue
        total_revenue = Order.objects.filter(
            vendor=vendor,
            status__in=["paid", "shipped", "delivered"]
        ).aggregate(Sum("total"))["total__sum"] or 0

        # Recent orders
        recent_orders = Order.objects.filter(vendor=vendor).order_by("-created_at")[:5]

        return Response({
            "total_products": total_products,
            "total_orders": total_orders,
            "total_revenue": str(total_revenue),
            "recent_orders": OrderSerializer(recent_orders, many=True).data
        })
```

## Vendor Settings & Configuration

### Optional Vendor Fields (api/vendors/models.py:35)
- Commission rate (if marketplace takes percentage)
- Payment information (bank account, mobile money)
- Shipping methods supported
- Return policy
- Business hours

### Future Enhancements
1. **Multi-user vendor teams**: Add vendor staff members
2. **Vendor subscriptions**: Premium features for paid vendors
3. **Commission management**: Automatic commission calculation
4. **Payout tracking**: Track payments to vendors
5. **Vendor ratings**: Customer reviews for vendors
6. **Vendor analytics dashboard**: Sales charts, top products
7. **Vendor notifications**: Email/SMS for new orders
8. **Custom vendor domains**: subdomain.grottomore.com

## Testing Vendor Workflows

### Factory for Vendors (api/vendors/tests/factories.py:5)
```python
class VendorFactory(DjangoModelFactory):
    class Meta:
        model = Vendor

    name = factory.Faker("company")
    email = factory.Faker("company_email")
    phone = factory.Faker("phone_number")
    status = "approved"
```

### Test Vendor Signup
```python
@pytest.mark.django_db
def test_vendor_signup(api_client, user):
    user.role = "vendor_admin"
    user.save()

    api_client.force_authenticate(user=user)
    url = reverse("vendors:vendor-signup")
    data = {
        "name": "My Store",
        "email": "store@example.com",
        "phone": "+233200000000"
    }
    response = api_client.post(url, data)

    assert response.status_code == 201
    assert response.data["status"] == "pending"
    assert Vendor.objects.filter(name="My Store").exists()
```

### Test Vendor Product Filtering
```python
@pytest.mark.django_db
def test_vendor_sees_own_products(api_client, vendor_factory, product_factory):
    vendor1 = vendor_factory()
    vendor2 = vendor_factory()
    user = UserFactory(role="vendor_admin", vendor=vendor1)

    product_factory.create_batch(3, vendor=vendor1)
    product_factory.create_batch(2, vendor=vendor2)

    api_client.force_authenticate(user=user)
    url = reverse("products:product-list-create")
    response = api_client.get(url)

    assert response.status_code == 200
    assert len(response.data["results"]) == 3
```

## Common Vendor Scenarios

### Scenario 1: New Vendor Onboarding
1. User registers with role="vendor_admin"
2. User creates vendor profile (status="pending")
3. User waits for admin approval
4. Admin reviews and approves vendor
5. Vendor can now create products

### Scenario 2: Vendor Creates Product
1. Vendor logs in (has approved vendor account)
2. POST /api/products/ with product details
3. Product automatically assigned to vendor
4. Product visible to customers (if status="active")

### Scenario 3: Customer Orders from Multiple Vendors
1. Customer adds products from vendor A and vendor B to cart
2. Customer proceeds to checkout
3. System creates separate orders for each vendor
4. Each vendor sees only their order
5. Each vendor ships independently

### Scenario 4: Vendor Suspension
1. Admin suspects policy violation
2. Admin suspends vendor (status="suspended")
3. Vendor cannot create new products
4. Vendor's existing products hidden from customers
5. Vendor's orders remain accessible for fulfillment
6. Admin can later reactivate by setting status="approved"

## Admin Vendor Management

### Viewing All Vendors
```
GET /api/vendors/
Headers: Authorization: Bearer {admin_access_token}
Query: ?status=pending  # Filter by status
Response: All vendors (including pending/rejected/suspended)
```

### Bulk Vendor Actions
For bulk operations, create custom admin actions or management commands:

```python
# management/commands/approve_vendors.py
class Command(BaseCommand):
    def handle(self, *args, **options):
        pending = Vendor.objects.filter(status="pending")
        for vendor in pending:
            # Review logic
            vendor.status = "approved"
            vendor.save()
            # Send approval email
```

### Vendor Metrics Dashboard
Track key vendor metrics:
- Total vendors by status
- Approval rate
- Average products per vendor
- Top vendors by sales
- Suspended vendors requiring review

## Security Considerations

1. **Always verify vendor ownership**: Check `request.user.vendor == resource.vendor`
2. **Validate vendor status**: Only approved vendors can perform actions
3. **Prevent vendor data leaks**: Filter querysets by vendor
4. **Audit vendor actions**: Log product creation, order updates
5. **Rate limit vendor endpoints**: Prevent abuse of product creation
6. **Validate business documents**: Verify business license, tax ID
7. **Monitor suspended vendors**: Prevent circumvention via new accounts
