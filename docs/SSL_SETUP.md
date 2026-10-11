# SSL Certificate Setup with Certbot Docker

## Overview

This project uses Certbot inside Docker to generate Let’s Encrypt certificates for the EC2 deployment. Certbot stores certificates in the standard `ssl/live/<domain>/` directory, and the nginx container expects the nginx-compatible copies in `ssl/cert.pem` and `ssl/key.pem`.

## Quick SSL Certificate Generation

From the project root on the EC2 instance:

```bash
chmod +x generate-ssl.sh
./generate-ssl.sh api.grottomore.com admin@api.grottomore.com
```

This script does the following:

- creates the `ssl/` directory
- generates the certificate using Certbot
- verifies the certs at `ssl/live/api.grottomore.com/fullchain.pem` and `ssl/live/api.grottomore.com/privkey.pem`
- copies them to `ssl/fullchain.pem` and `ssl/privkey.pem`
- copies them again to the nginx-compatible names `ssl/cert.pem` and `ssl/key.pem`
- sets the correct file permissions
- restarts nginx

## What to do if certificates already exist

If the cert already exists in `ssl/live/<domain>/`, you can skip the generation step and only copy the certs into the files nginx is configured to read:

```bash
mkdir -p ssl
cp ssl/live/api.grottomore.com/fullchain.pem ssl/cert.pem
cp ssl/live/api.grottomore.com/privkey.pem ssl/key.pem
chmod 600 ssl/key.pem
chmod 644 ssl/cert.pem

docker compose restart nginx
```

## Manual certbot command

If you prefer to generate the cert manually:

```bash
mkdir -p ssl

docker run --rm -it \
  -v $(pwd)/ssl:/etc/letsencrypt \
  -v $(pwd)/ssl:/var/lib/letsencrypt \
  -p 80:80 \
  -p 443:443 \
  certbot/certbot certonly \
  --standalone \
  --email admin@api.grottomore.com \
  --agree-tos \
  --no-eff-email \
  -d api.grottomore.com
```

After that, copy the cert into nginx-friendly paths:

```bash
cp ssl/live/api.grottomore.com/fullchain.pem ssl/cert.pem
cp ssl/live/api.grottomore.com/privkey.pem ssl/key.pem
chmod 600 ssl/key.pem
chmod 644 ssl/cert.pem
```

## Renewal

To renew automatically, add this cron job:

```bash
crontab -e
```

Then add:

```bash
0 12 * * * cd /opt/discount-ecommerce-api && docker run --rm -v $(pwd)/ssl:/etc/letsencrypt -v $(pwd)/ssl:/var/lib/letsencrypt certbot/certbot renew --quiet && cp ssl/live/api.grottomore.com/fullchain.pem ssl/cert.pem && cp ssl/live/api.grottomore.com/privkey.pem ssl/key.pem && docker compose restart nginx
```

This keeps the certs fresh and restores the nginx-compatible copies after renewal.
