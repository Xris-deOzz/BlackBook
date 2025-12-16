#!/bin/bash
# Import BlackBook database from Windows export
# Usage: ./import_database.sh /path/to/blackbook_export_XXXXXXXX.sql

set -e

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.sql>"
    echo "Example: $0 /volume1/docker/blackbook/backups/blackbook_export_20251216.sql"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: File not found: $BACKUP_FILE"
    exit 1
fi

echo ""
echo "========================================"
echo " BlackBook Database Import"
echo "========================================"
echo ""
echo "Backup file: $BACKUP_FILE"
echo ""

# Check if containers are running
if ! docker ps | grep -q blackbook-db; then
    echo "Error: blackbook-db container is not running"
    echo "Start containers first: docker-compose -f docker-compose.prod.yml up -d"
    exit 1
fi

# Confirm before proceeding
echo "WARNING: This will REPLACE all existing data in the database!"
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Step 1: Copying backup file to container..."
docker cp "$BACKUP_FILE" blackbook-db:/tmp/import.sql

echo "Step 2: Dropping existing data..."
docker exec -it blackbook-db psql -U blackbook -d perunsblackbook -c "
    DROP SCHEMA public CASCADE;
    CREATE SCHEMA public;
    GRANT ALL ON SCHEMA public TO blackbook;
    GRANT ALL ON SCHEMA public TO public;
"

echo "Step 3: Importing database..."
docker exec -it blackbook-db psql -U blackbook -d perunsblackbook -f /tmp/import.sql

echo "Step 4: Cleaning up..."
docker exec -it blackbook-db rm /tmp/import.sql

echo ""
echo "========================================"
echo " Import Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Run migrations: docker exec -it blackbook-app alembic upgrade head"
echo "2. Restart app: docker-compose -f docker-compose.prod.yml restart app"
echo "3. Test: curl http://localhost:8000/health"
echo ""
