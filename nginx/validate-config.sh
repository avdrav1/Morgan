#!/bin/bash

# Nginx Configuration Validation Script
# This script validates the Nginx configuration before deployment

set -e

echo "==================================="
echo "Nginx Configuration Validation"
echo "==================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if nginx directory exists
if [ ! -d "nginx" ]; then
    echo -e "${RED}Error: nginx directory not found${NC}"
    exit 1
fi

echo "1. Checking nginx.conf syntax..."
# Note: We can't fully validate the config without the backend service running
# So we'll do a basic syntax check by looking for common errors
if [ -f "nginx/nginx.conf" ]; then
    # Check for basic syntax issues
    if grep -q "upstream backend" nginx/nginx.conf && \
       grep -q "server {" nginx/nginx.conf && \
       grep -q "location" nginx/nginx.conf; then
        echo -e "${GREEN}✓ nginx.conf structure looks valid${NC}"
        echo -e "${YELLOW}  Note: Full validation requires backend service to be running${NC}"
    else
        echo -e "${RED}✗ nginx.conf appears to be malformed${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ nginx.conf not found${NC}"
    exit 1
fi

echo ""
echo "2. Checking required files..."

# Check for required files
REQUIRED_FILES=(
    "nginx/nginx.conf"
    "nginx/Dockerfile"
    "nginx/errors/404.html"
    "nginx/errors/50x.html"
    "nginx/errors/429.html"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓ $file exists${NC}"
    else
        echo -e "${RED}✗ $file is missing${NC}"
        exit 1
    fi
done

echo ""
echo "3. Checking SSL directory..."
if [ -d "nginx/ssl" ]; then
    echo -e "${GREEN}✓ SSL directory exists${NC}"
    
    # Check for SSL certificates
    if [ -f "nginx/ssl/cert.pem" ] && [ -f "nginx/ssl/key.pem" ]; then
        echo -e "${GREEN}✓ SSL certificates found${NC}"
    else
        echo -e "${YELLOW}⚠ SSL certificates not found (will need to be generated)${NC}"
    fi
else
    echo -e "${YELLOW}⚠ SSL directory not found (will be created)${NC}"
fi

echo ""
echo "4. Checking configuration values..."

# Check for placeholder values that need to be replaced
if grep -q "server_name _;" nginx/nginx.conf; then
    echo -e "${YELLOW}⚠ server_name is set to '_' (wildcard). Update with your domain for production.${NC}"
fi

if grep -q "ssl_certificate /etc/nginx/ssl/cert.pem;" nginx/nginx.conf; then
    echo -e "${YELLOW}⚠ Using default SSL certificate paths. Update for Let's Encrypt if needed.${NC}"
fi

echo ""
echo "5. Checking rate limiting configuration..."
if grep -q "limit_req_zone" nginx/nginx.conf; then
    echo -e "${GREEN}✓ Rate limiting is configured${NC}"
    echo "   - API limit: $(grep 'zone=api_limit' nginx/nginx.conf | grep -o 'rate=[^ ]*')"
    echo "   - Auth limit: $(grep 'zone=auth_limit' nginx/nginx.conf | grep -o 'rate=[^ ]*')"
    echo "   - General limit: $(grep 'zone=general_limit' nginx/nginx.conf | grep -o 'rate=[^ ]*')"
else
    echo -e "${RED}✗ Rate limiting not configured${NC}"
    exit 1
fi

echo ""
echo "6. Checking security headers..."
SECURITY_HEADERS=(
    "Strict-Transport-Security"
    "X-Frame-Options"
    "X-Content-Type-Options"
    "X-XSS-Protection"
    "Content-Security-Policy"
)

for header in "${SECURITY_HEADERS[@]}"; do
    if grep -q "$header" nginx/nginx.conf; then
        echo -e "${GREEN}✓ $header is configured${NC}"
    else
        echo -e "${RED}✗ $header is missing${NC}"
        exit 1
    fi
done

echo ""
echo "7. Checking gzip compression..."
if grep -q "gzip on;" nginx/nginx.conf; then
    echo -e "${GREEN}✓ Gzip compression is enabled${NC}"
else
    echo -e "${RED}✗ Gzip compression is not enabled${NC}"
    exit 1
fi

echo ""
echo "8. Checking upstream configuration..."
if grep -q "upstream backend" nginx/nginx.conf; then
    echo -e "${GREEN}✓ Backend upstream is configured${NC}"
else
    echo -e "${RED}✗ Backend upstream is not configured${NC}"
    exit 1
fi

echo ""
echo "==================================="
echo -e "${GREEN}All validation checks passed!${NC}"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Update server_name with your domain"
echo "2. Generate or obtain SSL certificates"
echo "3. Build the Docker image: docker-compose -f docker-compose.prod.yml build nginx"
echo "4. Test the deployment: docker-compose -f docker-compose.prod.yml up nginx"
echo ""
