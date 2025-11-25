#!/bin/bash

# ============================================
# Environment Variable Validation Script
# ============================================
# This script validates that all required environment variables
# are set and contain appropriate values for production deployment
#
# Usage: ./scripts/validate-env.sh [env-file]
# Example: ./scripts/validate-env.sh .env.production
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
ERRORS=0
WARNINGS=0
CHECKS=0

# Environment file to validate (default: .env.production)
ENV_FILE="${1:-.env.production}"

echo "============================================"
echo "Environment Variable Validation"
echo "============================================"
echo "Validating: $ENV_FILE"
echo ""

# Check if file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}ERROR: Environment file '$ENV_FILE' not found${NC}"
    echo "Please create it from .env.production.example"
    exit 1
fi

# Load environment variables
# Use a safer method that handles spaces in values
while IFS='=' read -r key value; do
    # Skip comments and empty lines
    [[ $key =~ ^#.*$ ]] && continue
    [[ -z $key ]] && continue
    
    # Remove leading/trailing whitespace
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs)
    
    # Remove quotes if present
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    
    # Export the variable
    export "$key=$value"
done < "$ENV_FILE"

# ============================================
# Validation Functions
# ============================================

check_required() {
    local var_name=$1
    local var_value="${!var_name}"
    CHECKS=$((CHECKS + 1))
    
    if [ -z "$var_value" ]; then
        echo -e "${RED}✗ REQUIRED: $var_name is not set${NC}"
        ERRORS=$((ERRORS + 1))
        return 1
    else
        echo -e "${GREEN}✓ $var_name is set${NC}"
        return 0
    fi
}

check_not_default() {
    local var_name=$1
    local var_value="${!var_name}"
    local default_pattern=$2
    CHECKS=$((CHECKS + 1))
    
    if [ -z "$var_value" ]; then
        echo -e "${RED}✗ SECURITY: $var_name is not set${NC}"
        ERRORS=$((ERRORS + 1))
        return 1
    elif echo "$var_value" | grep -qi "$default_pattern"; then
        echo -e "${RED}✗ SECURITY: $var_name contains default/placeholder value${NC}"
        ERRORS=$((ERRORS + 1))
        return 1
    else
        echo -e "${GREEN}✓ $var_name has been customized${NC}"
        return 0
    fi
}

check_min_length() {
    local var_name=$1
    local var_value="${!var_name}"
    local min_length=$2
    CHECKS=$((CHECKS + 1))
    
    if [ -z "$var_value" ]; then
        echo -e "${RED}✗ SECURITY: $var_name is not set${NC}"
        ERRORS=$((ERRORS + 1))
        return 1
    elif [ ${#var_value} -lt $min_length ]; then
        echo -e "${RED}✗ SECURITY: $var_name is too short (${#var_value} chars, minimum $min_length)${NC}"
        ERRORS=$((ERRORS + 1))
        return 1
    else
        echo -e "${GREEN}✓ $var_name has sufficient length (${#var_value} chars)${NC}"
        return 0
    fi
}

check_equals() {
    local var_name=$1
    local var_value="${!var_name}"
    local expected=$2
    CHECKS=$((CHECKS + 1))
    
    if [ "$var_value" != "$expected" ]; then
        echo -e "${RED}✗ CONFIG: $var_name should be '$expected' but is '$var_value'${NC}"
        ERRORS=$((ERRORS + 1))
        return 1
    else
        echo -e "${GREEN}✓ $var_name is correctly set to '$expected'${NC}"
        return 0
    fi
}

check_url_https() {
    local var_name=$1
    local var_value="${!var_name}"
    CHECKS=$((CHECKS + 1))
    
    if [ -z "$var_value" ]; then
        echo -e "${RED}✗ REQUIRED: $var_name is not set${NC}"
        ERRORS=$((ERRORS + 1))
        return 1
    elif ! echo "$var_value" | grep -q "^https://"; then
        echo -e "${YELLOW}⚠ WARNING: $var_name should use HTTPS in production${NC}"
        WARNINGS=$((WARNINGS + 1))
        return 1
    else
        echo -e "${GREEN}✓ $var_name uses HTTPS${NC}"
        return 0
    fi
}

check_pattern() {
    local var_name=$1
    local var_value="${!var_name}"
    local pattern=$2
    local description=$3
    CHECKS=$((CHECKS + 1))
    
    if [ -z "$var_value" ]; then
        echo -e "${RED}✗ REQUIRED: $var_name is not set${NC}"
        ERRORS=$((ERRORS + 1))
        return 1
    elif ! echo "$var_value" | grep -qE "$pattern"; then
        echo -e "${RED}✗ FORMAT: $var_name does not match expected format ($description)${NC}"
        ERRORS=$((ERRORS + 1))
        return 1
    else
        echo -e "${GREEN}✓ $var_name format is valid${NC}"
        return 0
    fi
}

# ============================================
# Application Configuration Checks
# ============================================

echo "Checking Application Configuration..."
check_required "APP_NAME"
check_equals "ENVIRONMENT" "production"
check_equals "DEBUG" "False"
echo ""

# ============================================
# Database Configuration Checks
# ============================================

echo "Checking Database Configuration..."
check_required "POSTGRES_USER"
check_not_default "POSTGRES_PASSWORD" "CHANGE_THIS"
check_min_length "POSTGRES_PASSWORD" 16
check_required "POSTGRES_DB"
check_pattern "DATABASE_URL" "^postgresql://" "PostgreSQL connection string"
echo ""

# ============================================
# Redis Configuration Checks
# ============================================

echo "Checking Redis Configuration..."
check_pattern "REDIS_URL" "^redis://" "Redis connection string"
echo ""

# ============================================
# Security Configuration Checks
# ============================================

echo "Checking Security Configuration..."
check_not_default "JWT_SECRET_KEY" "CHANGE_THIS"
check_min_length "JWT_SECRET_KEY" 32
check_required "JWT_ALGORITHM"
check_not_default "ENCRYPTION_KEY" "CHANGE_THIS"
check_min_length "ENCRYPTION_KEY" 32
echo ""

# ============================================
# URL Configuration Checks
# ============================================

echo "Checking URL Configuration..."
check_url_https "FRONTEND_URL"
check_url_https "BACKEND_URL"
check_url_https "VITE_API_URL"
check_required "CORS_ORIGINS"
echo ""

# ============================================
# External API Checks
# ============================================

echo "Checking External API Configuration..."
check_not_default "ANTHROPIC_API_KEY" "your_anthropic"
check_pattern "ANTHROPIC_API_KEY" "^sk-ant-" "Anthropic API key format"
check_required "ANTHROPIC_MODEL"
echo ""

# ============================================
# Discord Configuration Checks
# ============================================

echo "Checking Discord Configuration..."
check_not_default "DISCORD_TOKEN" "your_discord"
check_not_default "DISCORD_CLIENT_ID" "your_discord"
check_not_default "DISCORD_CLIENT_SECRET" "your_discord"
check_url_https "DISCORD_REDIRECT_URI"
echo ""

# ============================================
# Optional Configuration Checks
# ============================================

echo "Checking Optional Configuration..."
if [ -n "$DOMAIN" ]; then
    echo -e "${GREEN}✓ DOMAIN is set: $DOMAIN${NC}"
    CHECKS=$((CHECKS + 1))
else
    echo -e "${YELLOW}⚠ WARNING: DOMAIN not set (needed for SSL certificates)${NC}"
    WARNINGS=$((WARNINGS + 1))
    CHECKS=$((CHECKS + 1))
fi

if [ -n "$LETSENCRYPT_EMAIL" ]; then
    echo -e "${GREEN}✓ LETSENCRYPT_EMAIL is set${NC}"
    CHECKS=$((CHECKS + 1))
else
    echo -e "${YELLOW}⚠ WARNING: LETSENCRYPT_EMAIL not set (needed for SSL certificates)${NC}"
    WARNINGS=$((WARNINGS + 1))
    CHECKS=$((CHECKS + 1))
fi
echo ""

# ============================================
# Summary
# ============================================

echo "============================================"
echo "Validation Summary"
echo "============================================"
echo "Total checks: $CHECKS"
echo -e "${GREEN}Passed: $((CHECKS - ERRORS - WARNINGS))${NC}"
echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
echo -e "${RED}Errors: $ERRORS${NC}"
echo ""

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}VALIDATION FAILED${NC}"
    echo "Please fix the errors above before deploying to production"
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}VALIDATION PASSED WITH WARNINGS${NC}"
    echo "Review the warnings above - they may indicate security or configuration issues"
    exit 0
else
    echo -e "${GREEN}VALIDATION PASSED${NC}"
    echo "All environment variables are properly configured"
    exit 0
fi
