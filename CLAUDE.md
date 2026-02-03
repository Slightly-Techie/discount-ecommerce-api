# Discount E-commerce API

## Project Overview
Django REST Framework-based e-commerce backend supporting multi-vendor marketplace operations, product management, shopping cart, orders with shipping/tax calculations, and JWT authentication with role-based access control.

**Live Domains**: grottomore.com | discount-ecommerce-frontend.vercel.app

## Tech Stack
- **Framework**: Django 5.2.4 + Django REST Framework 3.14+
- **Database**: PostgreSQL (via DATABASE_URL env var)
- **Authentication**: JWT (djangorestframework-simplejwt)
- **Storage**: AWS S3 (boto3, django-storages) or local filesystem (USE_S3 env flag)
- **API Docs**: drf-yasg (Swagger/ReDoc at /swagger/ and /redoc/)
- **Testing**: pytest + pytest-django + factory-boy
- **Server**: Gunicorn (production), runserver (dev)
- **Deployment**: Docker + nginx (configs in repo root)

## Project Structure

```
api/
├── users/         # User auth, registration, profiles, roles (customer/seller/vendor_admin/manager/admin)
├── vendors/       # Vendor onboarding, approval workflow, vendor-specific data
├── products/      # Product catalog, variants, images, reviews, bulk upload (JSON/CSV)
├── category/      # Hierarchical categories (self-referential parent field)
├── cart/          # Shopping cart (one per user) and cart items
├── orders/        # Order processing, shipping zones/methods, tax zones/rates, countries
└── common/        # Shared utilities (permissions, validators, OTP, email, shipping/tax calculation)

core/
├── settings.py    # Django config (core/settings.py:1)
├── urls.py        # Root URL routing (core/urls.py:1)
└── wsgi.py        # WSGI entry point

tests/             # Root-level integration tests
static/            # Collected static files (STATIC_ROOT)
media/             # Uploaded files if USE_S3=False
```

## Key Directories & Their Purpose

**api/users**: Authentication (JWT tokens at /api/auth/token/), user registration/login, profile management, email/phone verification (OTP), password reset, role-based access (api/users/models.py:15 for User.Role choices)

**api/vendors**: Vendor signup, admin approval/rejection/suspension workflows, vendor profile management (api/vendors/models.py:8 for Vendor.Status)

**api/products**: CRUD for products with variants/images/reviews, filtering/search/ordering, bulk upload endpoint for admins (api/products/views.py:140 for bulk upload), stock management, discounted product queries

**api/category**: Hierarchical category tree (category.parent allows nesting), used for product organization

**api/cart**: User-specific cart and cart items, automatically created on first item add, cleared after checkout

**api/orders**: Multi-vendor order splitting (orders grouped by vendor), shipping calculation by country/zone (api/common/utils.py:43), tax calculation (api/common/utils.py:75), order status workflow (pending→paid→shipped→delivered)

**api/common**: Shared code - custom permissions (IsAdminOrManager, IsVendorAdmin at api/common/permissions.py:10), phone/email validators, OTP generation/verification, shipping/tax calculators, delivery availability checker

## Core Architectural Patterns

**See .claude/docs/architectural_patterns.md** for detailed patterns including:
- BaseModel inheritance (UUID primary keys, timestamps)
- QuerySet/Manager pattern for reusable filters
- Soft delete pattern (is_deleted field)
- Role-based access control
- Serializer strategies (read/write separation, nested serializers)
- View patterns (conditional permissions, queryset filtering)

## Essential Commands

**Setup**:
```bash
# NOTE: Virtual environment is located in parent directory (..\venv)
..\venv\scripts\activate  # Windows - activate venv from parent directory
pip install -r requirements.txt
cp sample_env .env  # Edit .env with your config
python manage.py migrate
python manage.py createsuperuser
```

**Development**:
```bash
# IMPORTANT: Always activate virtual environment first
..\venv\scripts\activate  # Activate venv (Windows - venv is in parent directory)

python manage.py runserver  # Dev server at http://localhost:8000
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic  # Gather static files
python manage.py add_countries  # Load shipping/tax country data
```

**Testing**:
```bash
# Activate venv first: ..\venv\scripts\activate

pytest                          # Run all tests
pytest api/products/tests/      # Test specific app
pytest -k "test_product_list"   # Run tests matching name
pytest --reuse-db               # Reuse test database (faster)
pytest -v                       # Verbose output
```

**Production**:
```bash
gunicorn core.wsgi:application --bind 0.0.0.0:8000
```

**Docker**:
```bash
docker build -t ecommerce-api .
docker run -p 8000:8000 --env-file .env ecommerce-api
```

## Environment Configuration

Required variables in `.env` (see `sample_env` for full list):
- `SECRET_KEY`: Django secret key
- `DEBUG`: True/False
- `ALLOWED_HOSTS`: Comma-separated hosts
- `DATABASE_URL`: postgresql://user:pass@host:port/dbname
- `USE_S3`: True/False (enables AWS S3 storage)
- `AWS_*`: S3 credentials if USE_S3=True

## API Endpoints

**Base URL**: All endpoints under `/api/`

**Authentication** (/api/auth/):
- POST /token/ - Obtain JWT pair (access + refresh)
- POST /token/refresh/ - Refresh access token
- POST /token/verify/ - Verify token

**Users** (/api/users/): register, login, me (profile), change-password, verify-email, verify-phone

**Vendors** (/api/vendors/): signup, list, detail, me, approve, reject, suspend

**Products** (/api/products/): CRUD, bulk-upload, fetch-discounted, images, variants, reviews

**Categories** (/api/category/): CRUD with hierarchical support

**Cart** (/api/cart/): my-cart, add-item, update-item, remove-item, clear-cart

**Orders** (/api/orders/): checkout, my-orders, vendor-orders (for vendor_admin role), detail, update-status

See /swagger/ or /redoc/ for interactive API documentation.

## Additional Documentation

The following documentation files are automatically loaded into memory:

@.claude/docs/architectural_patterns.md
@.claude/docs/authentication_guide.md
@.claude/docs/testing_guide.md
@.claude/docs/vendor_workflow.md
@.claude/docs/order_processing.md

## Common Workflows

**Adding a new model**:
1. Define model in app/models.py (inherit from BaseModel for UUID+timestamps)
2. Create serializer in app/serializers.py
3. Create views in app/views.py (use generics.ListCreateAPIView, etc.)
4. Add URL patterns in app/urls.py with app_name namespace
5. Register in app/admin.py for Django admin
6. Run makemigrations + migrate
7. Create factory in app/tests/factories.py
8. Register factory in api/conftest.py using register(YourFactory)
9. Write tests in app/tests/test_views.py using fixtures (NOT factory imports)

**Adding a new API endpoint**:
1. Create view class in app/views.py
2. Set permission_classes (see api/common/permissions.py for custom options)
3. Add URL pattern in app/urls.py
4. Add @swagger_auto_schema decorator for API docs (optional)
5. Write tests covering happy path + error cases

**Writing tests (CRITICAL PATTERN)**:
1. NEVER import factories directly (from api.app.tests.factories import Factory)
2. ALWAYS use fixtures (def test_something(api_client, user_factory, vendor):)
3. Fixtures are auto-available from api/conftest.py registration
4. Use `model_factory()` to create instances, `model` for single default instance
5. Example: `user_factory(role="admin")` NOT `UserFactory(role="admin")`

**Working with vendors**:
- Vendor signup creates pending vendor (api/vendors/views.py:15)
- Admin approves via PATCH /api/vendors/{id}/approve/ (api/vendors/views.py:80)
- Vendor users have role="vendor_admin" and user.vendor foreign key
- Products/orders filtered by vendor for vendor_admin users (see api/products/views.py:25 get_queryset)

**File references format**: Use path:line format (e.g., api/users/models.py:42)
