#!/bin/bash

################################################################################
# Backup Cron Setup Script
# 
# This script configures automated daily backups via cron
# Backups run at 2:00 AM daily by default
################################################################################

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_SCRIPT="$SCRIPT_DIR/backup-database.sh"

# Default backup time (2:00 AM daily)
BACKUP_HOUR="${BACKUP_HOUR:-2}"
BACKUP_MINUTE="${BACKUP_MINUTE:-0}"

# Cron job identifier
CRON_IDENTIFIER="# Proactive Accountability Assistant - Database Backup"

################################################################################
# Functions
################################################################################

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
}

check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if backup script exists
    if [ ! -f "$BACKUP_SCRIPT" ]; then
        error "Backup script not found: $BACKUP_SCRIPT"
        return 1
    fi
    
    # Make backup script executable
    chmod +x "$BACKUP_SCRIPT"
    chmod +x "$SCRIPT_DIR/cleanup-backups.sh"
    chmod +x "$SCRIPT_DIR/restore-database.sh"
    
    log "Prerequisites check passed"
    return 0
}

remove_existing_cron() {
    log "Removing existing backup cron jobs..."
    
    # Get current crontab
    local current_cron=$(crontab -l 2>/dev/null || true)
    
    # Remove existing backup jobs
    local new_cron=$(echo "$current_cron" | grep -v "$CRON_IDENTIFIER" | grep -v "$BACKUP_SCRIPT" || true)
    
    # Update crontab
    echo "$new_cron" | crontab -
    
    log "Existing backup cron jobs removed"
}

add_backup_cron() {
    log "Adding backup cron job..."
    
    # Get current crontab
    local current_cron=$(crontab -l 2>/dev/null || true)
    
    # Create new cron entry
    local cron_entry="$BACKUP_MINUTE $BACKUP_HOUR * * * $BACKUP_SCRIPT >> $PROJECT_ROOT/backups/backup.log 2>&1"
    
    # Add new cron job
    (
        echo "$current_cron"
        echo "$CRON_IDENTIFIER"
        echo "$cron_entry"
    ) | crontab -
    
    log "Backup cron job added successfully"
    log "Backups will run daily at $BACKUP_HOUR:$(printf '%02d' $BACKUP_MINUTE)"
}

verify_cron() {
    log "Verifying cron job installation..."
    
    if crontab -l | grep -q "$BACKUP_SCRIPT"; then
        log "Cron job verified successfully"
        return 0
    else
        error "Cron job verification failed"
        return 1
    fi
}

display_cron_info() {
    echo ""
    echo "=========================================="
    echo "Backup Cron Job Configuration"
    echo "=========================================="
    echo "Schedule: Daily at $BACKUP_HOUR:$(printf '%02d' $BACKUP_MINUTE)"
    echo "Script: $BACKUP_SCRIPT"
    echo "Log: $PROJECT_ROOT/backups/backup.log"
    echo ""
    echo "Current cron jobs:"
    crontab -l | grep -A1 "$CRON_IDENTIFIER" || echo "No backup cron jobs found"
    echo "=========================================="
    echo ""
}

test_backup() {
    log "Running test backup..."
    
    if "$BACKUP_SCRIPT"; then
        log "Test backup completed successfully"
        return 0
    else
        error "Test backup failed"
        return 1
    fi
}

################################################################################
# Main execution
################################################################################

main() {
    echo "=========================================="
    echo "Setting up automated database backups"
    echo "=========================================="
    
    # Check prerequisites
    if ! check_prerequisites; then
        error "Prerequisites check failed"
        exit 1
    fi
    
    # Remove existing cron jobs
    remove_existing_cron
    
    # Add new cron job
    add_backup_cron
    
    # Verify installation
    if ! verify_cron; then
        error "Cron job installation failed"
        exit 1
    fi
    
    # Display configuration
    display_cron_info
    
    # Ask if user wants to run a test backup
    read -p "Would you like to run a test backup now? (yes/no): " -r
    echo
    
    if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        if test_backup; then
            echo ""
            echo "=========================================="
            echo "Setup completed successfully!"
            echo "=========================================="
            echo "Automated backups are now configured."
            echo "Check $PROJECT_ROOT/backups/ for backup files."
            echo "=========================================="
        else
            error "Test backup failed. Please check the configuration."
            exit 1
        fi
    else
        echo ""
        echo "=========================================="
        echo "Setup completed successfully!"
        echo "=========================================="
        echo "Automated backups are now configured."
        echo "The first backup will run at $BACKUP_HOUR:$(printf '%02d' $BACKUP_MINUTE)."
        echo "=========================================="
    fi
}

# Run main function
main "$@"
