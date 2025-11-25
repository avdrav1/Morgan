#!/bin/bash

# Production SSL Certificate Setup Script using Let's Encrypt
# This script obtains SSL certificates from Let's Encrypt using Certbot

set -e

echo "=========================================="
echo "Production SSL Certificate Setup"
echo "Let's Encrypt with Certbot"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠ This script should be run as root or with sudo"
    echo "  Some operations may fail without proper permissions"
    echo ""
fi

# Check for required commands
command -v docker >/dev/null 2>&1 || { echo "✗ Docker is required but not installed. Aborting." >&2; exit 1; }
command -v docker-compose >/dev/null 2>&1 || command -v docker compose >/dev/null 2>&1 || { echo "✗ Docker Compose is required but not installed. Aborting." >&2; exit 1; }

# Get domain name
echo "Enter your domain name (e.g., example.com):"
read -r DOMAIN

if [ -z "$DOMAIN" ]; then
    echo "✗ Domain name is required"
    exit 1
fi

echo ""
echo "Enter your email address for Let's Encrypt notifications:"
read -r EMAIL

if [ -z "$EMAIL" ]; then
    echo "✗ Email address is required"
    exit 1
fi

echo ""
echo "Configuration:"
echo "  Domain: $DOMAIN"
echo "  Email: $EMAIL"
echo ""
read -p "Is this correct? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Check if certificates already exist
if [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    echo ""
    echo "⚠ Certificates for $DOMAIN already exist."
    read -p "Do you want to renew them? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing certificates."
        exit 0
    fi
    CERTBOT_CMD="renew"
else
    CERTBOT_CMD="certonly"
fi

echo ""
echo "Step 1: Creating required directories..."
mkdir -p nginx/ssl
mkdir -p certbot/www
mkdir -p certbot/conf

echo "✓ Directories created"
echo ""

# Check if nginx is running
NGINX_RUNNING=$(docker ps -q -f name=accountability-nginx-prod)

if [ -n "$NGINX_RUNNING" ]; then
    echo "Step 2: Nginx is running, will use webroot method..."
    WEBROOT_PATH="/var/www/certbot"
    
    # Run certbot in webroot mode
    echo "Step 3: Obtaining SSL certificate from Let's Encrypt..."
    docker run -it --rm \
        -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
        -v "$(pwd)/certbot/www:/var/www/certbot" \
        certbot/certbot $CERTBOT_CMD \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email "$EMAIL" \
        --agree-tos \
        --no-eff-email \
        -d "$DOMAIN"
else
    echo "Step 2: Nginx is not running, using standalone method..."
    echo "⚠ Make sure ports 80 and 443 are available"
    echo ""
    
    # Run certbot in standalone mode
    echo "Step 3: Obtaining SSL certificate from Let's Encrypt..."
    docker run -it --rm \
        -p 80:80 \
        -p 443:443 \
        -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
        certbot/certbot $CERTBOT_CMD \
        --standalone \
        --email "$EMAIL" \
        --agree-tos \
        --no-eff-email \
        -d "$DOMAIN"
fi

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ SSL certificate obtained successfully!"
    echo ""
    
    # Create symlinks for nginx
    echo "Step 4: Creating certificate symlinks for Nginx..."
    ln -sf "$(pwd)/certbot/conf/live/$DOMAIN/fullchain.pem" nginx/ssl/cert.pem
    ln -sf "$(pwd)/certbot/conf/live/$DOMAIN/privkey.pem" nginx/ssl/key.pem
    
    echo "✓ Symlinks created"
    echo ""
    
    # Update nginx configuration with domain
    echo "Step 5: Updating Nginx configuration..."
    if [ -f "nginx/nginx.conf" ]; then
        # Backup original config
        cp nginx/nginx.conf nginx/nginx.conf.backup
        
        # Replace server_name _ with actual domain
        sed -i "s/server_name _;/server_name $DOMAIN;/g" nginx/nginx.conf
        
        echo "✓ Nginx configuration updated"
        echo "  Backup saved to nginx/nginx.conf.backup"
    fi
    echo ""
    
    echo "=========================================="
    echo "SSL Certificate Setup Complete!"
    echo "=========================================="
    echo ""
    echo "Certificate details:"
    docker run --rm \
        -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
        certbot/certbot certificates
    echo ""
    echo "Next steps:"
    echo "1. Update your DNS records to point $DOMAIN to this server"
    echo "2. Update .env.production with FRONTEND_URL=https://$DOMAIN"
    echo "3. Restart Nginx: docker-compose -f docker-compose.prod.yml restart nginx"
    echo "4. Set up automatic renewal with: ./nginx/renew-ssl.sh"
    echo ""
    echo "⚠ Certificate will expire in 90 days. Set up automatic renewal!"
    echo ""
else
    echo ""
    echo "✗ Failed to obtain SSL certificate"
    echo ""
    echo "Common issues:"
    echo "- Domain DNS not pointing to this server"
    echo "- Firewall blocking ports 80/443"
    echo "- Rate limit reached (5 certificates per domain per week)"
    echo ""
    exit 1
fi
