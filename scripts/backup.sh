#!/bin/bash
# =============================================================================
# Perun's BlackBook - Database Backup Script for Synology NAS
# =============================================================================
# Usage: ./backup.sh
#
# This script creates a PostgreSQL backup and manages retention.
# Configure as a scheduled task in Synology DSM:
#   Control Panel -> Task Scheduler -> Create -> Scheduled Task -> User-defined script
#   Run daily at a convenient time (e.g., 3:00 AM)
#
# Script location on NAS: /volume1/docker/blackbook/scripts/backup.sh

set -e

# Configuration
BACKUP_DIR="/volume1/docker/blackbook/backups"
CONTAINER_NAME="blackbook-db"
DB_USER="blackbook"
DB_NAME="perunsblackbook"
RETENTION_DAYS=7

# Create timestamp
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.sql"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

echo "=========================================="
echo "Perun's BlackBook Database Backup"
echo "Started: $(date)"
echo "=========================================="

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: Container $CONTAINER_NAME is not running!"
    exit 1
fi

# Create backup
echo "Creating backup: $BACKUP_FILE"
docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP_FILE"

# Check if backup was successful
if [ -f "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "Backup created successfully: $BACKUP_SIZE"
else
    echo "ERROR: Backup file is empty or missing!"
    exit 1
fi

# Compress backup
echo "Compressing backup..."
gzip "$BACKUP_FILE"
COMPRESSED_FILE="${BACKUP_FILE}.gz"
COMPRESSED_SIZE=$(du -h "$COMPRESSED_FILE" | cut -f1)
echo "Compressed size: $COMPRESSED_SIZE"

# Clean up old backups
echo "Cleaning up backups older than $RETENTION_DAYS days..."
DELETED_COUNT=$(find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete -print | wc -l)
echo "Deleted $DELETED_COUNT old backup(s)"

# List current backups
echo ""
echo "Current backups:"
ls -lh "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null || echo "No backups found"

echo ""
echo "=========================================="
echo "Backup completed: $(date)"
echo "=========================================="
