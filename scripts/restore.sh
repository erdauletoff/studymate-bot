#!/bin/bash
#
# Restore PostgreSQL backup for StudyMate Bot
# Usage: ./scripts/restore.sh [backup_file.sql.gz]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Source .env file if exists
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
fi

BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"

# Determine which backup to restore
if [ -z "$1" ]; then
    # Use latest backup
    BACKUP_FILE="$BACKUP_DIR/latest.sql.gz"
    if [ ! -f "$BACKUP_FILE" ]; then
        echo "ERROR: No latest backup found at $BACKUP_FILE"
        echo "Usage: $0 [backup_file.sql.gz]"
        exit 1
    fi
else
    BACKUP_FILE="$1"
    if [ ! -f "$BACKUP_FILE" ]; then
        echo "ERROR: Backup file not found: $BACKUP_FILE"
        exit 1
    fi
fi

echo "WARNING: This will restore database from: $BACKUP_FILE"
echo "Current database will be OVERWRITTEN!"
read -p "Are you sure? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo "Restoring database..."

# Decompress if needed
TEMP_FILE="$BACKUP_FILE"
if [[ "$BACKUP_FILE" == *.gz ]]; then
    TEMP_FILE="${BACKUP_FILE%.gz}"
    gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
fi

# Restore using docker-compose
cd "$PROJECT_DIR"

# Drop and recreate database
docker-compose exec -T postgres psql -U studymate -c "DROP DATABASE IF EXISTS studymate;"
docker-compose exec -T postgres psql -U studymate -c "CREATE DATABASE studymate;"

# Restore backup
cat "$TEMP_FILE" | docker-compose exec -T postgres psql -U studymate studymate

# Clean up temp file
if [[ "$BACKUP_FILE" == *.gz ]]; then
    rm -f "$TEMP_FILE"
fi

echo "Database restored successfully!"
echo "Restarting bot..."
docker-compose restart bot

exit 0
