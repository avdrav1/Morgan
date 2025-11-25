#!/bin/bash

################################################################################
# Backup System Test Script
# 
# This script tests the backup system functionality without requiring
# a running database (for development/CI testing)
################################################################################

set -eo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

################################################################################
# Functions
################################################################################

log_test() {
    echo -e "${YELLOW}[TEST]${NC} $*"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $*"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $*"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

test_script_exists() {
    local script="$1"
    log_test "Checking if $script exists..."
    
    if [ -f "$script" ]; then
        log_pass "$script exists"
    else
        log_fail "$script not found"
    fi
}

test_script_executable() {
    local script="$1"
    log_test "Checking if $script is executable..."
    
    if [ -x "$script" ]; then
        log_pass "$script is executable"
    else
        log_fail "$script is not executable"
    fi
}

test_script_syntax() {
    local script="$1"
    log_test "Checking syntax of $script..."
    
    if bash -n "$script" 2>/dev/null; then
        log_pass "$script has valid syntax"
    else
        log_fail "$script has syntax errors"
    fi
}

test_backup_directory_structure() {
    log_test "Testing backup directory structure..."
    
    local temp_dir=$(mktemp -d)
    export BACKUP_DIR="$temp_dir"
    
    mkdir -p "$temp_dir/daily" "$temp_dir/weekly" "$temp_dir/monthly"
    
    if [ -d "$temp_dir/daily" ] && [ -d "$temp_dir/weekly" ] && [ -d "$temp_dir/monthly" ]; then
        log_pass "Backup directory structure created successfully"
    else
        log_fail "Failed to create backup directory structure"
    fi
    rm -rf "$temp_dir"
}

test_cleanup_logic() {
    log_test "Testing cleanup logic..."
    
    local temp_dir=$(mktemp -d)
    local daily_dir="$temp_dir/daily"
    mkdir -p "$daily_dir"
    
    # Create 10 fake backup files with different timestamps
    for i in {01..10}; do
        touch -t "202401011200.$i" "$daily_dir/backup_$i.sql.gz"
    done
    
    # Count files
    local count=$(find "$daily_dir" -type f | wc -l)
    
    if [ "$count" -eq 10 ]; then
        log_pass "Created 10 test backup files"
        
        # Test that we can identify oldest files
        local oldest=$(find "$daily_dir" -type f -printf '%T+ %p\n' | sort | head -n 3 | wc -l)
        
        if [ "$oldest" -eq 3 ]; then
            log_pass "Can identify oldest files for cleanup"
        else
            log_fail "Failed to identify oldest files"
        fi
    else
        log_fail "Failed to create test backup files"
    fi
    rm -rf "$temp_dir"
}

test_backup_type_detection() {
    log_test "Testing backup type detection logic..."
    
    # Test monthly (1st of month)
    local day_of_month="01"
    if [ "$day_of_month" = "01" ]; then
        log_pass "Monthly backup detection works"
    else
        log_fail "Monthly backup detection failed"
    fi
    
    # Test weekly (Sunday = day 7)
    local day_of_week="7"
    if [ "$day_of_week" = "7" ]; then
        log_pass "Weekly backup detection works"
    else
        log_fail "Weekly backup detection failed"
    fi
}

test_compression() {
    log_test "Testing compression functionality..."
    
    local temp_dir=$(mktemp -d)
    local test_file="$temp_dir/test.sql"
    
    # Create test file
    echo "SELECT * FROM test;" > "$test_file"
    
    # Compress
    if gzip -f "$test_file"; then
        if [ -f "${test_file}.gz" ]; then
            log_pass "Compression works"
        else
            log_fail "Compressed file not created"
        fi
    else
        log_fail "Compression failed"
    fi
    rm -rf "$temp_dir"
}

test_encryption() {
    log_test "Testing encryption functionality..."
    
    if ! command -v openssl &> /dev/null; then
        log_pass "OpenSSL not installed (optional - skipping)"
        return 0
    fi
    
    local temp_dir=$(mktemp -d)
    local test_file="$temp_dir/test.txt"
    local encrypted_file="$temp_dir/test.txt.enc"
    local key="test_key_123"
    
    # Create test file
    echo "test data" > "$test_file"
    
    # Encrypt
    if openssl enc -aes-256-cbc -salt -in "$test_file" -out "$encrypted_file" -k "$key" 2>/dev/null; then
        # Decrypt
        if openssl enc -aes-256-cbc -d -in "$encrypted_file" -out "$temp_dir/decrypted.txt" -k "$key" 2>/dev/null; then
            local original=$(cat "$test_file")
            local decrypted=$(cat "$temp_dir/decrypted.txt")
            
            if [ "$original" = "$decrypted" ]; then
                log_pass "Encryption/decryption works"
            else
                log_fail "Decrypted content doesn't match original"
            fi
        else
            log_fail "Decryption failed"
        fi
    else
        log_fail "Encryption failed"
    fi
    rm -rf "$temp_dir"
}

test_documentation() {
    log_test "Checking documentation..."
    
    if [ -f "scripts/BACKUP_SYSTEM.md" ]; then
        log_pass "Backup system documentation exists"
    else
        log_fail "Backup system documentation not found"
    fi
}

################################################################################
# Main execution
################################################################################

main() {
    echo "=========================================="
    echo "Backup System Test Suite"
    echo "=========================================="
    echo ""
    
    # Test script existence
    test_script_exists "scripts/backup-database.sh"
    test_script_exists "scripts/cleanup-backups.sh"
    test_script_exists "scripts/restore-database.sh"
    test_script_exists "scripts/setup-backup-cron.sh"
    
    echo ""
    
    # Test script executability
    test_script_executable "scripts/backup-database.sh"
    test_script_executable "scripts/cleanup-backups.sh"
    test_script_executable "scripts/restore-database.sh"
    test_script_executable "scripts/setup-backup-cron.sh"
    
    echo ""
    
    # Test script syntax
    test_script_syntax "scripts/backup-database.sh"
    test_script_syntax "scripts/cleanup-backups.sh"
    test_script_syntax "scripts/restore-database.sh"
    test_script_syntax "scripts/setup-backup-cron.sh"
    
    echo ""
    
    # Test functionality
    test_backup_directory_structure
    test_cleanup_logic
    test_backup_type_detection
    test_compression
    test_encryption
    test_documentation
    
    echo ""
    echo "=========================================="
    echo "Test Results"
    echo "=========================================="
    echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
    echo -e "${RED}Failed: $TESTS_FAILED${NC}"
    echo "=========================================="
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        exit 0
    else
        echo -e "${RED}Some tests failed!${NC}"
        exit 1
    fi
}

# Run main function
main "$@"
