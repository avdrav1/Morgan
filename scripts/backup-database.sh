#!/bin/bash

################################################################################
# Database Backup Script
# 
# This script creates compressed and encrypted backups of the PostgreSQL database
# with support for retention policies (7 daily, 4 weekly, 3 monthly)
#
# Requirements: 10.1, 10.2, 10.3
################################################################################

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE=$(date +%Y%m%d)
DAY_OF_WEEK=$(date +%u)  # 1-7 (Monday-Sunday)
DAY_OF_MONTH=$(date +%d)

# Backup types
DAILY_DIR="$BACKUP_DIR/daily"
WEEKLY_DIR="$BACKUP_DIR/weekly"
MONTHLY_DIR="$BACKUP_DIR/monthly"

# Database configuration (from environment or .env file)
if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
fi

DB_CONTAINER="${DB_CONTAINER:-postgres}"
DB_NAME="${POSTGRES_DB:-accountability_db}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_PASSWORD="${POSTGRES_PASSWORD}"

# Encryption configuration (optional)
ENCRYPT_BACKUPS="${ENCRYPT_BACKUPS:-false}"
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"

# Remote backup configuration (optional)
REMOTE_BACKUP="${REMOTE_BACKUP:-false}"
REMOTE_BACKUP_PATH="${REMOTE_BACKUP_PATH:-}"

# Notification configuration (optional)
NOTIFY_ON_FAILURE="${NOTIFY_ON_FAILURE:-false}"
NOTIFICATION_EMAIL="${NOTIFICATION_EMAIL:-}"

# Logging
LOG_FILE="$BACKUP_DIR/backup.log"

################################################################################
# Functions
################################################################################

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "$LOG_FILE" >&2
}

send_notification() {
    local subject="$1"
    local message="$2"
    
    if [ "$NOTIFY_ON_FAILURE" = "true" ] && [ -n "$NOTIFICATION_EMAIL" ]; then
        echo "$message" | mail -s "$subject" "$NOTIFICATION_EMAIL" 2>/dev/null || true
    fi
}

check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if Docker is running
    if ! docker ps >/dev/null 2>&1; then
        error "Docker is not running"
        return 1
    fi
    
    # Check if database container exists
    if ! docker ps -a --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
        error "Database container '$DB_CONTAINER' not found"
        return 1
    fi
    
    # Check if database container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
        error "Database container '$DB_CONTAINER' is not running"
        return 1
    fi
    
    log "Prerequisites check passed"
    return 0
}

create_backup_directories() {
    log "Creating backup directories..."
    mkdir -p "$DAILY_DIR" "$WEEKLY_DIR" "$MONTHLY_DIR"
}

create_backup() {
    local backup_type="$1"
    local backup_dir="$2"
    local backup_file="$backup_dir/${DB_NAME}_${backup_type}_${TIMESTAMP}.sql"
    
    log "Creating $backup_type backup: $backup_file"
    
    # Create SQL dump using pg_dump
    if docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists > "$backup_file"; then
        log "Database dump created successfully"
    else
        error "Failed to create database dump"
        return 1
    fi
    
    # Compress the backup
    log "Compressing backup..."
    if gzip -f "$backup_file"; then
        backup_file="${backup_file}.gz"
        log "Backup compressed: $backup_file"
    else
        error "Failed to compress backup"
        return 1
    fi
    
    # Encrypt the backup if enabled
    if [ "$ENCRYPT_BACKUPS" = "true" ] && [ -n "$ENCRYPTION_KEY" ]; then
        log "Encrypting backup..."
        if openssl enc -aes-256-cbc -salt -in "$backup_file" -out "${backup_file}.enc" -k "$ENCRYPTION_KEY"; then
            rm "$backup_file"
            backup_file="${backup_file}.enc"
            log "Backup encrypted: $backup_file"
        else
            error "Failed to encrypt backup"
            return 1
        fi
    fi
    
    # Get backup size
    local backup_size=$(du -h "$backup_file" | cut -f1)
    log "Backup created successfully: $backup_file (Size: $backup_size)"
    
    # Upload to remote storage if enabled
    if [ "$REMOTE_BACKUP" = "true" ] && [ -n "$REMOTE_BACKUP_PATH" ]; then
        upload_to_remote "$backup_file" "$backup_type"
    fi
    
    echo "$backup_file"
}

upload_to_remote() {
    local backup_file="$1"
    local backup_type="$2"
    
    log "Uploading backup to remote storage..."
    
    # This is a placeholder - implement based on your remote storage solution
    # Examples:
    # - AWS S3: aws s3 cp "$backup_file" "s3://$REMOTE_BACKUP_PATH/$backup_type/"
    # - rsync: rsync -avz "$backup_file" "$REMOTE_BACKUP_PATH/$backup_type/"
    # - rclone: rclone copy "$backup_file" "$REMOTE_BACKUP_PATH/$backup_type/"
    
    if [ -d "$REMOTE_BACKUP_PATH" ]; then
        cp "$backup_file" "$REMOTE_BACKUP_PATH/$backup_type/" && \
            log "Backup uploaded to remote storage successfully" || \
            error "Failed to upload backup to remote storage"
    else
        log "Remote backup path not configured or not accessible"
    fi
}

determine_backup_type() {
    # Monthly backup on the 1st of each month
    if [ "$DAY_OF_MONTH" = "01" ]; then
        echo "monthly"
        return
    fi
    
    # Weekly backup on Sundays (day 7)
    if [ "$DAY_OF_WEEK" = "7" ]; then
        echo "weekly"
        return
    fi
    
    # Daily backup for all other days
    echo "daily"
}

################################################################################
# Main execution
################################################################################

main() {
    log "=========================================="
    log "Starting database backup process"
    log "=========================================="
    
    # Check prerequisites
    if ! check_prerequisites; then
        error "Prerequisites check failed"
        send_notification "Backup Failed" "Prerequisites check failed for database backup"
        exit 1
    fi
    
    # Create backup directories
    create_backup_directories
    
    # Determine backup type based on date
    BACKUP_TYPE=$(determine_backup_type)
    log "Backup type: $BACKUP_TYPE"
    
    # Select appropriate directory
    case "$BACKUP_TYPE" in
        daily)
            BACKUP_TARGET_DIR="$DAILY_DIR"
            ;;
        weekly)
            BACKUP_TARGET_DIR="$WEEKLY_DIR"
            ;;
        monthly)
            BACKUP_TARGET_DIR="$MONTHLY_DIR"
            ;;
    esac
    
    # Create the backup
    if BACKUP_FILE=$(create_backup "$BACKUP_TYPE" "$BACKUP_TARGET_DIR"); then
        log "Backup completed successfully: $BACKUP_FILE"
        
        # Run cleanup to enforce retention policy
        "$SCRIPT_DIR/cleanup-backups.sh"
        
        log "=========================================="
        log "Backup process completed successfully"
        log "=========================================="
        exit 0
    else
        error "Backup failed"
        send_notification "Backup Failed" "Database backup failed. Check logs at $LOG_FILE"
        log "=========================================="
        log "Backup process failed"
        log "=========================================="
        exit 1
    fi
}

# Run main function
main "$@"
