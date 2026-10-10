# Quick EC2 Deployment

Since Docker and Docker Compose are already installed on your EC2 instance, here are the minimal steps:


## 1. Generate SSL Certificates

```bash
# Make the script executable
chmod +x generate-ssl.sh

# Run the script with your domain
./generate-ssl.sh your-domain.com your-email@example.com
```

## 2. Initialize Database (first deploy + every release)

```bash
# Start database service
docker compose up -d db

# Apply schema migrations
docker compose run --rm web python manage.py migrate --noinput

# Collect static files
docker compose run --rm web python manage.py collectstatic --noinput

# Seed country data (idempotent)
docker compose run --rm web python manage.py add_countries
```

## 3. Start Application

```bash
docker compose up -d --remove-orphans
```

## 4. Create Superuser

```bash
docker compose exec web python manage.py createsuperuser
```

## 5. Monitor Application

```bash
./monitor.sh
```

## AWS Security Group

Make sure these ports are open:
- HTTP (80) - 0.0.0.0/0
- HTTPS (443) - 0.0.0.0/0
- SSH (22) - Your IP only

## Access Your Application

- **Main App**: `https://your-domain.com/`
- **Admin**: `https://your-domain.com/admin/`
- **API**: `https://your-domain.com/api/`
- **Swagger**: `https://your-domain.com/swagger/`

That's it! Your Django application is now deployed with SSL.
