# Nginx Quick Reference Guide

## Common Commands

### Validate Configuration
```bash
./nginx/validate-config.sh
```

### Generate Development SSL Certificates
```bash
./nginx/setup-ssl-dev.sh
```

### Build Nginx Docker Image
```bash
docker-compose -f docker-compose.prod.yml build nginx
```

### Start Nginx Service
```bash
docker-compose -f docker-compose.prod.yml up -d nginx
```

### View Nginx Logs
```bash
# Access logs
docker-compose -f docker-compose.prod.yml logs -f nginx

# Error logs only
docker-compose -f docker-compose.prod.yml logs nginx | grep error
```

### Reload Nginx Configuration (without downtime)
```bash
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

### Test Nginx Configuration Inside Container
```bash
docker-compose -f docker-compose.prod.yml exec nginx nginx -t
```

### Restart Nginx Service
```bash
docker-compose -f docker-compose.prod.yml restart nginx
```

## Testing Endpoints

### Test HTTP to HTTPS Redirect
```bash
curl -I http://localhost
# Should return: HTTP/1.1 301 Moved Permanently
# Location: https://localhost/
```

### Test Backend API Routing
```bash
curl -k https://localhost/api/health
# Should return backend health check response
```

### Test Rate Limiting
```bash
# Send 15 rapid requests (limit is 10/s with burst of 20)
for i in {1..15}; do 
    curl -I http://localhost/api/health 2>&1 | grep "HTTP"
done
# Should eventually return: HTTP/1.1 429 Too Many Requests
```

### Test Security Headers
```bash
curl -I -k https://localhost | grep -E "(Strict-Transport|X-Frame|X-Content|X-XSS|Content-Security)"
```

### Test Gzip Compression
```bash
curl -H "Accept-Encoding: gzip" -I https://localhost/
# Should include: Content-Encoding: gzip
```

## Configuration Updates

### Update Domain Name
Edit `nginx/nginx.conf` and replace `server_name _;` with your domain:
```nginx
server_name yourdomain.com www.yourdomain.com;
```

### Adjust Rate Limits
Edit the `limit_req_zone` directives in `nginx/nginx.conf`:
```nginx
# Change from 10r/s to 20r/s
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=20r/s;
```

### Add New API Route
Add a new location block in the HTTPS server section:
```nginx
location /api/v2/ {
    proxy_pass http://backend/api/v2/;
    # ... other proxy settings
}
```

### Modify Security Headers
Edit the `add_header` directives in the HTTPS server block:
```nginx
add_header Content-Security-Policy "your-custom-policy" always;
```

## Troubleshooting

### 502 Bad Gateway
**Cause**: Backend service is not running or not accessible

**Solution**:
```bash
# Check backend status
docker-compose -f docker-compose.prod.yml ps backend

# Check backend logs
docker-compose -f docker-compose.prod.yml logs backend

# Restart backend
docker-compose -f docker-compose.prod.yml restart backend
```

### 404 Not Found for API Routes
**Cause**: Incorrect routing configuration or backend not serving the endpoint

**Solution**:
```bash
# Check nginx configuration
docker-compose -f docker-compose.prod.yml exec nginx cat /etc/nginx/nginx.conf | grep "location /api"

# Test backend directly
docker-compose -f docker-compose.prod.yml exec backend curl http://localhost:8000/health
```

### SSL Certificate Errors
**Cause**: Missing or invalid SSL certificates

**Solution**:
```bash
# For development, generate self-signed certificates
./nginx/setup-ssl-dev.sh

# For production, use Let's Encrypt (see task 3)
```

### Rate Limiting Too Aggressive
**Cause**: Rate limits are too strict for your traffic

**Solution**:
1. Edit `nginx/nginx.conf` and increase rate limits
2. Reload configuration: `docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload`

### Cannot Access Frontend
**Cause**: Frontend files not properly mounted or built

**Solution**:
```bash
# Check frontend build
docker-compose -f docker-compose.prod.yml logs frontend

# Verify frontend files exist
docker-compose -f docker-compose.prod.yml exec nginx ls -la /usr/share/nginx/html
```

## Performance Tuning

### Increase Worker Connections
Edit `nginx/nginx.conf`:
```nginx
events {
    worker_connections 2048;  # Increase from 1024
}
```

### Increase Upstream Keepalive
Edit `nginx/nginx.conf`:
```nginx
upstream backend {
    server backend:8000;
    keepalive 64;  # Increase from 32
}
```

### Adjust Client Body Size
Edit `nginx/nginx.conf`:
```nginx
http {
    client_max_body_size 20M;  # Increase from 10M
}
```

## Monitoring

### Check Active Connections
```bash
docker-compose -f docker-compose.prod.yml exec nginx cat /var/run/nginx.pid | xargs ps -p
```

### Monitor Access Logs in Real-Time
```bash
docker-compose -f docker-compose.prod.yml exec nginx tail -f /var/log/nginx/access.log
```

### Monitor Error Logs in Real-Time
```bash
docker-compose -f docker-compose.prod.yml exec nginx tail -f /var/log/nginx/error.log
```

### Check Nginx Status
```bash
docker-compose -f docker-compose.prod.yml exec nginx nginx -V
```

## Security

### Test SSL Configuration
```bash
# Using testssl.sh (if installed)
testssl.sh https://yourdomain.com

# Using SSL Labs (online)
# Visit: https://www.ssllabs.com/ssltest/
```

### Check for Security Headers
```bash
curl -I -k https://localhost | grep -i "security\|frame\|xss\|content-security"
```

### Review Access Logs for Suspicious Activity
```bash
docker-compose -f docker-compose.prod.yml exec nginx grep "429\|403\|401" /var/log/nginx/access.log
```

## Backup and Restore

### Backup Nginx Configuration
```bash
tar -czf nginx-config-backup-$(date +%Y%m%d).tar.gz nginx/
```

### Restore Nginx Configuration
```bash
tar -xzf nginx-config-backup-YYYYMMDD.tar.gz
docker-compose -f docker-compose.prod.yml restart nginx
```

## Production Checklist

Before deploying to production:

- [ ] Update `server_name` with actual domain
- [ ] Obtain valid SSL certificates (Let's Encrypt)
- [ ] Review and adjust rate limits for expected traffic
- [ ] Test all routes (API, frontend, health checks)
- [ ] Verify security headers are present
- [ ] Test HTTP to HTTPS redirect
- [ ] Configure log rotation
- [ ] Set up monitoring and alerts
- [ ] Test error pages (404, 50x, 429)
- [ ] Review and adjust resource limits
- [ ] Test SSL configuration with SSL Labs
- [ ] Verify CORS settings match frontend domain
- [ ] Test WebSocket connections (if applicable)
- [ ] Configure firewall rules (ports 80, 443, 22 only)
- [ ] Set up automated certificate renewal

## Additional Resources

- [Nginx Documentation](https://nginx.org/en/docs/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [OWASP Secure Headers](https://owasp.org/www-project-secure-headers/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
