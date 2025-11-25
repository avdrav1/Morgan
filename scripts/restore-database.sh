#!/bin/bash

################################################################################
# Database Restore Script
# 
# This script restores a PostgreSQL database from a backup file
# Supports compressed and encrypted backups
#
# Usage: ./restore-database.sh <backup_file>
################################################################################

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Database configuration (from environment or .env file)
if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
fi

DB_CONTAINER="${DB_CONTAINER:-postgres}"
DB_NAME="${POSTGRES_DB:-accountability_db}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_PASSWORD="${POSTGRES_PASSWORD}"

# Encryption configuration
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"

# Logging
LOG_FILE="$PROJECT_ROOT/backups/restore.log"

################################################################################
# Functions
################################################################################

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "$LOG_FILE" >&2
}

usage() {
    cat << EOF
Usage: $0 <backup_file>

Restore a PostgreSQL database from a backup file.

Arguments:
  backup_file    Path to the backup file (.sql, .sql.gz, or .sql.gz.enc)

Examples:
  $0 backups/daily/accountability_db_daily_20240101_120000.sql.gz
  $0 backups/weekly/accountability_db_weekly_20240101_120000.sql.gz.enc

Environment Variables:
  DB_CONTAINER           Docker container name (default: postgres)
  POSTGRES_DB            Database name (default: accountability_db)
  POSTGRES_USER          Database user (default: postgres)
  BACKUP_ENCRYPTION_KEY  Encryption key for encrypted backups

EOF
    exit 1
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

confirm_restore() {
    local backup_file="$1"
    
    echo ""
    echo "=========================================="
    echo "WARNING: Database Restore Operation"
    echo "=========================================="
    echo "This will REPLACE the current database with the backup:"
    echo "  Backup file: $backup_file"
    echo "  Database: $DB_NAME"
    echo "  Container: $DB_CONTAINER"
    echo ""
    echo "All current data will be LOST!"
    echo "=========================================="
    echo ""
    
    read -p "Are you sure you want to continue? (yes/no): " -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log "Restore cancelled by user"
        exit 0
    fi
}

restore_backup() {
    local backup_file="$1"
    local temp_file="/tmp/restore_$(date +%s).sql"
    
    log "Starting restore from: $backup_file"
    
    # Decrypt if encrypted
    if [[ "$backup_file" == *.enc ]]; then
        log "Decrypting backup..."
        if [ -z "$ENCRYPTION_KEY" ]; then
            error "Backup is encrypted but BACKUP_ENCRYPTION_KEY is not set"
            return 1
        fi
        
        local decrypted_file="${backup_file%.enc}"
        if openssl enc -aes-256-cbc -d -in "$backup_file" -out "$decrypted_file" -k "$ENCRYPTION_KEY"; then
            log "Backup decrypted successfully"
            backup_file="$decrypted_file"
        else
            error "Failed to decrypt backup"
            return 1
        fi
    fi
    
    # Decompress if compressed
    if [[ "$backup_file" == *.gz ]]; then
        log "Decompressing backup..."
        if gunzip -c "$backup_file" > "$temp_file"; then
            log "Backup decompressed successfully"
        else
            error "Failed to decompress backup"
            rm -f "$temp_file"
            return 1
        fi
    else
        cp "$backup_file" "$temp_file"
    fi
    
    # Restore to database
    log "Restoring database..."
    if docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" < "$temp_file"; then
        log "Database restored successfully"
        rm -f "$temp_file"
        return 0
    else
        error "Failed to restore database"
        rm -f "$temp_file"
        return 1
    fi
}

verify_restore() {
    log "Verifying database restore..."
    
    # Check if database is accessible
    if docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" >/dev/null 2>&1; then
        log "Database is accessible"
    else
        error "Database is not accessible after restore"
        return 1
    fi
    
    # Get table count
    local table_count=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
    log "Tables in database: $table_count"
    
    log "Restore verification completed"
    return 0
}

################################################################################
# Main execution
################################################################################

main() {
    # Check arguments
    if [ $# -ne 1 ]; then
        usage
    fi
    
    local backup_file="$1"
    
    # Check if backup file exists
    if [ ! -f "$backup_file" ]; then
        error "Backup file not found: $backup_file"
        exit 1
    fi
    
    log "=========================================="
    log "Starting database restore process"
    log "=========================================="
    
    # Check prerequisites
    if ! check_prerequisites; then
        error "Prerequisites check failed"
        exit 1
    fi
    
    # Confirm restore operation
    confirm_restore "$backup_file"
    
    # Perform restore
    if restore_backup "$backup_file"; then
        log "Restore completed successfully"
        
        # Verify restore
        if verify_restore; then
            log "=========================================="
            log "Database restore completed and verified"
            log "=========================================="
            exit 0
        else
            error "Restore verification failed"
            exit 1
        fi
    else
        error "Restore failed"
        log "=========================================="
        log "Database restore failed"
        log "=========================================="
        exit 1
    fi
}

# Run main function
main "$@"
