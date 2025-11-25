# SSL/TLS Quick Reference

Quick commands for common SSL certificate management tasks.

## Initial Setup

```bash
# 1. Obtain SSL certificate
sudo ./nginx/setup-ssl-prod.sh

# 2. Set up automatic renewal
sudo ./nginx/setup-cron-renewal.sh

# 3. Test SSL configuration
./nginx/test-ssl.sh yourdomain.com
```

## Daily Operations

```bash
# Check certificate expiration
docker run --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    certbot/certbot certificates

# Manual renewal
sudo ./nginx/renew-ssl.sh

# View renewal logs
tail -f /var/log/certbot-renewal.log

# Restart Nginx
docker-compose -f docker-compose.prod.yml restart nginx
```

## Troubleshooting

```bash
# Test SSL connection
curl -I https://yourdomain.com

# Check certificate details
openssl s_client -servername yourdomain.com \
    -connect yourdomain.com:443 < /dev/null | \
    openssl x509 -noout -dates -subject -issuer

# Validate Nginx config
docker exec accountability-nginx-prod nginx -t

# View Nginx logs
docker logs accountability-nginx-prod

# Check DNS
host yourdomain.com
dig yourdomain.com

# Check ports
nc -zv yourdomain.com 80
nc -zv yourdomain.com 443
```

## File Locations

```
nginx/
├── ssl/                      # SSL certificates (symlinks)
│   ├── cert.pem             # Certificate (symlink to Let's Encrypt)
│   ├── key.pem              # Private key (symlink to Let's Encrypt)
│   └── dhparam.pem          # DH parameters (optional)
├── ssl-params.conf          # SSL configuration parameters
├── nginx.conf               # Main Nginx configuration
├── setup-ssl-prod.sh        # Initial certificate setup
├── renew-ssl.sh             # Certificate renewal script
├── setup-cron-renewal.sh    # Cron job setup
├── test-ssl.sh              # SSL testing script
└── SSL_SETUP.md             # Complete documentation

certbot/
├── conf/                    # Certbot configuration
│   └── live/               # Live certificates
│       └── yourdomain.com/
│           ├── fullchain.pem
│           ├── privkey.pem
│           └── ...
└── www/                     # ACME challenge files

/var/log/
└── certbot-renewal.log      # Renewal logs
```

## Certificate Lifecycle

```
Day 0:   Obtain certificate (valid for 90 days)
Day 60:  Renewal window opens (30 days before expiry)
Day 61+: Automatic renewal attempts daily at 3:00 AM
Day 90:  Certificate expires (if not renewed)
```

## Common Issues

| Issue | Solution |
|-------|----------|
| DNS not resolving | Update DNS A record to point to server IP |
| Port 80/443 blocked | Open firewall: `sudo ufw allow 80/tcp && sudo ufw allow 443/tcp` |
| Rate limit reached | Wait 1 week or use staging environment |
| Certificate expired | Run `sudo ./nginx/renew-ssl.sh` manually |
| Nginx won't start | Check config: `docker exec nginx nginx -t` |
| Mixed content warnings | Update all URLs to use HTTPS |

## Security Checklist

- [ ] TLS 1.2+ only (no TLS 1.0/1.1)
- [ ] Strong cipher suites configured
- [ ] HSTS header enabled (1 year)
- [ ] OCSP stapling enabled
- [ ] Security headers configured
- [ ] Automatic renewal set up
- [ ] Certificate expiration monitoring
- [ ] Regular SSL Labs testing (A/A+ rating)

## Emergency Procedures

### Certificate Expired

```bash
# 1. Renew immediately
sudo ./nginx/renew-ssl.sh

# 2. If renewal fails, use staging to test
docker run -it --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    certbot/certbot renew --dry-run

# 3. Check logs for errors
tail -100 /var/log/certbot-renewal.log

# 4. Restart Nginx
docker-compose -f docker-compose.prod.yml restart nginx
```

### Nginx Won't Start

```bash
# 1. Check configuration
docker exec accountability-nginx-prod nginx -t

# 2. Check certificate files exist
ls -la nginx/ssl/

# 3. Check certificate validity
openssl x509 -in nginx/ssl/cert.pem -noout -dates

# 4. View Nginx logs
docker logs accountability-nginx-prod --tail 100

# 5. Restart with fresh config
docker-compose -f docker-compose.prod.yml restart nginx
```

## Testing Commands

```bash
# Quick test
./nginx/test-ssl.sh yourdomain.com

# SSL Labs test
# Visit: https://www.ssllabs.com/ssltest/analyze.html?d=yourdomain.com

# Test specific TLS version
openssl s_client -tls1_2 -connect yourdomain.com:443 < /dev/null
openssl s_client -tls1_3 -connect yourdomain.com:443 < /dev/null

# Test cipher suites
nmap --script ssl-enum-ciphers -p 443 yourdomain.com

# Check security headers
curl -I https://yourdomain.com | grep -i "strict-transport-security\|x-frame-options\|x-content-type-options"
```

## Monitoring

```bash
# Check certificate expiration (days remaining)
echo | openssl s_client -servername yourdomain.com \
    -connect yourdomain.com:443 2>/dev/null | \
    openssl x509 -noout -dates

# Check renewal cron job
crontab -l | grep renew-ssl

# Monitor renewal logs in real-time
tail -f /var/log/certbot-renewal.log

# Check Nginx access logs
docker exec accountability-nginx-prod tail -f /var/log/nginx/access.log

# Check Nginx error logs
docker exec accountability-nginx-prod tail -f /var/log/nginx/error.log
```

## Resources

- **Let's Encrypt**: https://letsencrypt.org/
- **Certbot**: https://certbot.eff.org/
- **SSL Labs**: https://www.ssllabs.com/ssltest/
- **Mozilla SSL Config**: https://ssl-config.mozilla.org/
- **Full Documentation**: See `SSL_SETUP.md`
