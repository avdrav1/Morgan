#!/bin/bash

# SSL Certificate Renewal Script for Let's Encrypt
# This script renews SSL certificates and reloads Nginx
# Should be run via cron job (e.g., daily or weekly)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Logging
LOG_FILE="/var/log/certbot-renewal.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "SSL Certificate Renewal Check"
log "=========================================="

# Check if certbot configuration exists
if [ ! -d "$PROJECT_ROOT/certbot/conf" ]; then
    log "✗ Certbot configuration not found. Run setup-ssl-prod.sh first."
    exit 1
fi

# Check if nginx is running
NGINX_CONTAINER=$(docker ps -q -f name=accountability-nginx-prod)

if [ -z "$NGINX_CONTAINER" ]; then
    log "⚠ Nginx container is not running. Skipping renewal."
    exit 0
fi

log "Checking certificate expiration..."

# Run certbot renew
docker run --rm \
    -v "$PROJECT_ROOT/certbot/conf:/etc/letsencrypt" \
    -v "$PROJECT_ROOT/certbot/www:/var/www/certbot" \
    certbot/certbot renew \
    --webroot \
    --webroot-path=/var/www/certbot \
    --quiet \
    --deploy-hook "echo 'Certificate renewed successfully'" \
    2>&1 | tee -a "$LOG_FILE"

RENEWAL_EXIT_CODE=${PIPESTATUS[0]}

if [ $RENEWAL_EXIT_CODE -eq 0 ]; then
    log "✓ Certificate renewal check completed"
    
    # Check if certificates were actually renewed
    if grep -q "Certificate renewed successfully" "$LOG_FILE"; then
        log "✓ Certificates were renewed, reloading Nginx..."
        
        # Reload Nginx to pick up new certificates
        docker exec "$NGINX_CONTAINER" nginx -s reload
        
        if [ $? -eq 0 ]; then
            log "✓ Nginx reloaded successfully"
            
            # Send success notification (optional - configure as needed)
            # Uncomment and configure if you want email notifications
            # echo "SSL certificates renewed successfully on $(hostname)" | \
            #     mail -s "SSL Certificate Renewal Success" admin@example.com
        else
            log "✗ Failed to reload Nginx"
            exit 1
        fi
    else
        log "ℹ Certificates are not due for renewal yet (renews within 30 days of expiry)"
    fi
else
    log "✗ Certificate renewal failed with exit code $RENEWAL_EXIT_CODE"
    
    # Send failure notification (optional - configure as needed)
    # Uncomment and configure if you want email notifications
    # echo "SSL certificate renewal failed on $(hostname). Check logs at $LOG_FILE" | \
    #     mail -s "SSL Certificate Renewal FAILED" admin@example.com
    
    exit 1
fi

log "=========================================="
log "Renewal check complete"
log "=========================================="
