# GitHub Actions EC2 Deployment Guide

This guide explains how to deploy this Django API to a production EC2 instance using the workflow at `.github/workflows/deploy-ec2.yml`.

## Deployment Strategy

The workflow:
1. Triggers on pushes to `main` (and manual `workflow_dispatch`).
2. Copies application files from GitHub Actions runner to EC2 over SSH.
3. Writes a production `.env` file from a GitHub secret.
4. Builds the `web` image and starts `db`.
5. Waits for Postgres readiness.
6. Runs explicit one-off initialization commands:
   - `python manage.py migrate --noinput`
   - `python manage.py collectstatic --noinput`
   - `python manage.py add_countries`
7. Starts the full stack with `docker compose up -d --remove-orphans`.

This matches the current project setup (`Dockerfile`, `docker-compose.yml`, `entrypoint.sh`, `nginx.conf`).

---

## 1) One-time EC2 Setup

### A. Launch EC2
- Recommended OS: Ubuntu 22.04 LTS
- Size: at least 2 vCPU / 4 GB RAM for production-like use
- Attach an Elastic IP (recommended)

### B. Configure Security Group
Open only:
- `22/tcp` from your trusted IP(s) (SSH)
- `80/tcp` from `0.0.0.0/0` (HTTP)
- `443/tcp` from `0.0.0.0/0` (HTTPS)

Do **not** expose `5432` publicly unless you intentionally need external Postgres access.

### C. Install Docker + Compose plugin
Run on EC2:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable docker
sudo systemctl start docker
```

### D. Prepare deploy directory
```bash
sudo mkdir -p /opt/discount-ecommerce-api
sudo chown -R $USER:$USER /opt/discount-ecommerce-api
```

---

## 2) GitHub Secrets Required

In your GitHub repository:
**Settings → Secrets and variables → Actions → New repository secret**

### Required secrets

1. `EC2_HOST`  
   - Value: EC2 public IPv4 or DNS

2. `EC2_USERNAME`  
   - Value example: `ubuntu` (Ubuntu AMI), `ec2-user` (Amazon Linux)

3. `EC2_SSH_PRIVATE_KEY`  
   - Value: full PEM private key content (including `-----BEGIN ...-----`)
   - This key must match a public key allowed for `EC2_USERNAME` on the server.

4. `PROD_ENV_FILE`  
   - Value: complete multiline production `.env` file content.
   - Example:
     ```env
     DEBUG=False
     SECRET_KEY=replace-with-a-long-random-value
     ALLOWED_HOSTS=api.grottomore.com,grottomore.com
     DATABASE_URL=postgresql://app_user:strong_password@db:5432/elikem_db
     DEFAULT_FROM_EMAIL=no-reply@grottomore.com
     EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
     BASE_OTP_SECRET=replace-with-a-strong-base32-secret
     USE_S3=True
     AWS_ACCESS_KEY_ID=...
     AWS_SECRET_ACCESS_KEY=...
     AWS_STORAGE_BUCKET_NAME=...
     AWS_S3_REGION_NAME=...
     RUN_MIGRATIONS_ON_STARTUP=false
     RUN_COLLECTSTATIC_ON_STARTUP=false
     ```

### Optional secrets

5. `EC2_SSH_PORT`  
   - Default in workflow: `22`

6. `EC2_APP_DIR`  
   - Default in workflow: `/opt/discount-ecommerce-api`

---

## 3) Production Environment Variables Checklist

These variables are expected by `core/settings.py`:

- `SECRET_KEY` (**required**)
- `DEBUG` (must be `False` in production)
- `ALLOWED_HOSTS` (comma-separated domains)
- `DATABASE_URL` (PostgreSQL connection URL)
- `DEFAULT_FROM_EMAIL`
- `EMAIL_BACKEND`
- `BASE_OTP_SECRET`
- `USE_S3` (`True` / `False`)

If `USE_S3=True`, also set:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_STORAGE_BUCKET_NAME`
- `AWS_S3_REGION_NAME`

Recommended for this GitHub Actions deployment flow:
- `RUN_MIGRATIONS_ON_STARTUP=false`
- `RUN_COLLECTSTATIC_ON_STARTUP=false`

These prevent duplicate startup work because migrations and static collection already run during deployment.

---

## 4) SSL / Domain Setup (one-time)

After first deploy, SSH into EC2:

```bash
cd /opt/discount-ecommerce-api
chmod +x generate-ssl.sh
./generate-ssl.sh your-domain.com your-email@example.com
```

Also ensure your DNS A records point to the EC2 public IP.

> Note: the current `nginx.conf` has domain-specific values (`api.grottomore.com`). Update this file if your production domain differs.

---

## 5) First Deployment

1. Commit and push to `main`.
2. Open GitHub → **Actions** → **Deploy to EC2**.
3. Confirm the workflow run is green.

Database initialization is part of the workflow and runs automatically on first deploy and subsequent deploys (idempotent).

Then verify on EC2:

```bash
cd /opt/discount-ecommerce-api
docker compose ps
```

Create an admin user (first time only):

```bash
docker compose exec web python manage.py createsuperuser
```

---

## 6) Ongoing Deployments

Every push to `main` automatically redeploys.

You can also deploy manually via:
- GitHub Actions → **Deploy to EC2** → **Run workflow**

---

## 7) Rollback Options

If a deployment fails:
1. Revert the problematic commit and push to `main`, or
2. Re-run workflow from a known-good commit/branch via manual workflow dispatch.

---

## 8) Troubleshooting

### SSH/auth failures
- Verify `EC2_HOST`, `EC2_USERNAME`, `EC2_SSH_PRIVATE_KEY`, and SSH port.
- Ensure the private key has corresponding public key in `~/.ssh/authorized_keys` on EC2.

### Containers not starting
- Check:
  ```bash
  docker compose logs --tail=200 web
  docker compose logs --tail=200 nginx
  ```
- Validate `PROD_ENV_FILE` values, especially `DATABASE_URL`, `SECRET_KEY`, `ALLOWED_HOSTS`.

### 502/Bad Gateway
- Confirm `web` container is healthy and listening on port 8000 internally.
- Confirm `nginx.conf` reverse proxy points to `web:8000` (current config does).
