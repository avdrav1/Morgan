# SSL/TLS Certificate Management Guide

This guide covers SSL/TLS certificate setup, renewal, and management for production deployment using Let's Encrypt.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Initial Setup](#initial-setup)
4. [Certificate Renewal](#certificate-renewal)
5. [Testing SSL Configuration](#testing-ssl-configuration)
6. [Troubleshooting](#troubleshooting)
7. [Security Best Practices](#security-best-practices)

## Overview

The SSL/TLS setup uses:
- **Let's Encrypt** for free SSL certificates
- **Certbot** for certificate management
- **Nginx** for SSL termination
- **Automatic renewal** via cron jobs

### Certificate Lifecycle

1. **Obtain**: Get initial certificate from Let's Encrypt
2. **Deploy**: Configure Nginx to use the certificate
3. **Renew**: Automatically renew before expiration (90 days)
4. **Monitor**: Check certificate validity and expiration

## Prerequisites

Before setting up SSL certificates:

1. **Domain Name**: You must own a domain name
2. **DNS Configuration**: Domain must point to your server's IP address
3. **Ports Open**: Ports 80 and 443 must be accessible
4. **Docker**: Docker and Docker Compose must be installed
5. **Server Access**: Root or sudo access to the server

### Verify Prerequisites

```bash
# Check DNS resolution
host yourdomain.com

# Check port accessibility
nc -zv yourdomain.com 80
nc -zv yourdomain.com 443

# Check Docker
docker --version
docker-compose --version
```

## Initial Setup

### Step 1: Prepare Environment

```bash
# Navigate to project directory
cd /path/to/project

# Make scripts executable
chmod +x nginx/setup-ssl-prod.sh
chmod +x nginx/renew-ssl.sh
chmod +x nginx/setup-cron-renewal.sh
chmod +x nginx/test-ssl.sh
```

### Step 2: Obtain SSL Certificate

Run the production SSL setup script:

```bash
sudo ./nginx/setup-ssl-prod.sh
```

The script will:
1. Prompt for your domain name
2. Prompt for your email address
3. Obtain certificate from Let's Encrypt
4. Create symlinks for Nginx
5. Update Nginx configuration

**Example:**
```
Enter your domain name (e.g., example.com):
> myapp.example.com

Enter your email address for Let's Encrypt notifications:
> admin@example.com
```

### Step 3: Update Environment Variables

Update your `.env.production` file:

```bash
# Frontend URL (with HTTPS)
FRONTEND_URL=https://yourdomain.com

# Backend URL (with HTTPS)
BACKEND_URL=https://yourdomain.com/api

# CORS origins (with HTTPS)
CORS_ORIGINS=https://yourdomain.com

# Discord OAuth redirect URI (with HTTPS)
DISCORD_REDIRECT_URI=https://yourdomain.com/oauth/callback
```

### Step 4: Restart Services

```bash
# Restart Nginx to load new certificates
docker-compose -f docker-compose.prod.yml restart nginx

# Or restart all services
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d
```

### Step 5: Verify SSL Setup

```bash
# Test SSL configuration
./nginx/test-ssl.sh yourdomain.com

# Or visit in browser
https://yourdomain.com
```

## Certificate Renewal

Let's Encrypt certificates expire after **90 days**. Automatic renewal is essential.

### Setup Automatic Renewal

```bash
# Run the cron setup script (requires sudo)
sudo ./nginx/setup-cron-renewal.sh
```

This creates a cron job that runs daily at 3:00 AM to check for renewal.

### Manual Renewal

To manually renew certificates:

```bash
# Run renewal script
sudo ./nginx/renew-ssl.sh

# Check renewal logs
tail -f /var/log/certbot-renewal.log
```

### Renewal Process

1. **Check**: Certbot checks if certificate expires within 30 days
2. **Renew**: If yes, obtains new certificate from Let's Encrypt
3. **Deploy**: Updates certificate files
4. **Reload**: Reloads Nginx to use new certificate
5. **Log**: Records result in log file

### Monitoring Renewal

```bash
# View renewal logs
tail -f /var/log/certbot-renewal.log

# Check certificate expiration
docker run --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    certbot/certbot certificates

# List cron jobs
crontab -l
```

## Testing SSL Configuration

### Quick Test

```bash
./nginx/test-ssl.sh yourdomain.com
```

This tests:
- DNS resolution
- Port accessibility
- HTTP to HTTPS redirect
- Certificate validity
- TLS protocol support
- Security headers

### Comprehensive Test

Use SSL Labs for detailed analysis:

1. Visit: https://www.ssllabs.com/ssltest/
2. Enter your domain
3. Wait for analysis (2-5 minutes)
4. Target rating: **A or A+**

### Manual Testing

```bash
# Test HTTPS connection
curl -I https://yourdomain.com

# Check certificate details
openssl s_client -servername yourdomain.com -connect yourdomain.com:443 < /dev/null

# Test TLS 1.2
openssl s_client -tls1_2 -connect yourdomain.com:443 < /dev/null

# Test TLS 1.3
openssl s_client -tls1_3 -connect yourdomain.com:443 < /dev/null
```

## Troubleshooting

### Certificate Obtainment Fails

**Problem**: Cannot obtain certificate from Let's Encrypt

**Solutions**:

1. **Check DNS**: Ensure domain points to your server
   ```bash
   host yourdomain.com
   dig yourdomain.com
   ```

2. **Check Firewall**: Ensure ports 80 and 443 are open
   ```bash
   sudo ufw status
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   ```

3. **Check Rate Limits**: Let's Encrypt has rate limits
   - 5 certificates per domain per week
   - 50 certificates per account per week
   - Wait or use staging environment for testing

4. **Check Logs**: Review Certbot logs
   ```bash
   docker logs $(docker ps -q -f name=certbot)
   ```

### Certificate Renewal Fails

**Problem**: Automatic renewal is not working

**Solutions**:

1. **Check Cron Job**: Verify cron job exists
   ```bash
   crontab -l | grep renew-ssl
   ```

2. **Check Logs**: Review renewal logs
   ```bash
   tail -100 /var/log/certbot-renewal.log
   ```

3. **Test Manually**: Run renewal script manually
   ```bash
   sudo ./nginx/renew-ssl.sh
   ```

4. **Check Nginx**: Ensure Nginx is running
   ```bash
   docker ps | grep nginx
   ```

### Browser Shows Certificate Error

**Problem**: Browser shows "Your connection is not private"

**Solutions**:

1. **Check Certificate**: Verify certificate is valid
   ```bash
   ./nginx/test-ssl.sh yourdomain.com
   ```

2. **Check Domain**: Ensure accessing correct domain
   - Certificate is issued for specific domain
   - www.example.com ≠ example.com

3. **Clear Browser Cache**: Clear SSL cache
   - Chrome: chrome://net-internals/#sockets
   - Firefox: Clear recent history

4. **Check System Time**: Ensure server time is correct
   ```bash
   date
   timedatectl
   ```

### Mixed Content Warnings

**Problem**: Browser shows mixed content warnings

**Solutions**:

1. **Update URLs**: Ensure all resources use HTTPS
   ```javascript
   // Bad
   <script src="http://example.com/script.js">
   
   // Good
   <script src="https://example.com/script.js">
   ```

2. **Use Protocol-Relative URLs**: Let browser choose protocol
   ```javascript
   <script src="//example.com/script.js">
   ```

3. **Check CSP**: Review Content-Security-Policy header
   ```nginx
   add_header Content-Security-Policy "upgrade-insecure-requests";
   ```

## Security Best Practices

### 1. Strong SSL Configuration

Our configuration includes:
- **TLS 1.2 and 1.3 only** (no TLS 1.0/1.1)
- **Strong cipher suites** (AEAD ciphers preferred)
- **Perfect forward secrecy** (ECDHE key exchange)
- **OCSP stapling** (improved performance and privacy)

### 2. Security Headers

Essential headers configured:
- **HSTS**: Force HTTPS for 1 year
- **X-Frame-Options**: Prevent clickjacking
- **X-Content-Type-Options**: Prevent MIME sniffing
- **Content-Security-Policy**: Prevent XSS attacks

### 3. Certificate Management

Best practices:
- **Automatic renewal**: Set up cron job
- **Monitor expiration**: Check regularly
- **Backup certificates**: Keep secure backups
- **Use strong keys**: 2048-bit RSA minimum

### 4. Additional Security

Optional enhancements:

#### Generate DH Parameters

```bash
./nginx/generate-dhparam.sh
```

Then uncomment in `nginx/ssl-params.conf`:
```nginx
ssl_dhparam /etc/nginx/ssl/dhparam.pem;
```

#### Enable Certificate Transparency

Already enabled via OCSP stapling.

#### Add CAA DNS Record

Add CAA record to DNS:
```
example.com. CAA 0 issue "letsencrypt.org"
```

### 5. Monitoring

Set up monitoring for:
- Certificate expiration (alert 30 days before)
- Renewal failures (alert immediately)
- SSL Labs rating (check monthly)
- Security headers (check after updates)

## Advanced Configuration

### Multiple Domains

To add certificates for multiple domains:

```bash
# Run setup for each domain
sudo ./nginx/setup-ssl-prod.sh

# Or use wildcard certificate
docker run -it --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email admin@example.com \
    --agree-tos \
    -d example.com \
    -d www.example.com \
    -d api.example.com
```

### Wildcard Certificates

For wildcard certificates (*.example.com):

```bash
docker run -it --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    certbot/certbot certonly \
    --manual \
    --preferred-challenges dns \
    --email admin@example.com \
    --agree-tos \
    -d example.com \
    -d "*.example.com"
```

Note: Requires manual DNS TXT record creation.

### Staging Environment

For testing, use Let's Encrypt staging:

```bash
docker run -it --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email admin@example.com \
    --agree-tos \
    --staging \
    -d example.com
```

## References

- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Certbot Documentation](https://certbot.eff.org/docs/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [SSL Labs Testing](https://www.ssllabs.com/ssltest/)
- [OWASP TLS Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Protection_Cheat_Sheet.html)

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review Certbot logs: `/var/log/certbot-renewal.log`
3. Review Nginx logs: `docker logs accountability-nginx-prod`
4. Test SSL configuration: `./nginx/test-ssl.sh yourdomain.com`
