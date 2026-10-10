#!/bin/bash

# SSL Certificate Generation Script
# This script generates SSL certificates using certbot docker image

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if domain is provided
if [ $# -eq 0 ]; then
    print_error "Usage: $0 <domain> [email]"
    echo "Example: $0 example.com admin@example.com"
    exit 1
fi

DOMAIN=$1
EMAIL=${2:-"admin@$DOMAIN"}

print_status "Generating SSL certificates for domain: $DOMAIN"
print_status "Email: $EMAIL"

# Create SSL directory
print_status "Creating SSL directory..."
mkdir -p ssl

# Stop nginx temporarily to free up ports
print_status "Stopping nginx to free up ports..."
docker-compose stop nginx 2>/dev/null || true

# Generate SSL certificates using certbot docker image
print_status "Generating SSL certificates..."
docker run --rm -it \
  -v $(pwd)/ssl:/etc/letsencrypt \
  -v $(pwd)/ssl:/var/lib/letsencrypt \
  -p 80:80 \
  -p 443:443 \
  certbot/certbot certonly \
  --standalone \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$DOMAIN" 

# Check if certificates were generated
if [ ! -f "ssl/fullchain.pem" ] || [ ! -f "ssl/privkey.pem" ]; then
    print_error "SSL certificates were not generated successfully"
    exit 1
fi

print_status "SSL certificates generated successfully!"

# Set proper permissions
print_status "Setting proper permissions..."
chmod 600 ssl/privkey.pem
chmod 644 ssl/fullchain.pem

# Copy certificates to nginx location
print_status "Copying certificates to nginx location..."
cp ssl/fullchain.pem ssl/cert.pem
cp ssl/privkey.pem ssl/key.pem

# Update nginx configuration with domain
print_status "Updating nginx configuration..."
sed -i "s/localhost/$DOMAIN/g" nginx.conf

# Restart nginx
print_status "Restarting nginx..."
docker-compose up -d nginx

print_status "SSL setup completed successfully!"
print_status "Your application should now be accessible at: https://$DOMAIN"
print_status "Admin panel: https://$DOMAIN/admin/"
print_status "API: https://$DOMAIN/api/"
print_status "Swagger: https://$DOMAIN/swagger/"

echo ""
print_warning "Don't forget to:"
echo "  - Update your domain's DNS to point to your EC2 IP"
echo "  - Configure AWS security groups to allow ports 80 and 443"
echo "  - Set up SSL renewal with: crontab -e"
echo "  - Add this line to crontab for automatic renewal:"
echo "    0 12 * * * docker run --rm -v $(pwd)/ssl:/etc/letsencrypt -v $(pwd)/ssl:/var/lib/letsencrypt certbot/certbot renew --quiet && cp ssl/fullchain.pem ssl/cert.pem && cp ssl/privkey.pem ssl/key.pem && docker-compose restart nginx" 