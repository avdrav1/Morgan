#!/bin/bash

# Generate Diffie-Hellman parameters for enhanced SSL security
# This improves forward secrecy for DHE cipher suites

set -e

echo "=========================================="
echo "Diffie-Hellman Parameter Generation"
echo "=========================================="
echo ""

# Create SSL directory if it doesn't exist
mkdir -p nginx/ssl

# Check if DH params already exist
if [ -f "nginx/ssl/dhparam.pem" ]; then
    echo "⚠ DH parameters already exist at nginx/ssl/dhparam.pem"
    echo ""
    read -p "Do you want to regenerate them? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing DH parameters."
        exit 0
    fi
fi

echo "Generating 2048-bit Diffie-Hellman parameters..."
echo "⚠ This may take several minutes (2-5 minutes typically)"
echo ""

# Generate DH parameters
openssl dhparam -out nginx/ssl/dhparam.pem 2048

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ DH parameters generated successfully!"
    echo ""
    echo "File: nginx/ssl/dhparam.pem"
    echo "Size: $(wc -c < nginx/ssl/dhparam.pem) bytes"
    echo ""
    echo "To use these parameters, uncomment the following line in nginx/ssl-params.conf:"
    echo "  ssl_dhparam /etc/nginx/ssl/dhparam.pem;"
    echo ""
    echo "Then restart Nginx to apply the changes."
    echo ""
else
    echo ""
    echo "✗ Failed to generate DH parameters"
    exit 1
fi
