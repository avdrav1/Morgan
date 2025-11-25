#!/bin/bash

# Script to set up automatic SSL certificate renewal via cron
# This configures a cron job to run the renewal script daily

set -e

echo "=========================================="
echo "SSL Certificate Auto-Renewal Setup"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠ This script must be run as root or with sudo"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RENEWAL_SCRIPT="$SCRIPT_DIR/renew-ssl.sh"

# Check if renewal script exists
if [ ! -f "$RENEWAL_SCRIPT" ]; then
    echo "✗ Renewal script not found at $RENEWAL_SCRIPT"
    exit 1
fi

# Make renewal script executable
chmod +x "$RENEWAL_SCRIPT"
echo "✓ Made renewal script executable"
echo ""

# Create log directory
mkdir -p /var/log
touch /var/log/certbot-renewal.log
chmod 644 /var/log/certbot-renewal.log
echo "✓ Created log file at /var/log/certbot-renewal.log"
echo ""

# Check if cron job already exists
CRON_JOB="0 3 * * * $RENEWAL_SCRIPT >> /var/log/certbot-renewal.log 2>&1"
CRON_EXISTS=$(crontab -l 2>/dev/null | grep -F "$RENEWAL_SCRIPT" || true)

if [ -n "$CRON_EXISTS" ]; then
    echo "⚠ Cron job for SSL renewal already exists:"
    echo "  $CRON_EXISTS"
    echo ""
    read -p "Do you want to replace it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing cron job."
        exit 0
    fi
    
    # Remove existing cron job
    crontab -l 2>/dev/null | grep -v "$RENEWAL_SCRIPT" | crontab -
    echo "✓ Removed existing cron job"
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

if [ $? -eq 0 ]; then
    echo "✓ Cron job added successfully!"
    echo ""
    echo "Cron job details:"
    echo "  Schedule: Daily at 3:00 AM"
    echo "  Script: $RENEWAL_SCRIPT"
    echo "  Log: /var/log/certbot-renewal.log"
    echo ""
    echo "Current crontab:"
    crontab -l | grep "$RENEWAL_SCRIPT"
    echo ""
    echo "=========================================="
    echo "Auto-Renewal Setup Complete!"
    echo "=========================================="
    echo ""
    echo "The renewal script will run daily at 3:00 AM."
    echo "Certificates will be renewed automatically when they are"
    echo "within 30 days of expiration."
    echo ""
    echo "To manually test the renewal:"
    echo "  sudo $RENEWAL_SCRIPT"
    echo ""
    echo "To view renewal logs:"
    echo "  tail -f /var/log/certbot-renewal.log"
    echo ""
else
    echo "✗ Failed to add cron job"
    exit 1
fi
