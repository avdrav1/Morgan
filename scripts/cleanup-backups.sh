#!/bin/bash

################################################################################
# Backup Cleanup Script
# 
# This script enforces backup retention policies:
# - 7 daily backups
# - 4 weekly backups
# - 3 monthly backups
#
# Requirements: 10.3
################################################################################

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"

# Retention policies
DAILY_RETENTION=7
WEEKLY_RETENTION=4
MONTHLY_RETENTION=3

# Backup directories
DAILY_DIR="$BACKUP_DIR/daily"
WEEKLY_DIR="$BACKUP_DIR/weekly"
MONTHLY_DIR="$BACKUP_DIR/monthly"

# Logging
LOG_FILE="$BACKUP_DIR/backup.log"

################################################################################
# Functions
################################################################################

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cleanup_directory() {
    local dir="$1"
    local retention="$2"
    local backup_type="$3"
    
    if [ ! -d "$dir" ]; then
        log "Directory $dir does not exist, skipping cleanup"
        return 0
    fi
    
    log "Cleaning up $backup_type backups in $dir (retention: $retention)"
    
    # Count current backups
    local backup_count=$(find "$dir" -type f \( -name "*.sql.gz" -o -name "*.sql.gz.enc" \) | wc -l)
    log "Current $backup_type backup count: $backup_count"
    
    if [ "$backup_count" -le "$retention" ]; then
        log "No cleanup needed for $backup_type backups"
        return 0
    fi
    
    # Calculate how many backups to delete
    local delete_count=$((backup_count - retention))
    log "Deleting $delete_count old $backup_type backup(s)"
    
    # Find and delete oldest backups
    find "$dir" -type f \( -name "*.sql.gz" -o -name "*.sql.gz.enc" \) -printf '%T+ %p\n' | \
        sort | \
        head -n "$delete_count" | \
        cut -d' ' -f2- | \
        while IFS= read -r file; do
            log "Deleting old backup: $file"
            rm -f "$file"
        done
    
    # Verify cleanup
    local new_count=$(find "$dir" -type f \( -name "*.sql.gz" -o -name "*.sql.gz.enc" \) | wc -l)
    log "After cleanup: $new_count $backup_type backup(s) remaining"
}

cleanup_remote_backups() {
    local remote_path="$1"
    
    if [ -z "$remote_path" ] || [ ! -d "$remote_path" ]; then
        return 0
    fi
    
    log "Cleaning up remote backups at $remote_path"
    
    # Cleanup remote daily backups
    if [ -d "$remote_path/daily" ]; then
        cleanup_directory "$remote_path/daily" "$DAILY_RETENTION" "remote daily"
    fi
    
    # Cleanup remote weekly backups
    if [ -d "$remote_path/weekly" ]; then
        cleanup_directory "$remote_path/weekly" "$WEEKLY_RETENTION" "remote weekly"
    fi
    
    # Cleanup remote monthly backups
    if [ -d "$remote_path/monthly" ]; then
        cleanup_directory "$remote_path/monthly" "$MONTHLY_RETENTION" "remote monthly"
    fi
}

generate_cleanup_report() {
    log "=========================================="
    log "Backup Cleanup Report"
    log "=========================================="
    
    if [ -d "$DAILY_DIR" ]; then
        local daily_count=$(find "$DAILY_DIR" -type f \( -name "*.sql.gz" -o -name "*.sql.gz.enc" \) | wc -l)
        local daily_size=$(du -sh "$DAILY_DIR" 2>/dev/null | cut -f1)
        log "Daily backups: $daily_count files ($daily_size)"
    fi
    
    if [ -d "$WEEKLY_DIR" ]; then
        local weekly_count=$(find "$WEEKLY_DIR" -type f \( -name "*.sql.gz" -o -name "*.sql.gz.enc" \) | wc -l)
        local weekly_size=$(du -sh "$WEEKLY_DIR" 2>/dev/null | cut -f1)
        log "Weekly backups: $weekly_count files ($weekly_size)"
    fi
    
    if [ -d "$MONTHLY_DIR" ]; then
        local monthly_count=$(find "$MONTHLY_DIR" -type f \( -name "*.sql.gz" -o -name "*.sql.gz.enc" \) | wc -l)
        local monthly_size=$(du -sh "$MONTHLY_DIR" 2>/dev/null | cut -f1)
        log "Monthly backups: $monthly_count files ($monthly_size)"
    fi
    
    local total_size=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
    log "Total backup size: $total_size"
    log "=========================================="
}

################################################################################
# Main execution
################################################################################

main() {
    log "Starting backup cleanup process"
    
    # Create backup directories if they don't exist
    mkdir -p "$DAILY_DIR" "$WEEKLY_DIR" "$MONTHLY_DIR"
    
    # Cleanup local backups
    cleanup_directory "$DAILY_DIR" "$DAILY_RETENTION" "daily"
    cleanup_directory "$WEEKLY_DIR" "$WEEKLY_RETENTION" "weekly"
    cleanup_directory "$MONTHLY_DIR" "$MONTHLY_RETENTION" "monthly"
    
    # Cleanup remote backups if configured
    if [ -n "${REMOTE_BACKUP_PATH:-}" ]; then
        cleanup_remote_backups "$REMOTE_BACKUP_PATH"
    fi
    
    # Generate report
    generate_cleanup_report
    
    log "Backup cleanup completed successfully"
}

# Run main function
main "$@"
