# Deployment Guide — StudyMate Bot

## 🚀 Quick Start (Docker Compose)

### Prerequisites
- Docker and Docker Compose installed
- Telegram bot token from @BotFather

### 1. Clone and Configure

```bash
git clone <your-repo>
cd studymate-bot
cp .env.example .env
```

### 2. Edit `.env` file

```env
# REQUIRED
BOT_TOKEN=your-bot-token-from-botfather
SECRET_KEY=your-random-secret-key
POSTGRES_PASSWORD=secure-db-password

# OPTIONAL (for production)
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
ADMIN_TELEGRAM_IDS=123456789,987654321
```

Generate SECRET_KEY:
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### 3. Start Services

```bash
docker-compose up -d
```

This will start:
- PostgreSQL database
- Redis for FSM storage
- Telegram bot

### 4. Check Logs

```bash
docker-compose logs -f bot
```

### 5. Stop Services

```bash
docker-compose down
```

---

## 🛠️ Manual Deployment (without Docker)

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis 7+

### 1. Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Setup PostgreSQL

```bash
createdb studymate
createuser studymate -P
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
```

### 4. Run Migrations

```bash
python manage.py migrate
```

### 5. Create Django Superuser (for admin panel)

```bash
python manage.py createsuperuser
```

### 6. Start Redis

```bash
redis-server
```

### 7. Start Bot

```bash
python run_bot.py
```

---

## 🔧 Production Setup

### Using systemd (Linux)

**Quick setup:**
```bash
# Copy service file
sudo cp scripts/studymate-bot.service /etc/systemd/system/

# Create user and directories
sudo useradd -r -s /bin/false studymate
sudo mkdir -p /opt/studymate-bot /var/log/studymate-bot
sudo chown -R studymate:studymate /opt/studymate-bot /var/log/studymate-bot

# Deploy bot to /opt/studymate-bot
sudo -u studymate git clone <repo> /opt/studymate-bot
cd /opt/studymate-bot
sudo -u studymate python -m venv .venv
sudo -u studymate .venv/bin/pip install -r requirements.txt

# Configure .env
sudo -u studymate cp .env.example .env
sudo -u studymate nano .env

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable studymate-bot
sudo systemctl start studymate-bot
```

**Manage service:**
```bash
# Check status
sudo systemctl status studymate-bot

# View logs
sudo journalctl -u studymate-bot -f

# Restart
sudo systemctl restart studymate-bot

# Stop
sudo systemctl stop studymate-bot
```

See `scripts/studymate-bot.service` for the full service file.

---

## 📊 Monitoring

### Check Bot Health

**Automated health check (recommended):**
```bash
./scripts/health_check.sh
```

This checks:
- All services status (postgres, redis, bot)
- Database connection and size
- Redis connection and memory
- Recent error logs
- Disk space

**Manual checks:**
```bash
# Check if bot is running
docker-compose ps

# Check logs
docker-compose logs -f bot

# Check Redis connection
docker-compose exec redis redis-cli ping

# Check PostgreSQL connection
docker-compose exec postgres pg_isready
```

**Setup monitoring cron:**
```bash
# Health check every 5 minutes
*/5 * * * * /path/to/studymate-bot/scripts/health_check.sh || echo "Health check failed!" | mail -s "Bot Alert" admin@example.com
```

### Log Files

Logs are stored in `logs/bot.log`:

```bash
tail -f logs/bot.log
```

---

## 🔄 Updates and Maintenance

### Update Bot

```bash
git pull
docker-compose down
docker-compose build
docker-compose up -d
```

### Database Backup

**Automated backup (recommended):**
```bash
# Run backup script
./scripts/backup.sh

# Setup daily automatic backups (cron)
crontab -e
# Add: 0 3 * * * /path/to/studymate-bot/scripts/backup.sh
```

**Manual backup:**
```bash
# Backup
docker-compose exec postgres pg_dump -U studymate studymate > backup_$(date +%Y%m%d).sql

# Restore from backup
./scripts/restore.sh backups/studymate_20260201_030000.sql.gz
```

**Backup location:** `backups/` directory (not in git)
**Retention:** 30 days by default (configurable via `BACKUP_RETENTION_DAYS`)

See `scripts/README.md` for detailed backup documentation.

### Cleanup Old Logs

```bash
# Remove logs older than 30 days
find logs/ -name "*.log" -mtime +30 -delete
```

---

## 🐛 Troubleshooting

### Bot doesn't start

1. Check BOT_TOKEN is set:
   ```bash
   docker-compose exec bot env | grep BOT_TOKEN
   ```

2. Check Redis connection:
   ```bash
   docker-compose exec bot python -c "import redis; r=redis.from_url('redis://redis:6379/0'); print(r.ping())"
   ```

3. Check database connection:
   ```bash
   docker-compose exec bot python manage.py check
   ```

### Students lose quiz progress

- Make sure Redis is running and USE_REDIS=true
- Check Redis data persistence:
  ```bash
  docker-compose exec redis redis-cli DBSIZE
  ```

### Bot crashes on error

- Check logs: `docker-compose logs -f bot`
- Verify ErrorHandlerMiddleware is registered
- Check admin notifications are configured (ADMIN_TELEGRAM_IDS)

### High memory usage

- Check for memory leaks in custom handlers
- Monitor with: `docker stats bot`
- Restart periodically if needed (systemd Restart=always helps)

---

## 🔐 Security Checklist

- [ ] SECRET_KEY is random and secure
- [ ] DEBUG=False in production
- [ ] ALLOWED_HOSTS is restricted
- [ ] PostgreSQL password is strong
- [ ] Redis is not exposed to internet
- [ ] Admin panel (/admin) is protected
- [ ] Logs don't contain sensitive data
- [ ] Regular database backups configured
- [ ] Bot token is kept secret

---

## 📈 Scaling

### Horizontal Scaling (Multiple Bot Instances)

**Note:** Telegram Bot API doesn't support multiple instances with polling.
Options:

1. **Use webhooks** instead of polling
2. **Use different bots** for different mentors
3. **Use single instance** with enough resources

### Vertical Scaling

Increase resources in docker-compose.yml:

```yaml
bot:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
```

---

## 📞 Support

For issues, check:
1. Logs: `docker-compose logs -f`
2. GitHub Issues: <your-repo-url>
3. Admin notifications (if configured)
