#!/bin/bash

# Production Configuration Validation Script
# This script validates the production Docker Compose configuration

set -e

echo "==================================="
echo "Production Configuration Validator"
echo "==================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    exit 1
fi
echo "✅ Docker is installed"

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed"
    exit 1
fi
echo "✅ Docker Compose is installed"

# Check if docker-compose.prod.yml exists
if [ ! -f "docker-compose.prod.yml" ]; then
    echo "❌ docker-compose.prod.yml not found"
    exit 1
fi
echo "✅ docker-compose.prod.yml exists"

# Validate Docker Compose syntax
echo ""
echo "Validating Docker Compose syntax..."
if docker-compose -f docker-compose.prod.yml config > /dev/null 2>&1 || docker compose -f docker-compose.prod.yml config > /dev/null 2>&1; then
    echo "✅ Docker Compose syntax is valid"
else
    echo "❌ Docker Compose syntax is invalid"
    exit 1
fi

# Check if .env.production exists
if [ ! -f ".env.production" ]; then
    echo "⚠️  .env.production not found (use .env.production.example as template)"
else
    echo "✅ .env.production exists"
    
    # Check for required environment variables
    echo ""
    echo "Checking required environment variables..."
    
    required_vars=(
        "POSTGRES_USER"
        "POSTGRES_PASSWORD"
        "POSTGRES_DB"
        "JWT_SECRET_KEY"
        "ANTHROPIC_API_KEY"
        "DISCORD_TOKEN"
        "DISCORD_CLIENT_ID"
        "DISCORD_CLIENT_SECRET"
        "FRONTEND_URL"
        "BACKEND_URL"
        "VITE_API_URL"
        "CORS_ORIGINS"
        "DISCORD_REDIRECT_URI"
        "DISCORD_WEBHOOK_URL"
    )
    
    missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" .env.production; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -eq 0 ]; then
        echo "✅ All required environment variables are present"
    else
        echo "⚠️  Missing environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "   - $var"
        done
    fi
fi

# Check if Nginx configuration directory exists
if [ ! -d "nginx" ]; then
    echo "⚠️  nginx/ directory not found (will be created in Task 2)"
else
    echo "✅ nginx/ directory exists"
fi

echo ""
echo "==================================="
echo "Validation Summary"
echo "==================================="
echo "✅ Docker Compose configuration is valid"
echo "⚠️  Complete remaining tasks:"
echo "   - Task 2: Create Nginx reverse proxy configuration"
echo "   - Task 3: Create SSL/TLS certificate management setup"
echo "   - Task 4: Create production environment configuration"
echo ""
echo "To deploy:"
echo "  1. Copy .env.production.example to .env.production"
echo "  2. Fill in all required environment variables"
echo "  3. Complete Nginx configuration (Task 2)"
echo "  4. Run: docker-compose -f docker-compose.prod.yml up -d"
echo ""
