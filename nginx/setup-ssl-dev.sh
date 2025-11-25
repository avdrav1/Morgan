#!/bin/bash

# Development SSL Certificate Setup Script
# This script generates self-signed certificates for local testing

set -e

echo "==================================="
echo "Development SSL Certificate Setup"
echo "==================================="
echo ""

# Create SSL directory if it doesn't exist
mkdir -p nginx/ssl

# Check if certificates already exist
if [ -f "nginx/ssl/cert.pem" ] && [ -f "nginx/ssl/key.pem" ]; then
    echo "SSL certificates already exist."
    read -p "Do you want to regenerate them? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing certificates."
        exit 0
    fi
fi

echo "Generating self-signed SSL certificate..."
echo ""

# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout nginx/ssl/key.pem \
    -out nginx/ssl/cert.pem \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost" \
    2>/dev/null

if [ $? -eq 0 ]; then
    echo "✓ SSL certificates generated successfully!"
    echo ""
    echo "Certificate details:"
    openssl x509 -in nginx/ssl/cert.pem -noout -subject -dates
    echo ""
    echo "⚠ WARNING: These are self-signed certificates for development only."
    echo "   Browsers will show security warnings."
    echo "   For production, use Let's Encrypt certificates."
    echo ""
else
    echo "✗ Failed to generate SSL certificates"
    exit 1
fi
