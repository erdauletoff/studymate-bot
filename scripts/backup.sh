#!/bin/bash
#
# Automated PostgreSQL backup script for StudyMate Bot
# Usage: ./scripts/backup.sh
# Add to crontab: 0 3 * * * /path/to/studymate-bot/scripts/backup.sh
#

set -e

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Source .env file if exists
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
fi

# Configuration
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/studymate_$TIMESTAMP.sql"
LATEST_LINK="$BACKUP_DIR/latest.sql"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Log file
LOG_FILE="$BACKUP_DIR/backup.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting backup..."

# Parse DATABASE_URL or use docker-compose
if [ ! -z "$DATABASE_URL" ]; then
    log "Using DATABASE_URL for backup"
    # Extract database connection details from DATABASE_URL
    # Format: postgresql://user:password@host:port/dbname

    DB_USER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    DB_PASS=$(echo $DATABASE_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')

    export PGPASSWORD="$DB_PASS"
    pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_FILE"
else
    log "Using docker-compose for backup"
    # Use docker-compose exec
    cd "$PROJECT_DIR"
    docker-compose exec -T postgres pg_dump -U studymate studymate > "$BACKUP_FILE"
fi

# Check if backup was successful
if [ $? -eq 0 ] && [ -s "$BACKUP_FILE" ]; then
    log "Backup created successfully: $BACKUP_FILE"

    # Compress backup
    gzip "$BACKUP_FILE"
    BACKUP_FILE="$BACKUP_FILE.gz"

    # Update latest symlink
    ln -sf "$BACKUP_FILE" "$LATEST_LINK.gz"

    # Get backup size
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "Backup size: $BACKUP_SIZE"
else
    log "ERROR: Backup failed!"
    exit 1
fi

# Clean up old backups
log "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "studymate_*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete

REMAINING_BACKUPS=$(find "$BACKUP_DIR" -name "studymate_*.sql.gz" -type f | wc -l)
log "Cleanup complete. Remaining backups: $REMAINING_BACKUPS"

# Calculate total backup size
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "Total backup directory size: $TOTAL_SIZE"

log "Backup completed successfully!"

# Optional: Send notification to admin
if [ ! -z "$ADMIN_TELEGRAM_IDS" ] && [ ! -z "$BOT_TOKEN" ]; then
    ADMIN_ID=$(echo $ADMIN_TELEGRAM_IDS | cut -d',' -f1)
    MESSAGE="✅ Database backup completed\n\nFile: $(basename $BACKUP_FILE)\nSize: $BACKUP_SIZE\nTime: $(date '+%Y-%m-%d %H:%M:%S')"

    curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
        -d chat_id="$ADMIN_ID" \
        -d text="$MESSAGE" \
        -d parse_mode="HTML" > /dev/null
fi

exit 0
