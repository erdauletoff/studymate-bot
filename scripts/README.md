# Scripts Directory

Utility scripts for StudyMate Bot deployment and maintenance.

## Available Scripts

### 📦 backup.sh
Automated PostgreSQL backup script.

**Usage:**
```bash
./scripts/backup.sh
```

**Features:**
- Creates compressed backup (.sql.gz)
- Maintains retention policy (default: 30 days)
- Logs all operations
- Optional Telegram notification to admin
- Works with docker-compose or direct PostgreSQL connection

**Cron Setup:**
```bash
# Daily backup at 3 AM
0 3 * * * /opt/studymate-bot/scripts/backup.sh
```

**Environment Variables:**
- `BACKUP_DIR`: Backup directory (default: ./backups)
- `BACKUP_RETENTION_DAYS`: Keep backups for N days (default: 30)

---

### 🔄 restore.sh
Restore database from backup.

**Usage:**
```bash
# Restore from latest backup
./scripts/restore.sh

# Restore from specific backup
./scripts/restore.sh backups/studymate_20260201_030000.sql.gz
```

**Warning:** This will overwrite current database!

---

### 🏥 health_check.sh
Check bot and services health.

**Usage:**
```bash
./scripts/health_check.sh
```

**Checks:**
- Docker services status (postgres, redis, bot)
- PostgreSQL connection and database size
- Redis connection and memory usage
- Recent error logs
- Disk space usage

**Exit codes:**
- 0: All checks passed
- 1: One or more checks failed

**Monitoring Setup:**
```bash
# Check every 5 minutes
*/5 * * * * /opt/studymate-bot/scripts/health_check.sh || /opt/studymate-bot/scripts/alert_admin.sh
```

---

### ⚙️ studymate-bot.service
Systemd service file for production deployment.

**Installation:**
```bash
# Copy service file
sudo cp scripts/studymate-bot.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable studymate-bot

# Start service
sudo systemctl start studymate-bot

# Check status
sudo systemctl status studymate-bot

# View logs
sudo journalctl -u studymate-bot -f
```

**Prerequisites:**
1. Create user: `sudo useradd -r -s /bin/false studymate`
2. Install bot to: `/opt/studymate-bot`
3. Create log directory: `sudo mkdir -p /var/log/studymate-bot`
4. Set permissions: `sudo chown -R studymate:studymate /opt/studymate-bot /var/log/studymate-bot`

---

## Setup Instructions

### Make scripts executable

```bash
chmod +x scripts/*.sh
```

### Create required directories

```bash
mkdir -p backups logs
```

### Configure environment

All scripts use `.env` file from project root. Ensure it's properly configured.

---

## Troubleshooting

### Backup fails
- Check PostgreSQL is running: `docker-compose ps postgres`
- Check disk space: `df -h`
- Check permissions: `ls -la backups/`
- View logs: `cat backups/backup.log`

### Health check fails
- Check all services: `docker-compose ps`
- Check logs: `docker-compose logs`
- Check disk space: `df -h`

### Systemd service issues
- Check service status: `sudo systemctl status studymate-bot`
- View logs: `sudo journalctl -u studymate-bot -n 100`
- Check file permissions: `ls -la /opt/studymate-bot`
- Verify .env file exists: `ls -la /opt/studymate-bot/.env`

---

## Maintenance

### Cleanup old backups manually
```bash
find backups/ -name "studymate_*.sql.gz" -mtime +30 -delete
```

### Test restore process
```bash
# Create test backup
./scripts/backup.sh

# Test restore (on staging only!)
./scripts/restore.sh
```

### Monitor backup size
```bash
du -sh backups/
ls -lh backups/ | tail
```
