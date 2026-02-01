# Heroku Deployment Guide

Deploy StudyMate Bot to Heroku in minutes!

## Prerequisites

- Heroku account (free tier works)
- Heroku CLI installed: https://devcenter.heroku.com/articles/heroku-cli
- Git repository

## Quick Deploy

### 1. Install Heroku CLI

**Windows:**
```bash
# Download and install from: https://devcenter.heroku.com/articles/heroku-cli
```

**Or use installer:**
Download from https://cli-assets.heroku.com/heroku-x64.exe

### 2. Login to Heroku

```bash
heroku login
```

### 3. Create Heroku App

```bash
# Create app (Heroku will generate unique name)
heroku create

# Or with custom name
heroku create studymate-bot-your-name
```

### 4. Add Required Addons

```bash
# PostgreSQL (free tier)
heroku addons:create heroku-postgresql:essential-0

# Redis (free tier)
heroku addons:create heroku-redis:mini
```

### 5. Set Environment Variables

```bash
# Required
heroku config:set BOT_TOKEN=your-bot-token-from-botfather
heroku config:set SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')

# Optional but recommended
heroku config:set DEBUG=False
heroku config:set USE_REDIS=true
heroku config:set ADMIN_TELEGRAM_IDS=your-telegram-id
```

**Get your SECRET_KEY:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 6. Deploy

```bash
# Add Heroku remote (if not already added)
heroku git:remote -a your-app-name

# Commit all changes
git add .
git commit -m "Deploy to Heroku"

# Push to Heroku
git push heroku main
```

If you're on a different branch:
```bash
git push heroku your-branch:main
```

### 7. Scale Worker

```bash
# Start the bot (1 worker dyno)
heroku ps:scale worker=1
```

### 8. Check Logs

```bash
# View real-time logs
heroku logs --tail

# View bot logs only
heroku logs --tail --ps worker
```

---

## Verify Deployment

```bash
# Check dynos status
heroku ps

# Check addons
heroku addons

# Check config
heroku config

# Check database
heroku pg:info
```

---

## Environment Variables

Heroku automatically sets:
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis connection
- `PORT` - Not used for bot (only for web apps)

You must set:
- `BOT_TOKEN` - Your Telegram bot token
- `SECRET_KEY` - Django secret key

Optional:
- `DEBUG` - Set to False for production (default)
- `USE_REDIS` - Set to true (default)
- `ADMIN_TELEGRAM_IDS` - Comma-separated admin IDs
- `ALLOWED_HOSTS` - Not needed for worker dyno

---

## Troubleshooting

### Bot not responding

```bash
# Check logs
heroku logs --tail

# Check worker is running
heroku ps

# Restart worker
heroku restart worker
```

### Database errors

```bash
# Run migrations manually
heroku run python manage.py migrate

# Check database
heroku pg:info
heroku pg:psql
```

### Redis errors

```bash
# Check Redis addon
heroku addons:info heroku-redis

# Check Redis URL
heroku config:get REDIS_URL
```

### Out of memory

```bash
# Check memory usage
heroku ps

# Upgrade to Hobby dyno ($7/month)
heroku ps:scale worker=1:hobby
```

---

## Updating Bot

```bash
# Pull latest changes
git pull

# Commit and push
git add .
git commit -m "Update bot"
git push heroku main

# Restart if needed
heroku restart
```

---

## Database Management

### Backup

```bash
# Create manual backup
heroku pg:backups:capture

# Download latest backup
heroku pg:backups:download
```

### Restore

```bash
# Restore from backup
heroku pg:backups:restore [BACKUP_ID] DATABASE_URL
```

### Access database

```bash
# Open PostgreSQL console
heroku pg:psql

# Run Django shell
heroku run python manage.py shell
```

---

## Monitoring

### View logs

```bash
# Real-time logs
heroku logs --tail

# Last 200 lines
heroku logs -n 200

# Filter by dyno
heroku logs --ps worker --tail
```

### Check metrics

```bash
# Dyno metrics (requires dashboard or CLI plugin)
heroku ps:metrics

# Or view in dashboard
heroku open --app your-app-name
```

---

## Costs

**Free Tier:**
- PostgreSQL: essential-0 (10k rows limit)
- Redis: mini (25 MB)
- Dyno: Eco ($5/month with 1000 hours)

**Upgrade if needed:**
```bash
# PostgreSQL
heroku addons:upgrade heroku-postgresql:mini

# Redis
heroku addons:upgrade heroku-redis:premium-0

# Dyno (more memory/CPU)
heroku ps:scale worker=1:basic
```

---

## Create Django Superuser

```bash
# Create admin user for Django admin panel
heroku run python manage.py createsuperuser
```

Then access admin at: `https://your-app-name.herokuapp.com/admin`

---

## Environment Setup Summary

After deployment, your bot will have:
- ✅ PostgreSQL database (automatic)
- ✅ Redis for FSM storage (automatic)
- ✅ Automatic migrations on deploy
- ✅ Logs to stdout (viewable via `heroku logs`)
- ✅ Automatic SSL/TLS
- ✅ Daily backups (on paid plans)

---

## One-Line Deploy (After Setup)

```bash
git add . && git commit -m "Update" && git push heroku main && heroku logs --tail
```

---

## Need Help?

```bash
# Heroku status
heroku status

# App info
heroku info

# Open dashboard
heroku open

# Get help
heroku help
```

Official docs: https://devcenter.heroku.com/categories/working-with-django
