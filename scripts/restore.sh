#!/bin/bash
# =============================================================================
# Perun's BlackBook - Database Restore Script for Synology NAS
# =============================================================================
# Usage: ./restore.sh [backup_file.sql.gz]
#
# If no backup file is specified, the script will list available backups
# and prompt you to choose one.

set -e

# Configuration
BACKUP_DIR="/volume1/docker/blackbook/backups"
CONTAINER_NAME="blackbook-db"
DB_USER="blackbook"
DB_NAME="perunsblackbook"

echo "=========================================="
echo "Perun's BlackBook Database Restore"
echo "Started: $(date)"
echo "=========================================="

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: Container $CONTAINER_NAME is not running!"
    exit 1
fi

# Get backup file
BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Available backups:"
    echo ""
    ls -lht "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null || { echo "No backups found!"; exit 1; }
    echo ""
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 /volume1/docker/blackbook/backups/backup_20250101_030000.sql.gz"
    exit 1
fi

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Confirm restore
echo ""
echo "WARNING: This will REPLACE ALL DATA in the database!"
echo "Backup file: $BACKUP_FILE"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

# Create a backup of current data first
echo ""
echo "Creating backup of current data before restore..."
CURRENT_BACKUP="$BACKUP_DIR/pre_restore_$(date +%Y%m%d_%H%M%S).sql"
docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" "$DB_NAME" > "$CURRENT_BACKUP"
gzip "$CURRENT_BACKUP"
echo "Current data backed up to: ${CURRENT_BACKUP}.gz"

# Decompress if needed
RESTORE_FILE="$BACKUP_FILE"
if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo "Decompressing backup..."
    RESTORE_FILE="/tmp/restore_$(date +%s).sql"
    gunzip -c "$BACKUP_FILE" > "$RESTORE_FILE"
fi

# Perform restore
echo "Restoring database..."

# Drop and recreate database
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

# Restore data
cat "$RESTORE_FILE" | docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME"

# Clean up temp file
if [[ "$RESTORE_FILE" == /tmp/* ]]; then
    rm "$RESTORE_FILE"
fi

echo ""
echo "=========================================="
echo "Restore completed: $(date)"
echo "=========================================="
echo ""
echo "IMPORTANT: Restart the application container to ensure proper connection:"
echo "  docker restart blackbook-app"
