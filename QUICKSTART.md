# Quick Start Guide

Get StudyMate Bot running in 5 minutes!

## 🚀 Option 1: Docker Compose (Recommended)

**Prerequisites:** Docker and Docker Compose installed

```bash
# 1. Clone repository
git clone <your-repo>
cd studymate-bot

# 2. Configure environment
cp .env.example .env
nano .env  # Edit BOT_TOKEN and SECRET_KEY

# 3. Start everything
docker-compose up -d

# 4. Check status
make health
# or
docker-compose logs -f bot
```

**That's it!** Bot is running with PostgreSQL + Redis.

---

## 🛠️ Option 2: Local Development

**Prerequisites:** Python 3.11+, PostgreSQL, Redis

```bash
# 1. Clone and install
git clone <your-repo>
cd studymate-bot
make install
# or: python -m venv .venv && .venv/bin/pip install -r requirements.txt

# 2. Activate virtualenv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows

# 3. Configure
cp .env.example .env
nano .env

# 4. Setup database
createdb studymate
python manage.py migrate

# 5. Start Redis (in separate terminal)
redis-server

# 6. Run bot
python run_bot.py
```

---

## 📝 Required Configuration

Edit `.env` file:

```env
# REQUIRED - Get from @BotFather
BOT_TOKEN=8421924187:AAGeSJJWsO-GjUl9Cldf2CWnWX-XJOdXgrM

# REQUIRED - Generate random key
SECRET_KEY=django-insecure-xyz123...

# Optional
DEBUG=True
ADMIN_TELEGRAM_IDS=123456789
```

**Generate SECRET_KEY:**
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

---

## ✅ Verify Installation

```bash
# Check all services
make health

# View logs
make logs

# Check database
docker-compose exec postgres psql -U studymate -c "SELECT COUNT(*) FROM students_student;"

# Check Redis
docker-compose exec redis redis-cli PING
```

---

## 🎯 Next Steps

1. **Setup Mentors:**
   - Go to http://localhost:8000/admin (if DEBUG=True)
   - Create superuser: `python manage.py createsuperuser`
   - Add mentors with their Telegram IDs and group chat IDs

2. **Test Bot:**
   - Send `/start` to your bot in Telegram
   - Join mentor's group
   - Bot should recognize you as student

3. **Upload Materials:**
   - As mentor, use bot commands to upload materials
   - Students will see them in their bot

4. **Create Quiz:**
   - Upload quiz .txt file
   - Choose ranked/practice mode
   - Students can take the quiz

---

## 🔧 Common Commands

```bash
# Start bot
make start

# Stop bot
make stop

# Restart bot
make restart

# View logs
make logs

# Backup database
make backup

# Restore database
make restore

# Health check
make health

# Django shell
make shell

# Run migrations
make migrate
```

---

## 🐛 Troubleshooting

### Bot doesn't start

```bash
# Check logs
make logs

# Check BOT_TOKEN
docker-compose exec bot env | grep BOT_TOKEN

# Check services
docker-compose ps
```

### Redis connection failed

```bash
# Check Redis is running
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli PING

# Check REDIS_URL in .env
cat .env | grep REDIS_URL
```

### Database error

```bash
# Check PostgreSQL
docker-compose ps postgres

# Run migrations
docker-compose exec bot python manage.py migrate

# Check connection
docker-compose exec postgres pg_isready -U studymate
```

### Students can't access bot

- Verify mentor's `group_chat_id` is correct
- Student must be in the mentor's Telegram group
- Check bot has admin permissions in the group

---

## 📚 Documentation

- **Full deployment guide:** [DEPLOYMENT.md](DEPLOYMENT.md)
- **Production readiness:** [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md)
- **Project structure:** [CLAUDE.md](CLAUDE.md)
- **Scripts documentation:** [scripts/README.md](scripts/README.md)

---

## 🆘 Need Help?

1. Check logs: `make logs`
2. Run health check: `make health`
3. Check documentation
4. Open GitHub issue

---

## 🎉 Success!

If you see "Bot is running..." in logs, you're good to go!

Test by sending `/start` to your bot in Telegram.
