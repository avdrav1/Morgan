#!/bin/bash
# Backend Production Configuration Verification Script
# This script verifies that the backend is properly configured for production

set -e

echo "=========================================="
echo "Backend Production Configuration Verification"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env.production exists
echo "1. Checking for .env.production file..."
if [ -f ".env.production" ]; then
    echo -e "${GREEN}✓${NC} .env.production file exists"
else
    echo -e "${YELLOW}⚠${NC} .env.production file not found"
    echo "   Copy .env.production.example to .env.production and configure it"
fi
echo ""

# Check Dockerfile
echo "2. Checking backend Dockerfile..."
if grep -q "gunicorn app.main:app" backend/Dockerfile; then
    echo -e "${GREEN}✓${NC} Dockerfile uses Gunicorn"
else
    echo -e "${RED}✗${NC} Dockerfile does not use Gunicorn"
fi

if grep -q "USER appuser" backend/Dockerfile; then
    echo -e "${GREEN}✓${NC} Dockerfile runs as non-root user"
else
    echo -e "${RED}✗${NC} Dockerfile runs as root (security risk)"
fi
echo ""

# Check config.py for production settings
echo "3. Checking backend configuration..."
if grep -q "DB_POOL_SIZE" backend/app/core/config.py; then
    echo -e "${GREEN}✓${NC} Database connection pool settings configured"
else
    echo -e "${RED}✗${NC} Database connection pool settings missing"
fi

if grep -q "GUNICORN_WORKERS" backend/app/core/config.py; then
    echo -e "${GREEN}✓${NC} Gunicorn worker settings configured"
else
    echo -e "${RED}✗${NC} Gunicorn worker settings missing"
fi

if grep -q "LOG_LEVEL" backend/app/core/config.py; then
    echo -e "${GREEN}✓${NC} Log level configuration present"
else
    echo -e "${RED}✗${NC} Log level configuration missing"
fi
echo ""

# Check docker-compose.prod.yml
echo "4. Checking production Docker Compose..."
if grep -q "ENVIRONMENT=production" docker-compose.prod.yml; then
    echo -e "${GREEN}✓${NC} ENVIRONMENT set to production"
else
    echo -e "${RED}✗${NC} ENVIRONMENT not set to production"
fi

if grep -q "DEBUG=false" docker-compose.prod.yml; then
    echo -e "${GREEN}✓${NC} DEBUG mode disabled"
else
    echo -e "${YELLOW}⚠${NC} DEBUG mode setting not found"
fi

if grep -q "DB_POOL_SIZE" docker-compose.prod.yml; then
    echo -e "${GREEN}✓${NC} Database pool settings in docker-compose"
else
    echo -e "${RED}✗${NC} Database pool settings missing from docker-compose"
fi

if grep -q "GUNICORN_WORKERS" docker-compose.prod.yml; then
    echo -e "${GREEN}✓${NC} Gunicorn worker settings in docker-compose"
else
    echo -e "${RED}✗${NC} Gunicorn worker settings missing from docker-compose"
fi
echo ""

# Check .env.production.example
echo "5. Checking production environment template..."
if grep -q "DB_POOL_SIZE" .env.production.example; then
    echo -e "${GREEN}✓${NC} Database pool settings documented"
else
    echo -e "${RED}✗${NC} Database pool settings not documented"
fi

if grep -q "GUNICORN_WORKERS" .env.production.example; then
    echo -e "${GREEN}✓${NC} Gunicorn settings documented"
else
    echo -e "${RED}✗${NC} Gunicorn settings not documented"
fi
echo ""

# Summary
echo "=========================================="
echo "Verification Complete"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Copy .env.production.example to .env.production"
echo "2. Fill in all required values in .env.production"
echo "3. Test locally: docker-compose -f docker-compose.prod.yml build backend"
echo "4. Deploy to production server"
echo ""
