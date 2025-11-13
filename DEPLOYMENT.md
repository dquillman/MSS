# MSS Production Deployment Guide

This guide covers deploying MSS to production with PostgreSQL.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [PostgreSQL Setup](#postgresql-setup)
3. [Database Migration](#database-migration)
4. [Environment Configuration](#environment-configuration)
5. [Deployment Platforms](#deployment-platforms)
6. [Post-Deployment](#post-deployment)

---

## Prerequisites

### Required Services
- PostgreSQL database (version 12+)
- Email service (SendGrid or Postmark)
- Stripe account with API keys
- Domain name with SSL certificate

### Python Dependencies
```bash
pip install psycopg2-binary  # Add to requirements.txt
```

### Cloud Run Environment Variables
- Store your PostgreSQL connection string as a GitHub secret named `DATABASE_URL` (the automated deploy workflow uses it when deploying to Cloud Run).
- If you deploy manually with `deploy-to-cloud-run.sh`, provide `DATABASE_URL` in the shell environment or set `DATABASE_URL_SECRET` to the name of the Secret Manager secret that contains it.
- Example Cloud SQL string: `postgresql://user:password@/mss?host=/cloudsql/project:region:instance`

---

## PostgreSQL Setup

### Option 1: Managed PostgreSQL (Recommended)

#### Railway
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Create new project
railway init

# Add PostgreSQL
railway add -p postgresql

# Get connection string
railway variables
# Look for DATABASE_URL
```

#### Heroku
```bash
# Add PostgreSQL addon
heroku addons:create heroku-postgresql:hobby-dev

# Get connection string
heroku config:get DATABASE_URL
```

#### Neon (Serverless PostgreSQL)
1. Go to https://neon.tech
2. Create new project
3. Copy connection string

### Option 2: Self-Hosted PostgreSQL

#### Ubuntu/Debian
```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql

CREATE DATABASE mss;
CREATE USER mssuser WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE mss TO mssuser;
\q
```

#### Docker
```bash
# Run PostgreSQL container
docker run -d \
  --name mss-postgres \
  -e POSTGRES_DB=mss \
  -e POSTGRES_USER=mssuser \
  -e POSTGRES_PASSWORD=your_secure_password \
  -p 5432:5432 \
  -v mss_pgdata:/var/lib/postgresql/data \
  postgres:15

# Connection string
# postgresql://mssuser:your_secure_password@localhost:5432/mss
```

---

## Database Migration

### Step 1: Backup SQLite Database
```bash
# Create backup
cp web/mss.db web/mss.db.backup

# Export to SQL (optional)
sqlite3 web/mss.db .dump > mss_backup.sql
```

### Step 2: Install PostgreSQL Driver
```bash
pip install psycopg2-binary
```

### Step 3: Set Environment Variables
```bash
# Set PostgreSQL connection string
export DATABASE_URL="postgresql://user:password@host:port/database"

# Set SQLite path (default: web/mss.db)
export SQLITE_DB_PATH="web/mss.db"
```

### Step 4: Run Migration Script
```bash
# Interactive migration (asks for confirmation)
python migrate_to_postgres.py

# Or with explicit parameters
python migrate_to_postgres.py \
  --sqlite-db web/mss.db \
  --postgres-url "postgresql://user:password@host:port/database"

# Dry run (preview without migrating)
python migrate_to_postgres.py --dry-run
```

### Step 5: Verify Migration
The script will automatically verify row counts. You can also manually check:

```sql
-- Connect to PostgreSQL
psql $DATABASE_URL

-- Check table counts
SELECT 'users' as table_name, COUNT(*) as count FROM users
UNION ALL
SELECT 'sessions', COUNT(*) FROM sessions
UNION ALL
SELECT 'video_history', COUNT(*) FROM video_history
UNION ALL
SELECT 'password_reset_tokens', COUNT(*) FROM password_reset_tokens
UNION ALL
SELECT 'admin_whitelist', COUNT(*) FROM admin_whitelist;
```

### Step 6: Update Application Configuration
```bash
# In your .env file or environment variables
DATABASE_URL=postgresql://user:password@host:port/database
```

---

## Environment Configuration

### Required Environment Variables

Create a `.env` file in the `web/` directory:

```bash
# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Stripe (REQUIRED for payments)
STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx

# Stripe Price IDs
STRIPE_PRICE_STARTER=price_xxxxxxxxxxxxx
STRIPE_PRICE_PRO=price_xxxxxxxxxxxxx
STRIPE_PRICE_AGENCY=price_xxxxxxxxxxxxx
STRIPE_PRICE_LIFETIME=price_xxxxxxxxxxxxx

# Email Service (for password reset)
# Option 1: SendGrid
SENDGRID_API_KEY=SG.xxxxxxxxxxxxx
EMAIL_FROM=noreply@yourdomain.com

# Option 2: Postmark
POSTMARK_SERVER_TOKEN=xxxxxxxxxxxxx
POSTMARK_FROM_EMAIL=noreply@yourdomain.com

# Security
SECRET_KEY=your-secret-key-here-use-long-random-string
SESSION_COOKIE_SECURE=True  # Only if using HTTPS
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax

# Application
ENVIRONMENT=production
DEBUG=False
FRONTEND_URL=https://yourdomain.com
API_BASE_URL=https://api.yourdomain.com

# Optional: Rate Limiting
RATE_LIMIT_ENABLED=True
RATE_LIMIT_PER_MINUTE=60

# Optional: Admin
ADMIN_EMAIL=admin@yourdomain.com
```

### Generate Secret Key
```python
import secrets
print(secrets.token_urlsafe(32))
```

---

## Deployment Platforms

### Railway (Recommended for Beginners)

1. **Install Railway CLI**
```bash
npm install -g @railway/cli
railway login
```

2. **Initialize Project**
```bash
cd mss
railway init
```

3. **Add PostgreSQL**
```bash
railway add -p postgresql
```

4. **Set Environment Variables**
```bash
railway variables set STRIPE_SECRET_KEY=sk_live_xxxxx
railway variables set STRIPE_WEBHOOK_SECRET=whsec_xxxxx
# ... add all other env vars
```

5. **Deploy**
```bash
railway up
```

### Heroku

1. **Install Heroku CLI**
```bash
brew install heroku/brew/heroku  # macOS
# or
curl https://cli-assets.heroku.com/install.sh | sh
```

2. **Create App**
```bash
heroku create mss-production
```

3. **Add PostgreSQL**
```bash
heroku addons:create heroku-postgresql:hobby-dev
```

4. **Set Environment Variables**
```bash
heroku config:set STRIPE_SECRET_KEY=sk_live_xxxxx
heroku config:set STRIPE_WEBHOOK_SECRET=whsec_xxxxx
# ... add all other env vars
```

5. **Create Procfile**
```bash
echo "web: cd web && gunicorn -w 4 -b 0.0.0.0:\$PORT api_server:app" > Procfile
```

6. **Deploy**
```bash
git push heroku main
```

### DigitalOcean App Platform

1. **Create App**
   - Go to https://cloud.digitalocean.com/apps
   - Click "Create App"
   - Connect GitHub repo

2. **Add PostgreSQL Database**
   - Add "Database" component
   - Choose PostgreSQL

3. **Configure**
   - Build Command: `pip install -r requirements.txt`
   - Run Command: `cd web && gunicorn -w 4 -b 0.0.0.0:8080 api_server:app`

4. **Set Environment Variables**
   - Add all variables
   - DATABASE_URL is auto-set

### VPS (Ubuntu) Deployment

For advanced users who want full control:

```bash
# Install dependencies
sudo apt update
sudo apt install python3-pip python3-venv nginx postgresql

# Create virtual environment
cd /var/www/mss
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install Gunicorn
pip install gunicorn

# Configure Nginx
sudo nano /etc/nginx/sites-available/mss

# Nginx config:
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /out/ {
        alias /var/www/mss/out/;
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/mss /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Create systemd service
sudo nano /etc/systemd/system/mss.service

# Service config:
[Unit]
Description=MSS API Server
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/mss/web
Environment="PATH=/var/www/mss/venv/bin"
ExecStart=/var/www/mss/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 api_server:app

[Install]
WantedBy=multi-user.target

# Start service
sudo systemctl enable mss
sudo systemctl start mss
```

---

## Post-Deployment

### 1. Test Critical Paths

```bash
# Health check
curl https://yourdomain.com/health

# User registration
curl -X POST https://yourdomain.com/api/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test123"}'

# Login
curl -X POST https://yourdomain.com/api/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test123"}'
```

### 2. Configure Stripe Webhooks

1. Go to Stripe Dashboard → Developers → Webhooks
2. Add endpoint: `https://yourdomain.com/stripe-webhook`
3. Select events:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Copy webhook signing secret to `STRIPE_WEBHOOK_SECRET`

### 3. Set Up Email Service

#### SendGrid
1. Go to https://sendgrid.com
2. Create API key
3. Verify sender domain
4. Add API key to environment variables

#### Postmark
1. Go to https://postmarkapp.com
2. Create server
3. Verify sender domain
4. Add server token to environment variables

### 4. Configure DNS

Add these DNS records:

```
A     @         -> your-server-ip
A     www       -> your-server-ip
CNAME api       -> your-server-hostname
MX    @         -> mail.yourdomain.com  (if using custom email)
```

### 5. Set Up SSL Certificate

#### Let's Encrypt (Free)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

#### Cloudflare (Free)
1. Add site to Cloudflare
2. Update nameservers
3. Enable SSL/TLS → Full

### 6. Monitoring & Logging

#### Application Monitoring
- Sentry: https://sentry.io
- Rollbar: https://rollbar.com

#### Server Monitoring
- UptimeRobot: https://uptimerobot.com
- Pingdom: https://pingdom.com

#### Log Aggregation
- Papertrail: https://papertrailapp.com
- Loggly: https://loggly.com

### 7. Backup Strategy

```bash
# Daily PostgreSQL backups
0 2 * * * pg_dump $DATABASE_URL > /backups/mss_$(date +\%Y\%m\%d).sql

# Weekly full backup
0 3 * * 0 tar -czf /backups/mss_full_$(date +\%Y\%m\%d).tar.gz /var/www/mss

# Upload to S3 (optional)
aws s3 cp /backups/ s3://your-backup-bucket/ --recursive
```

---

## Troubleshooting

### Database Connection Errors

```bash
# Test PostgreSQL connection
psql $DATABASE_URL

# Check if database exists
psql $DATABASE_URL -c "\l"

# Check tables
psql $DATABASE_URL -c "\dt"
```

### Application Won't Start

```bash
# Check logs
heroku logs --tail  # Heroku
railway logs        # Railway

# Test locally
export DATABASE_URL="postgresql://..."
cd web
python api_server.py
```

### Stripe Webhook Failures

1. Check webhook signing secret matches
2. Verify endpoint is publicly accessible
3. Test with Stripe CLI:
```bash
stripe listen --forward-to localhost:5000/stripe-webhook
```

---

## Security Checklist

- [ ] PostgreSQL connection uses SSL (`?sslmode=require`)
- [ ] All environment variables are set securely
- [ ] Secret keys are random and unique
- [ ] HTTPS is enabled (no HTTP)
- [ ] Cookies are secure and httponly
- [ ] Rate limiting is enabled
- [ ] Database backups are automated
- [ ] Monitoring and alerting are set up
- [ ] Email service is verified
- [ ] Stripe webhooks are configured
- [ ] Password reset emails work
- [ ] Admin accounts are secured with strong passwords

---

## Performance Optimization

### Database
```sql
-- Add indexes for common queries
CREATE INDEX idx_users_subscription_tier ON users(subscription_tier);
CREATE INDEX idx_video_history_user_created ON video_history(user_id, created_at DESC);
```

### Caching (Redis)
```bash
# Add Redis for session storage and caching
pip install redis flask-caching

# Configure
REDIS_URL=redis://localhost:6379/0
```

### CDN for Static Files
- Cloudflare: Free tier includes CDN
- AWS CloudFront: Pay as you go
- BunnyCDN: Affordable option

---

## Support

If you encounter issues:
1. Check logs first
2. Review this guide
3. Test database connection
4. Verify environment variables
5. Contact support@mss.com

---

**Last Updated:** 2025-10-11
**Version:** 5.5.2
