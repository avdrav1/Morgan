# SSL/TLS Setup Checklist

Use this checklist to ensure proper SSL/TLS configuration for production deployment.

## Pre-Deployment Checklist

### Prerequisites
- [ ] Domain name registered and owned
- [ ] DNS A record points to server IP address
- [ ] Server has public IP address
- [ ] Ports 80 and 443 are open in firewall
- [ ] Docker and Docker Compose installed
- [ ] Root/sudo access to server

### Verification Commands
```bash
# Check DNS
host yourdomain.com

# Check ports
nc -zv yourdomain.com 80
nc -zv yourdomain.com 443

# Check Docker
docker --version
docker-compose --version
```

## Initial Setup Checklist

### 1. Prepare Scripts
- [ ] Make scripts executable: `chmod +x nginx/*.sh`
- [ ] Verify scripts exist:
  - [ ] `setup-ssl-prod.sh`
  - [ ] `renew-ssl.sh`
  - [ ] `setup-cron-renewal.sh`
  - [ ] `test-ssl.sh`

### 2. Obtain SSL Certificate
- [ ] Run: `sudo ./nginx/setup-ssl-prod.sh`
- [ ] Enter domain name correctly
- [ ] Enter valid email address
- [ ] Confirm configuration
- [ ] Wait for certificate obtainment
- [ ] Verify success message

### 3. Update Configuration
- [ ] Update `.env.production`:
  - [ ] `FRONTEND_URL=https://yourdomain.com`
  - [ ] `BACKEND_URL=https://yourdomain.com/api`
  - [ ] `CORS_ORIGINS=https://yourdomain.com`
  - [ ] `DISCORD_REDIRECT_URI=https://yourdomain.com/oauth/callback`
- [ ] Verify `nginx/nginx.conf` has correct `server_name`
- [ ] Check certificate symlinks exist in `nginx/ssl/`

### 4. Deploy Services
- [ ] Build images: `docker-compose -f docker-compose.prod.yml build`
- [ ] Start services: `docker-compose -f docker-compose.prod.yml up -d`
- [ ] Check all containers running: `docker-compose -f docker-compose.prod.yml ps`
- [ ] Check Nginx logs: `docker logs accountability-nginx-prod`

### 5. Set Up Auto-Renewal
- [ ] Run: `sudo ./nginx/setup-cron-renewal.sh`
- [ ] Verify cron job: `crontab -l | grep renew-ssl`
- [ ] Check log file created: `ls -la /var/log/certbot-renewal.log`

### 6. Test Configuration
- [ ] Run: `./nginx/test-ssl.sh yourdomain.com`
- [ ] Verify all tests pass (✓)
- [ ] Test in browser: `https://yourdomain.com`
- [ ] Check for security warnings (should be none)
- [ ] Test HTTP redirect: `http://yourdomain.com` → `https://yourdomain.com`

## Post-Deployment Checklist

### Security Verification
- [ ] HTTPS works without warnings
- [ ] HTTP redirects to HTTPS
- [ ] Certificate is valid and trusted
- [ ] Certificate matches domain name
- [ ] Certificate expiration > 60 days
- [ ] TLS 1.2 and 1.3 enabled
- [ ] TLS 1.0 and 1.1 disabled
- [ ] Strong cipher suites configured

### Security Headers
- [ ] Strict-Transport-Security present
- [ ] X-Frame-Options present
- [ ] X-Content-Type-Options present
- [ ] X-XSS-Protection present
- [ ] Content-Security-Policy present
- [ ] Referrer-Policy present
- [ ] Permissions-Policy present

### Verification Commands
```bash
# Check security headers
curl -I https://yourdomain.com | grep -i "strict-transport-security\|x-frame-options\|x-content-type-options"

# Check TLS versions
openssl s_client -tls1_2 -connect yourdomain.com:443 < /dev/null
openssl s_client -tls1_3 -connect yourdomain.com:443 < /dev/null

# Check certificate
openssl s_client -servername yourdomain.com -connect yourdomain.com:443 < /dev/null | openssl x509 -noout -dates -subject
```

### SSL Labs Test
- [ ] Visit: https://www.ssllabs.com/ssltest/
- [ ] Enter domain name
- [ ] Wait for analysis (2-5 minutes)
- [ ] Verify rating: A or A+
- [ ] Review any warnings or recommendations

## Monitoring Checklist

### Daily Monitoring
- [ ] Check application is accessible via HTTPS
- [ ] Monitor error logs for SSL issues
- [ ] Verify no certificate warnings in browser

### Weekly Monitoring
- [ ] Check renewal logs: `tail -f /var/log/certbot-renewal.log`
- [ ] Verify cron job is running: `crontab -l`
- [ ] Check certificate expiration: `docker run --rm -v "$(pwd)/certbot/conf:/etc/letsencrypt" certbot/certbot certificates`

### Monthly Monitoring
- [ ] Run SSL test: `./nginx/test-ssl.sh yourdomain.com`
- [ ] Check SSL Labs rating
- [ ] Review security headers
- [ ] Update cipher suites if needed
- [ ] Check for Nginx updates

### Before Certificate Expiration (30 days)
- [ ] Verify automatic renewal is working
- [ ] Check renewal logs for errors
- [ ] Test manual renewal: `sudo ./nginx/renew-ssl.sh`
- [ ] Verify Nginx reloads after renewal

## Troubleshooting Checklist

### Certificate Obtainment Failed
- [ ] Check DNS resolution: `host yourdomain.com`
- [ ] Check ports open: `nc -zv yourdomain.com 80 443`
- [ ] Check firewall: `sudo ufw status`
- [ ] Check rate limits (5 certs/week per domain)
- [ ] Review Certbot logs
- [ ] Try staging environment: add `--staging` flag

### Certificate Renewal Failed
- [ ] Check cron job exists: `crontab -l`
- [ ] Check renewal logs: `tail -100 /var/log/certbot-renewal.log`
- [ ] Test manual renewal: `sudo ./nginx/renew-ssl.sh`
- [ ] Check Nginx is running: `docker ps | grep nginx`
- [ ] Verify certificate files exist: `ls -la nginx/ssl/`

### Browser Shows Certificate Error
- [ ] Check certificate validity: `openssl x509 -in nginx/ssl/cert.pem -noout -dates`
- [ ] Verify domain matches certificate
- [ ] Check system time is correct: `date`
- [ ] Clear browser SSL cache
- [ ] Test with different browser
- [ ] Check certificate chain: `openssl s_client -connect yourdomain.com:443 < /dev/null`

### Nginx Won't Start
- [ ] Validate config: `docker exec nginx nginx -t`
- [ ] Check certificate files exist: `ls -la nginx/ssl/`
- [ ] Check Nginx logs: `docker logs accountability-nginx-prod`
- [ ] Verify ports not in use: `netstat -tulpn | grep -E ':(80|443)'`
- [ ] Check Docker volumes: `docker volume ls`

## Maintenance Checklist

### Regular Maintenance
- [ ] Keep Nginx updated
- [ ] Keep Certbot updated
- [ ] Review and update cipher suites
- [ ] Monitor SSL/TLS security advisories
- [ ] Test backup and restore procedures
- [ ] Document any configuration changes

### Certificate Renewal (Automatic)
- [ ] Cron job runs daily at 3:00 AM
- [ ] Checks if certificate expires within 30 days
- [ ] Renews certificate if needed
- [ ] Reloads Nginx automatically
- [ ] Logs all operations

### Manual Renewal (When Needed)
- [ ] Run: `sudo ./nginx/renew-ssl.sh`
- [ ] Check logs: `tail -f /var/log/certbot-renewal.log`
- [ ] Verify Nginx reloaded: `docker logs accountability-nginx-prod`
- [ ] Test HTTPS: `curl -I https://yourdomain.com`

## Emergency Procedures Checklist

### Certificate Expired
1. [ ] Renew immediately: `sudo ./nginx/renew-ssl.sh`
2. [ ] If renewal fails, check DNS and ports
3. [ ] Review logs: `tail -100 /var/log/certbot-renewal.log`
4. [ ] Test with staging: add `--staging` flag
5. [ ] Contact Let's Encrypt support if needed

### Nginx Not Starting
1. [ ] Check config: `docker exec nginx nginx -t`
2. [ ] Check certificates: `ls -la nginx/ssl/`
3. [ ] Check logs: `docker logs accountability-nginx-prod`
4. [ ] Restart container: `docker-compose -f docker-compose.prod.yml restart nginx`
5. [ ] Rebuild if needed: `docker-compose -f docker-compose.prod.yml build nginx`

### Rate Limit Reached
1. [ ] Wait 1 week for limit reset
2. [ ] Use staging environment for testing
3. [ ] Review Let's Encrypt rate limits
4. [ ] Consider using wildcard certificate
5. [ ] Plan certificate requests carefully

## Documentation Checklist

### Documentation Review
- [ ] Read `SSL_SETUP.md` for detailed instructions
- [ ] Review `SSL_QUICK_REFERENCE.md` for common commands
- [ ] Check `nginx/README.md` for Nginx configuration
- [ ] Review `TASK_3_SSL_SETUP_SUMMARY.md` for implementation details

### Team Knowledge
- [ ] Document domain name and email used
- [ ] Share renewal schedule with team
- [ ] Document any custom configurations
- [ ] Create runbook for common issues
- [ ] Train team on SSL management

## Compliance Checklist

### Security Requirements
- [ ] TLS 1.2+ only (no TLS 1.0/1.1)
- [ ] Strong cipher suites
- [ ] Perfect forward secrecy
- [ ] HSTS enabled (1 year minimum)
- [ ] OCSP stapling enabled
- [ ] Security headers configured
- [ ] Certificate auto-renewal enabled

### Operational Requirements
- [ ] Monitoring in place
- [ ] Alerting configured
- [ ] Backup procedures documented
- [ ] Rollback procedures documented
- [ ] Incident response plan
- [ ] Regular testing schedule

### Audit Trail
- [ ] Certificate obtainment logged
- [ ] Renewal attempts logged
- [ ] Configuration changes documented
- [ ] Security incidents documented
- [ ] Regular audits scheduled

## Sign-Off

### Initial Setup
- [ ] SSL certificates obtained
- [ ] Auto-renewal configured
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Team trained

**Completed by:** ________________  
**Date:** ________________  
**Signature:** ________________

### Production Deployment
- [ ] All checklist items completed
- [ ] SSL Labs rating: A or A+
- [ ] No security warnings
- [ ] Monitoring active
- [ ] Team notified

**Approved by:** ________________  
**Date:** ________________  
**Signature:** ________________

## Notes

Use this section to document any deviations from the standard setup, custom configurations, or important information for your specific deployment.

---

**Last Updated:** 2024-11-25  
**Version:** 1.0  
**Maintained by:** DevOps Team
