#!/bin/bash

#######################################
# Log Rotation Script for Production
#######################################
# This script rotates application logs stored in Docker volumes
# and cleans up old log files based on retention policies.
#
# Usage: ./scripts/rotate-logs.sh
#
# Retention Policy:
# - Keep logs for 30 days
# - Compress logs older than 7 days
# - Delete logs older than 30 days

set -e

# Configuration
LOG_VOLUME="accountability-app-logs"
RETENTION_DAYS=30
COMPRESS_AFTER_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "Log Rotation Script"
echo "========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Check if log volume exists
if ! docker volume inspect "$LOG_VOLUME" > /dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Log volume '$LOG_VOLUME' does not exist${NC}"
    echo "Creating log volume..."
    docker volume create "$LOG_VOLUME"
fi

echo "Rotating logs in volume: $LOG_VOLUME"
echo ""

# Create a temporary container to access the volume
TEMP_CONTAINER="log-rotation-temp-$TIMESTAMP"

echo "Creating temporary container to access logs..."
docker run -d \
    --name "$TEMP_CONTAINER" \
    --mount source="$LOG_VOLUME",target=/var/log/app \
    alpine:latest \
    sleep 300

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Cleaning up temporary container..."
    docker rm -f "$TEMP_CONTAINER" > /dev/null 2>&1 || true
}
trap cleanup EXIT

# Compress logs older than COMPRESS_AFTER_DAYS
echo "Compressing logs older than $COMPRESS_AFTER_DAYS days..."
docker exec "$TEMP_CONTAINER" sh -c "
    find /var/log/app -type f -name '*.log' -mtime +$COMPRESS_AFTER_DAYS ! -name '*.gz' -exec gzip {} \; 2>/dev/null || true
"

# Delete logs older than RETENTION_DAYS
echo "Deleting logs older than $RETENTION_DAYS days..."
DELETED_COUNT=$(docker exec "$TEMP_CONTAINER" sh -c "
    find /var/log/app -type f \( -name '*.log' -o -name '*.gz' \) -mtime +$RETENTION_DAYS -delete -print | wc -l
")

# Get current log statistics
echo ""
echo "Current log statistics:"
docker exec "$TEMP_CONTAINER" sh -c "
    echo 'Total log files:'
    find /var/log/app -type f \( -name '*.log' -o -name '*.gz' \) | wc -l
    echo ''
    echo 'Total log size:'
    du -sh /var/log/app 2>/dev/null || echo '0'
    echo ''
    echo 'Breakdown by type:'
    echo '  Uncompressed logs:'
    find /var/log/app -type f -name '*.log' | wc -l
    echo '  Compressed logs:'
    find /var/log/app -type f -name '*.gz' | wc -l
"

echo ""
echo -e "${GREEN}Log rotation completed successfully${NC}"
echo "Deleted $DELETED_COUNT old log files"
echo ""

# Optional: Show recent log files
echo "Recent log files:"
docker exec "$TEMP_CONTAINER" sh -c "
    find /var/log/app -type f \( -name '*.log' -o -name '*.gz' \) -mtime -7 -ls 2>/dev/null | head -20 || echo 'No recent logs found'
"

echo ""
echo "========================================="
echo "Log rotation completed"
echo "========================================="
