#!/bin/bash
# Database initialization script with migration locking
# This script ensures migrations run safely in production environments

set -e  # Exit on error

# Configuration
MAX_RETRIES=30
RETRY_INTERVAL=2
LOCK_TIMEOUT=300  # 5 minutes
MIGRATION_LOCK_KEY="alembic_migration_lock"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Wait for database to be ready
wait_for_database() {
    log_info "Waiting for database to be ready..."
    
    local retries=0
    while [ $retries -lt $MAX_RETRIES ]; do
        if pg_isready -h "${DB_HOST:-postgres}" -p "${DB_PORT:-5432}" -U "${POSTGRES_USER}" > /dev/null 2>&1; then
            log_info "Database is ready!"
            return 0
        fi
        
        retries=$((retries + 1))
        log_warn "Database not ready yet (attempt $retries/$MAX_RETRIES). Retrying in ${RETRY_INTERVAL}s..."
        sleep $RETRY_INTERVAL
    done
    
    log_error "Database failed to become ready after $MAX_RETRIES attempts"
    return 1
}

# Acquire migration lock using PostgreSQL advisory lock
acquire_migration_lock() {
    log_info "Attempting to acquire migration lock..."
    
    # Use PostgreSQL advisory lock with timeout
    # Lock ID is a hash of the lock key
    local lock_id=$(echo -n "$MIGRATION_LOCK_KEY" | cksum | cut -d' ' -f1)
    
    local start_time=$(date +%s)
    local timeout_time=$((start_time + LOCK_TIMEOUT))
    
    while true; do
        # Try to acquire the lock (non-blocking)
        if psql "${DATABASE_URL}" -t -c "SELECT pg_try_advisory_lock($lock_id);" | grep -q 't'; then
            log_info "Migration lock acquired successfully"
            echo "$lock_id"
            return 0
        fi
        
        local current_time=$(date +%s)
        if [ $current_time -ge $timeout_time ]; then
            log_error "Failed to acquire migration lock within ${LOCK_TIMEOUT}s timeout"
            return 1
        fi
        
        log_warn "Migration lock held by another process. Waiting..."
        sleep 2
    done
}

# Release migration lock
release_migration_lock() {
    local lock_id=$1
    
    if [ -n "$lock_id" ]; then
        log_info "Releasing migration lock..."
        psql "${DATABASE_URL}" -t -c "SELECT pg_advisory_unlock($lock_id);" > /dev/null 2>&1 || true
        log_info "Migration lock released"
    fi
}

# Check if database is initialized
check_database_initialized() {
    log_info "Checking if database is initialized..."
    
    # Check if alembic_version table exists
    if psql "${DATABASE_URL}" -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alembic_version');" | grep -q 't'; then
        log_info "Database is already initialized"
        return 0
    else
        log_info "Database is not initialized"
        return 1
    fi
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    
    # Get current migration version
    local current_version=$(alembic current 2>/dev/null | grep -oP '(?<=\()[a-f0-9]+(?=\))' || echo "none")
    log_info "Current migration version: $current_version"
    
    # Run migrations
    if alembic upgrade head; then
        local new_version=$(alembic current 2>/dev/null | grep -oP '(?<=\()[a-f0-9]+(?=\))' || echo "unknown")
        log_info "Migrations completed successfully. New version: $new_version"
        return 0
    else
        log_error "Migration failed!"
        return 1
    fi
}

# Verify database schema
verify_database_schema() {
    log_info "Verifying database schema..."
    
    # Check that essential tables exist
    local required_tables=("users" "projects" "tasks" "check_ins" "alembic_version")
    
    for table in "${required_tables[@]}"; do
        if ! psql "${DATABASE_URL}" -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '$table');" | grep -q 't'; then
            log_error "Required table '$table' not found in database"
            return 1
        fi
    done
    
    log_info "Database schema verification passed"
    return 0
}

# Main initialization function
main() {
    log_info "Starting database initialization..."
    log_info "Environment: ${ENVIRONMENT:-development}"
    
    local lock_id=""
    local exit_code=0
    
    # Trap to ensure lock is released on exit
    trap 'release_migration_lock "$lock_id"' EXIT
    
    # Step 1: Wait for database
    if ! wait_for_database; then
        log_error "Database initialization failed: database not available"
        exit 1
    fi
    
    # Step 2: Acquire migration lock
    lock_id=$(acquire_migration_lock)
    if [ $? -ne 0 ]; then
        log_error "Database initialization failed: could not acquire lock"
        exit 1
    fi
    
    # Step 3: Check if database is initialized
    if check_database_initialized; then
        log_info "Database already initialized, checking for pending migrations..."
    else
        log_info "Initializing database for the first time..."
    fi
    
    # Step 4: Run migrations
    if ! run_migrations; then
        log_error "Database initialization failed: migration error"
        exit_code=1
    fi
    
    # Step 5: Verify schema (only if migrations succeeded)
    if [ $exit_code -eq 0 ]; then
        if ! verify_database_schema; then
            log_error "Database initialization failed: schema verification error"
            exit_code=1
        fi
    fi
    
    # Step 6: Release lock (handled by trap)
    if [ $exit_code -eq 0 ]; then
        log_info "Database initialization completed successfully!"
    else
        log_error "Database initialization failed!"
    fi
    
    exit $exit_code
}

# Run main function
main
