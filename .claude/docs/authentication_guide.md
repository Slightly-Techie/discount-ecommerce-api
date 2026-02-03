# Authentication & Authorization Guide

## JWT Authentication Setup

### Token Endpoints
Base URL: `/api/auth/`

**Obtain Token Pair** (api/users/urls.py:12):
```
POST /api/auth/token/
Body: {"email": "user@example.com", "password": "password123"}
Response: {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "user": {
        "id": "uuid",
        "email": "user@example.com",
        "role": "customer",
        ...
    }
}
```

**Refresh Access Token** (api/users/urls.py:13):
```
POST /api/auth/token/refresh/
Body: {"refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."}
Response: {"access": "new_access_token"}
```

**Verify Token** (api/users/urls.py:14):
```
POST /api/auth/token/verify/
Body: {"token": "eyJ0eXAiOiJKV1QiLCJhbGc..."}
Response: 200 if valid, 401 if invalid/expired
```

### Custom Token Serializer
Custom serializer includes user data in token response (api/users/views.py:45):
```python
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user_data = UserSerializer(self.user).data
        data["user"] = user_data
        return data
```

Benefit: Client gets user profile immediately without extra request.

### Using Tokens in Requests
Include access token in Authorization header:
```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

DRF automatically validates token via JWTAuthentication backend (core/settings.py:169).

### Token Expiration
- Access token: Short-lived (typically 5-15 minutes)
- Refresh token: Long-lived (typically 1-7 days)
- When access expires, use refresh endpoint to get new access token
- When refresh expires, user must re-login

## User Registration & Login

### Registration Flow (api/users/views.py:15)
```
POST /api/users/register/
Body: {
    "email": "user@example.com",
    "password": "securepass123",
    "first_name": "John",
    "last_name": "Doe",
    "phonenumber": "+233200000000",
    "role": "customer"  # Optional, defaults to customer
}
Response: 201 Created with user data
```

Registration creates user but doesn't return tokens. User must login after registration.

### Login Flow (api/users/views.py:30)
```
POST /api/users/login/
Body: {"email": "user@example.com", "password": "password123"}
Response: {
    "user": {...},
    "access": "access_token",
    "refresh": "refresh_token"
}
```

LoginView wraps token creation and returns user data with tokens.

### Email Verification (api/users/views.py:95)
```
POST /api/users/verify-email/
Body: {"email": "user@example.com", "otp": "123456"}
Response: 200 if valid, sets user.email_verified=True
```

Send OTP via email before verification (implement send_email in utils).

### Phone Verification (api/users/views.py:110, 125)
```
POST /api/users/verify-phone/request/
Body: {"phonenumber": "+233200000000"}
Response: OTP sent via SMS (implementation needed)

POST /api/users/verify-phone/confirm/
Body: {"phonenumber": "+233200000000", "otp": "123456"}
Response: 200 if valid, sets user.phone_verified=True
```

## User Roles & Permissions

### Role Hierarchy (api/users/models.py:15)
```python
class Role(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    SELLER = "seller", "Seller"
    VENDOR_ADMIN = "vendor_admin", "Vendor Admin"
    MANAGER = "manager", "Manager"
    ADMIN = "admin", "Admin"
```

**Access Levels**:
1. **admin**: Full system access, can approve vendors, bulk upload, manage all data
2. **manager**: Similar to admin, administrative operations
3. **vendor_admin**: Access only to own vendor's products/orders, cannot see other vendors
4. **seller**: Can create products (future use, currently similar to customer)
5. **customer**: Browse products, manage own cart/orders

### Django Staff Status
- is_staff: Access to Django admin panel
- is_superuser: Full Django admin permissions
- Both can be combined with role field for fine-grained control

### Setting User Role
Role is set during registration or by admin:
```python
user = User.objects.create_user(email=..., role="customer")
# Or update existing user
user.role = "vendor_admin"
user.save()
```

## Custom Permission Classes

Located in api/common/permissions.py:

### IsAdminOrManager (api/common/permissions.py:10)
```python
class IsAdminOrManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and (
                request.user.is_superuser
                or request.user.is_staff
                or getattr(request.user, "role", None) in ["admin", "manager"]
            )
        )
```

**Usage**: Restrict endpoints to admins/managers only.
```python
class ProductBulkUploadView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrManager]
```

### IsVendorAdmin (api/common/permissions.py:25)
```python
class IsVendorAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", None) == "vendor_admin"
        )
```

**Usage**: Restrict to vendor admin users.

### IsApprovedVendorAdmin (api/common/permissions.py:35)
```python
class IsApprovedVendorAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if getattr(request.user, "role", None) != "vendor_admin":
            return False
        vendor = getattr(request.user, "vendor", None)
        return vendor and vendor.status == "approved"
```

**Usage**: Restrict to vendor admins with approved vendor status.
Example: Only approved vendors can create products.

### IsAdminManagerOrApprovedVendorAdmin (api/common/permissions.py:50)
Combines admin/manager check with approved vendor check.

**Usage**: Endpoints accessible to both admins and approved vendors.
```python
class ProductCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminManagerOrApprovedVendorAdmin]
```

## Role-Based View Logic

### Filtering Querysets by Role (api/products/views.py:25)
```python
def get_queryset(self):
    user = self.request.user

    # Admins/managers see all products
    if user.is_authenticated and (user.is_staff or getattr(user, "role", None) in ["admin", "manager"]):
        return Product.objects.all()

    # Vendor admins see only their products
    if user.is_authenticated and getattr(user, "role", None) == "vendor_admin":
        vendor = getattr(user, "vendor", None)
        if vendor:
            return Product.objects.filter(vendor=vendor)
        return Product.objects.none()

    # Customers see only active products
    return Product.objects.filter(is_deleted=False, status="active")
```

Apply this pattern in all list views to enforce data access control.

### Conditional Permissions (api/products/views.py:30)
```python
def get_permissions(self):
    if self.request.method == "GET":
        return [AllowAny()]
    if self.request.method == "POST":
        return [IsAuthenticated(), IsAdminManagerOrApprovedVendorAdmin()]
    if self.request.method in ["PUT", "PATCH", "DELETE"]:
        return [IsAuthenticated(), IsAdminOrManager()]
    return [IsAuthenticated()]
```

Allows different permissions per HTTP method.

## Vendor-Specific Authentication

### Vendor Admin Setup
1. User registers with role="vendor_admin" or admin assigns role
2. User creates vendor profile via POST /api/vendors/signup/
3. Admin approves vendor via PATCH /api/vendors/{id}/approve/
4. User.vendor foreign key links user to vendor (api/users/models.py:52)

### Checking Vendor Association
```python
user = request.user
if hasattr(user, "vendor") and user.vendor:
    vendor = user.vendor
    # Filter products/orders by vendor
    products = Product.objects.filter(vendor=vendor)
```

### Vendor Approval Workflow
- Vendor signup creates vendor with status="pending"
- Admin reviews and approves: vendor.status = "approved"
- Only approved vendors can create products (IsApprovedVendorAdmin permission)

## Password Management

### Change Password (api/users/views.py:55)
```
POST /api/users/change-password/
Headers: Authorization: Bearer {access_token}
Body: {
    "old_password": "oldpass123",
    "new_password": "newpass456"
}
Response: 200 if successful
```

Requires authentication. Validates old password before updating.

### Password Reset (api/users/views.py:70)
```
POST /api/users/password-reset/
Body: {"email": "user@example.com"}
Response: 200, sends reset email (implementation needed)
```

No authentication required. Sends email with reset token/link.

## Email & Phone Verification

### OTP Generation (api/common/utils.py:15)
```python
from api.common.utils import generate_otp, verify_otp

# Generate OTP for user
secret = user.email  # Or any unique identifier
otp = generate_otp(secret, interval=300)  # Valid for 5 minutes

# Send OTP via email/SMS
send_email(subject="OTP", message=otp, recipient_list=[user.email])

# Verify OTP
is_valid = verify_otp(otp_input, secret, interval=300)
```

**Important**: Store OTP secret per user, regenerate for each verification request.

### Email Verification Flow
1. User registers
2. System generates OTP with user.email as secret
3. Send OTP to user's email
4. User submits email + OTP to /api/users/verify-email/
5. System validates OTP, sets user.email_verified=True

### Phone Verification Flow
1. User requests OTP via /api/users/verify-phone/request/
2. System generates OTP, sends via SMS (integration needed)
3. User submits phone + OTP to /api/users/verify-phone/confirm/
4. System validates OTP, sets user.phone_verified=True

## Testing Authentication

### Creating Test Users (api/users/tests/factories.py:5)
```python
from api.users.tests.factories import UserFactory

# Create user with specific role
admin = UserFactory(role="admin", is_staff=True)
customer = UserFactory(role="customer")
vendor_admin = UserFactory(role="vendor_admin", vendor=vendor)
```

### Force Authentication in Tests
```python
def test_protected_endpoint(api_client, user):
    api_client.force_authenticate(user=user)
    response = api_client.get("/api/users/me/")
    assert response.status_code == 200
```

### Testing Permissions
```python
def test_admin_only_endpoint(api_client, user):
    # Non-admin should get 403
    user.role = "customer"
    api_client.force_authenticate(user=user)
    response = api_client.post("/api/products/bulk-upload/", data={})
    assert response.status_code == 403

    # Admin should succeed
    user.role = "admin"
    user.save()
    response = api_client.post("/api/products/bulk-upload/", data={...})
    assert response.status_code in [200, 201]
```

## Security Best Practices

1. **Never expose password hashes**: Use write_only=True for password fields
2. **Validate password strength**: Use Django's validate_password (api/users/serializers.py:22)
3. **Rate limit auth endpoints**: Implement rate limiting for login/register
4. **Rotate JWT secret keys**: Change SECRET_KEY in production periodically
5. **Use HTTPS in production**: Enforce SSL for all API requests
6. **Validate role changes**: Only admins can change user roles
7. **Check vendor association**: Always verify user.vendor exists before filtering
8. **Log authentication failures**: Monitor failed login attempts
9. **Implement session timeout**: Configure JWT expiration appropriately
10. **Verify email/phone**: Require verification for sensitive operations

## Common Authentication Scenarios

### Scenario 1: Customer Registration & Login
1. POST /api/users/register/ (role defaults to "customer")
2. POST /api/users/login/ (get tokens)
3. Use access token for authenticated requests

### Scenario 2: Vendor Onboarding
1. POST /api/users/register/ with role="vendor_admin"
2. POST /api/vendors/signup/ (create vendor profile)
3. Admin: PATCH /api/vendors/{id}/approve/
4. Vendor can now create products (IsApprovedVendorAdmin permission)

### Scenario 3: Token Refresh
1. Access token expires (401 Unauthorized)
2. POST /api/auth/token/refresh/ with refresh token
3. Use new access token
4. If refresh token expired, redirect to login

### Scenario 4: Password Change
1. User logged in (has access token)
2. POST /api/users/change-password/ with old + new password
3. System validates old password, updates to new
4. User continues with existing tokens (no re-login needed)

### Scenario 5: Role-Based Product Access
1. Customer: GET /api/products/ (sees only active products)
2. Vendor admin: GET /api/products/ (sees only own vendor's products)
3. Admin: GET /api/products/ (sees all products including drafts/deleted)
