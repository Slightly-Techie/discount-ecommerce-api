# Discount E-commerce API

A Django REST Framework-based e-commerce backend that supports:
- User authentication (JWT, registration, login, roles)
- Product management (internal/external, categories, tags, images, variants, reviews)
- Cart and cart item management
- Bulk upload (JSON/CSV) for products, categories, tags
- Filtering, search, ordering, and more

## Getting Started

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd discount-ecommerce-api
```

### 2. Set Up Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables
- Copy `sample_env` to `.env` and fill in your secrets/configuration:
```bash
cp sample_env .env
```
- Edit `.env` as needed (see `sample_env` for required variables).

### 5. Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create a Superuser (for admin access)
```bash
python manage.py createsuperuser
```

### 7. Start the Development Server
```bash
python manage.py runserver
```

### 8. Access the API
- Swagger UI: [http://localhost:8000/swagger/](http://localhost:8000/swagger/)
- Redoc: [http://localhost:8000/redoc/](http://localhost:8000/redoc/)
- Django Admin: [http://localhost:8000/admin/](http://localhost:8000/admin/)

## Features
- JWT authentication with roles (customer, seller, manager, admin)
- Product, category, tag, image, variant, review management
- Cart and cart item management (one cart per user)
- Bulk upload (JSON/CSV) for products, categories, tags
- Filtering, search, ordering on all major endpoints
- Admin dashboards for all models

## Deployment
- GitHub Actions to EC2 (production): see [docs/GITHUB_ACTIONS_EC2_DEPLOYMENT.md](docs/GITHUB_ACTIONS_EC2_DEPLOYMENT.md)
- Quick manual EC2 deploy steps: see [docs/QUICK_DEPLOY.md](docs/QUICK_DEPLOY.md)
- SSL setup details: see [docs/SSL_SETUP.md](docs/SSL_SETUP.md)

## Contributing
Pull requests are welcome! Please open an issue first to discuss major changes.

## License
[MIT](LICENSE) 