## Discount E-commerce API – Developer Instructions

### 1. Introduction & Overview

This repository contains the **Discount E-commerce API**, a Django REST Framework–based backend for an e‑commerce platform.  
It provides APIs for authentication, user and profile management, products and categories, shopping cart, orders, coupons/discounts, shipping, and tax calculation.

Use this document as a **developer onboarding guide**: how the project is structured, how to set it up locally, how to run tests, and what conventions to follow when making changes.

---

### 2. Tech Stack

- **Backend framework**: Django 5.x, Django REST Framework
- **Database**: PostgreSQL (production), SQLite (default/dev)
- **Authentication**: JWT (`djangorestframework-simplejwt`)
- **API docs**: `drf-yasg` (Swagger / ReDoc)
- **File storage**: Local filesystem (dev) and optional AWS S3 via `django-storages`
- **Testing**: `pytest`, `pytest-django`, `pytest-factoryboy`, `factory-boy`
- **Code quality**: `black`, `isort`, `flake8`, `mypy`, `pre-commit`
- **Deployment**: Docker, Docker Compose, Nginx, Gunicorn
- **Other key libs**: `django-filter`, `django-cors-headers`, `Pillow`, `pyotp`

---

### 3. Project Structure

High-level layout (only key files/directories shown):

```text
discount-ecommerce-api/
├── api/                          # Main Django apps (domain logic)
│   ├── users/                    # User accounts & profiles
│   │   ├── models.py             # User, Profile, Address models
│   │   ├── views.py              # Auth, registration, profile endpoints
│   │   ├── serializers.py        # User/Address/Profile serializers
│   │   ├── urls.py               # User routes
│   │   ├── signals.py            # User-related signals
│   │   └── tests/                # Users app tests & factories
│   ├── products/                 # Product management
│   │   ├── models.py             # Product, ProductImage, Variant, Review
│   │   ├── views.py              # CRUD, bulk upload, discounted products
│   │   ├── serializers.py
│   │   └── urls.py
│   ├── category/                 # Categories & tags
│   │   ├── models.py             # Category (hierarchical), Tag
│   │   ├── views.py              # CRUD + bulk upload (JSON/CSV)
│   │   └── urls.py
│   ├── cart/                     # Shopping cart
│   │   ├── models.py             # Cart (per user), CartItem
│   │   ├── views.py              # Cart & cart item management
│   │   └── urls.py
│   ├── orders/                   # Orders, coupons, shipping, tax
│   │   ├── models.py             # Order, OrderItem, Coupon, Shipping/Tax models
│   │   ├── views.py              # Checkout and order endpoints
│   │   └── urls.py
│   ├── common/                   # Shared utilities & base models
│   │   ├── models.py             # `BaseModel` (UUID, timestamps)
│   │   ├── utils.py              # OTP, email, shipping/tax helpers, etc.
│   │   ├── permissions.py        # Custom DRF permissions
│   │   └── management/commands/  # Custom Django management commands
│   └── conftest.py               # Pytest fixtures & factory registration
├── core/                         # Django project configuration
│   ├── settings.py               # Settings (installed apps, DB, DRF, JWT, CORS, etc.)
│   ├── urls.py                   # Root URL router
│   ├── wsgi.py
│   └── asgi.py
├── tests/                        # Root-level tests (if any)
├── manage.py                     # Django management entry point
├── requirements.txt              # Runtime dependencies
├── dev-requirements.txt          # Dev/test tools
├── docker-compose.yml            # Docker Compose services
├── Dockerfile                    # Web app Docker image
├── nginx.conf                    # Nginx reverse proxy config
├── entrypoint.sh                 # Container entry script (Gunicorn, migrations, etc.)
├── pytest.ini                    # Pytest configuration
├── .pre-commit-config.yaml       # Pre-commit hooks
└── sample_env                    # Example environment file
```

When adding new features, follow the existing **per-app structure** inside `api/` (models, serializers, views, urls, tests).

---

### 4. Local Development Setup

#### 4.1 Prerequisites

- Python **3.11+**
- PostgreSQL (recommended for realistic local testing) or SQLite
- Git
- (Optional) Docker & Docker Compose

#### 4.2 Clone and Activate Virtual Environment (IMPORTANT)

**Always use your virtual environment** (venv). Do **not** install packages into your global Python / system environment.

If you already have a venv outside this repo, activate it first and then run the install commands.

```bash
git clone <REPO_URL>
cd discount-ecommerce-api

# Windows
. ..\venv\Scripts\Activate.ps1
# macOS / Linux
source <PATH_TO_YOUR_VENV>/bin/activate
```

If you need to create a new one, you can:

```bash
python -m venv venv
# Windows PowerShell
venv\Scripts\Activate.ps1
```

#### 4.3 Install Dependencies

```bash
pip install -r requirements.txt
pip install -r dev-requirements.txt  # for dev/test tooling
```

#### 4.4 Configure Environment Variables

1. Copy the sample file:
   ```bash
   cp sample_env .env
   ```
2. Open `.env` and set at least:
   - `SECRET_KEY` – strong secret key for Django.
   - `DEBUG` – `True` for local development.
   - `ALLOWED_HOSTS` – e.g. `127.0.0.1,localhost`.
   - `DATABASE_URL` – e.g.:
     - SQLite: `sqlite:///db.sqlite3`
     - PostgreSQL: `postgres://user:password@localhost:5432/discount_db`
   - `BASE_OTP_SECRET` – base32 secret for OTPs.
   - `DEFAULT_FROM_EMAIL` and `EMAIL_BACKEND` – for email sending.
   - Optional S3-related variables if using AWS for media/static.

See the **Environment Variables Reference** section below for more details.

#### 4.5 Initialize Database

```bash
python manage.py makemigrations
python manage.py migrate
```

Create a superuser:

```bash
python manage.py createsuperuser
```

Optionally load initial data (such as countries for shipping/tax):

```bash
python manage.py add_countries
```

#### 4.6 Run the Development Server

```bash
python manage.py runserver
```

Default endpoints:
- API root (depending on configuration): usually under `/api/`
- Admin: `/admin/`
- Swagger UI: `/swagger/`
- ReDoc: `/redoc/`

---

### 5. Running with Docker

> This is the preferred way to run the full stack (Django + PostgreSQL + Nginx).

#### 5.1 Build and Start Services

```bash
docker-compose up -d
```

This typically starts:
- `web` – Django app (via Gunicorn)
- `db` – PostgreSQL
- `nginx` – reverse proxy / SSL terminator

#### 5.2 Apply Migrations & Create Superuser

```bash
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

#### 5.3 Access the Application

- API: `http://localhost:8000/api/` (or via Nginx: `http://localhost/`)
- Admin: `http://localhost:8000/admin/`
- Swagger UI: `http://localhost:8000/swagger/`
- ReDoc: `http://localhost:8000/redoc/`

---

### 6. Major Features & Endpoints (High-Level)

> Exact URL patterns may vary slightly; check each app’s `urls.py` for specifics.

#### 6.1 Authentication & Users (`/api/users/`, `/api/auth/`)

- **Registration** – create a new user account.
- **Login** – obtain JWT access/refresh tokens.
- **Token refresh/verify** – via Simple JWT endpoints.
- **Current user** – retrieve/update own profile.
- **Password flows** – change/reset password.
- **Verification** – OTP-based email/phone verification.
- **Addresses** – CRUD operations for user addresses.
- **Roles** – customers, staff/manager/admin, used for permissions.

#### 6.2 Products (`/api/products/`)

- CRUD for products, variants, images, reviews.
- Bulk upload support (JSON/CSV) for importing products.
- Filters by category, tag, price range, status.
- Search and ordering (e.g. by price, date).
- Discounted products and related features.

#### 6.3 Categories & Tags (`/api/category/`)

- Hierarchical categories (parent/child).
- Tags for products.
- Bulk upload (JSON/CSV) for categories/tags.

#### 6.4 Cart (`/api/cart/`)

- One active cart per user (auto created).
- Add, update, remove cart items.
- Top-level endpoints to manage items without manually handling cart IDs.

#### 6.5 Orders, Coupons, Shipping & Tax (`/api/orders/`)

- **Checkout** – convert a cart into an order, applying coupons and calculating totals.
- **Order listing/detail** – user and admin views.
- **Order status updates** – controlled via permissions.
- **Coupons & promotion logic** – validation and tracking of coupon usage.
- **Shipping zones/methods** – shipping cost calculation.
- **Tax zones/rates** – tax calculation per region.

---

### 7. Testing

#### 7.1 Test Layout

- App-specific tests under `api/<app_name>/tests/`.
- Factories using `factory-boy` (often in `factories.py`) for creating test data.
- Shared fixtures and factory registration in `api/conftest.py`.
- Optional root-level tests under `tests/`.

#### 7.2 Running Tests

From the project root (with venv activated):

```bash
pytest                 # run all tests
pytest api/users/tests/  # run a specific app's tests
pytest -v             # verbose
pytest --reuse-db     # reuse test DB for speed
```

---

### 8. Deployment Notes

#### 8.1 Production Configuration

Typical production stack:
- Django app served by **Gunicorn**
- **Nginx** as reverse proxy and SSL terminator (see `nginx.conf`)
- PostgreSQL database
- Optional AWS S3 for static/media

Key steps:
1. Set `DEBUG=False` and proper `ALLOWED_HOSTS` in `.env`.
2. Configure a production database (`DATABASE_URL` for PostgreSQL).
3. Set a strong `SECRET_KEY`.
4. Configure email backend suitable for production.
5. Configure SSL certificates (see helper scripts like `generate-ssl.sh` if present).
6. Run:
   ```bash
   python manage.py migrate
   python manage.py collectstatic
   ```
7. Build and run containers with `docker-compose up -d` on the server.

There may be additional quick‑deploy guides such as `QUICK_DEPLOY.md` or SSL‑specific docs in the repo—refer to them if present.

---

### 9. Coding Guidelines & Conventions

#### 9.1 App & Module Organization

- Each **feature area** is a Django app under `api/` (`users`, `products`, `cart`, `orders`, etc.).
- Standard Django+DRF structure per app:
  - `models.py` – database models
  - `serializers.py` – DRF serializers
  - `views.py` – DRF views / viewsets / APIViews
  - `urls.py` – app routes
  - `tests/` – unit/integration tests and factories
- Shared logic goes in `api/common/` (base models, permissions, utilities).

#### 9.2 Models

- Most models inherit from `api.common.models.BaseModel`:
  - UUID primary keys
  - `created_at`, `updated_at` timestamps
- Use explicit managers/querysets for commonly used filters (e.g. active/non-deleted).
- Prefer **soft deletion flags** where relevant instead of hard deletes when business logic requires history.

#### 9.3 Views & Serializers

- Prefer DRF generics (`ListCreateAPIView`, `RetrieveUpdateDestroyAPIView`, etc.) when possible.
- Use `APIView` or custom mixins for complex flows (e.g. checkout, bulk operations).
- Use separate **read vs write serializers** when representations differ (e.g. nested detail on read, IDs on write).
- Implement validation in serializers where it concerns request data; keep business logic in models/services/utilities.

#### 9.4 URLs

- App URLs are defined in each `api/<app>/urls.py`.
- They are included in `core/urls.py` under appropriate prefixes (e.g. `/api/users/`, `/api/products/`).
- UUID primary keys are used in patterns where appropriate: `<uuid:pk>`.

#### 9.5 Code Style & Quality

- **Formatting**: `black` (line length typically 120) and `isort` (black profile).
- **Linting**: `flake8` configured via project settings.
- **Type checking**: `mypy` where applicable.
- **Pre-commit**: hooks defined in `.pre-commit-config.yaml`.

To run all hooks locally:

```bash
pre-commit install
pre-commit run --all-files
```

---

### 10. Environment Variables Reference (Summary)

| Variable                  | Description                              | Example                                  |
|---------------------------|------------------------------------------|------------------------------------------|
| `SECRET_KEY`             | Django secret key                        | `super-secret-key`                       |
| `DEBUG`                  | Debug mode                               | `True` / `False`                         |
| `ALLOWED_HOSTS`          | Allowed hostnames                        | `127.0.0.1,localhost`                    |
| `DATABASE_URL`           | Database connection string               | `sqlite:///db.sqlite3` or PostgreSQL URL |
| `BASE_OTP_SECRET`        | Base32 secret for OTP generation         | `BASE32SECRET3232`                       |
| `DEFAULT_FROM_EMAIL`     | Default from email address               | `webmaster@localhost`                    |
| `EMAIL_BACKEND`          | Email backend                            | `django.core.mail.backends.console.EmailBackend` |
| `USE_S3`                 | Toggle S3 for media/static               | `True` / `False`                         |
| `AWS_ACCESS_KEY_ID`      | AWS access key                           | (if `USE_S3=True`)                       |
| `AWS_SECRET_ACCESS_KEY`  | AWS secret key                           | (if `USE_S3=True`)                       |
| `AWS_STORAGE_BUCKET_NAME`| S3 bucket name                           | (if `USE_S3=True`)                       |
| `AWS_S3_REGION_NAME`     | S3 region                                | (if `USE_S3=True`)                       |

Refer to `sample_env` and `core/settings.py` for the full and authoritative list.

---

### 11. API Documentation

- **Swagger UI**: available at `/swagger/`
- **ReDoc**: available at `/redoc/`

Both are generated from DRF views using `drf-yasg`, and support JWT authentication. Use these UIs to discover endpoints and their request/response schemas.

---

### 12. How to Work on New Features

When adding or modifying functionality:

1. **Create/extend models** under the appropriate app in `api/`.
2. Add or update **serializers** to control API representations and validation.
3. Implement **views/viewsets** using DRF generics or `APIView` for complex flows.
4. Wire up new routes in the app’s `urls.py`.
5. Write or update **tests** in `api/<app>/tests/`.
6. Run `pytest` and ensure tests pass.
7. Run formatting/linting (`black`, `isort`, `flake8`, `pre-commit`).

Following these steps will keep the codebase consistent and maintainable.

