# SSL Certificate Setup with Certbot Docker

## Quick SSL Certificate Generation

Since Docker and Docker Compose are already installed on your EC2 instance, use the provided script to generate SSL certificates:

```bash
# Make the script executable
chmod +x generate-ssl.sh

# Run the script with your domain
./generate-ssl.sh your-domain.com your-email@example.com
```

## What the Script Does

- Uses the official certbot docker image
- Generates certificates for your domain and www subdomain
- Places certificates in the `ssl/` directory where nginx expects them
- Automatically updates nginx configuration with your domain
- Sets proper file permissions
- Restarts nginx with the new certificates

## Manual Commands (if needed)

If you prefer to run the commands manually:

```bash
# Create SSL directory
mkdir -p ssl

# Generate SSL certificates using certbot docker image
docker run --rm -it \
  -v $(pwd)/ssl:/etc/letsencrypt \
  -v $(pwd)/ssl:/var/lib/letsencrypt \
  -p 80:80 \
  -p 443:443 \
  certbot/certbot certonly \
  --standalone \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email \
  -d your-domain.com \
  -d www.your-domain.com

# Set proper permissions
chmod 600 ssl/privkey.pem
chmod 644 ssl/fullchain.pem

# Copy certificates to nginx location
cp ssl/fullchain.pem ssl/cert.pem
cp ssl/privkey.pem ssl/key.pem

# Restart nginx
docker-compose restart nginx
```

## SSL Renewal

To set up automatic renewal, add this to your crontab:

```bash
# Edit crontab
crontab -e

# Add this line for daily renewal check
0 12 * * * docker run --rm -v $(pwd)/ssl:/etc/letsencrypt -v $(pwd)/ssl:/var/lib/letsencrypt certbot/certbot renew --quiet && cp ssl/fullchain.pem ssl/cert.pem && cp ssl/privkey.pem ssl/key.pem && docker-compose restart nginx
```

That's it! Your SSL certificates will be generated and nginx will serve your application over HTTPS.
