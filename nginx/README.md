# Nginx Reverse Proxy Configuration

This directory contains the Nginx reverse proxy configuration for the Proactive Accountability Assistant production deployment.

## Overview

The Nginx reverse proxy provides:
- SSL/TLS termination
- HTTP to HTTPS redirection
- Request routing to backend services
- Static file serving for frontend
- Rate limiting
- Security headers
- Gzip compression
- Custom error pages

## Files

- `nginx.conf` - Main Nginx configuration file
- `Dockerfile` - Docker image for Nginx service
- `errors/` - Custom error page templates
  - `404.html` - Page not found
  - `50x.html` - Server error
  - `429.html` - Rate limit exceeded

## Configuration Details

### Rate Limiting

Three rate limiting zones are configured:

1. **API Limit**: 10 requests/second with burst of 20
   - Applied to `/api/*` endpoints
   
2. **Auth Limit**: 5 requests/minute with burst of 3
   - Applied to authentication endpoints (`/api/auth`, `/api/login`, `/api/register`)
   
3. **General Limit**: 100 requests/second with burst of 200
   - Applied globally as a safety net

### Security Headers

The following security headers are automatically added to all responses:

- `Strict-Transport-Security` - Forces HTTPS for 1 year
- `X-Frame-Options` - Prevents clickjacking
- `X-Content-Type-Options` - Prevents MIME sniffing
- `X-XSS-Protection` - Enables XSS filtering
- `Referrer-Policy` - Controls referrer information
- `Content-Security-Policy` - Restricts resource loading
- `Permissions-Policy` - Controls browser features

### SSL/TLS Configuration

- Protocols: TLS 1.2 and TLS 1.3 only
- Strong cipher suites with forward secrecy
- OCSP stapling enabled
- Session caching for performance

### Routing Rules

| Path | Destination | Rate Limit |
|------|-------------|------------|
| `/api/*` | Backend service | 10 req/s |
| `/api/auth`, `/api/login`, `/api/register` | Backend service | 5 req/min |
| `/docs`, `/openapi.json`, `/redoc` | Backend service | None |
| `/health` | Backend health check | None |
| `/*` | Frontend static files | 100 req/s |

### Caching Strategy

- **Static assets** (JS, CSS, images, fonts): 1 year cache with immutable flag
- **HTML files**: No caching (always fresh)
- **API responses**: No caching (handled by backend)

## SSL Certificate Setup

### Development/Testing

For local testing with self-signed certificates:

```bash
./nginx/setup-ssl-dev.sh
```

This generates self-signed certificates valid for 365 days. Browsers will show security warnings.

### Production with Let's Encrypt

For production deployment with free SSL certificates from Let's Encrypt:

```bash
# 1. Obtain SSL certificate
sudo ./nginx/setup-ssl-prod.sh

# 2. Set up automatic renewal
sudo ./nginx/setup-cron-renewal.sh

# 3. Test SSL configuration
./nginx/test-ssl.sh yourdomain.com
```

**Complete Documentation**: See [SSL_SETUP.md](SSL_SETUP.md) for detailed instructions.

**Quick Reference**: See [SSL_QUICK_REFERENCE.md](SSL_QUICK_REFERENCE.md) for common commands.

### SSL Scripts

- `setup-ssl-dev.sh` - Generate self-signed certificates for development
- `setup-ssl-prod.sh` - Obtain Let's Encrypt certificates for production
- `renew-ssl.sh` - Manually renew SSL certificates
- `setup-cron-renewal.sh` - Set up automatic certificate renewal
- `test-ssl.sh` - Test SSL configuration and security
- `generate-dhparam.sh` - Generate DH parameters for enhanced security
- `ssl-params.conf` - SSL/TLS configuration parameters

## Usage in Docker Compose

The Nginx service is defined in `docker-compose.prod.yml`:

```yaml
nginx:
  build: ./nginx
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./frontend/dist:/usr/share/nginx/html:ro
    - nginx_certs:/etc/nginx/ssl:ro
    - nginx_logs:/var/log/nginx
  depends_on:
    - backend
    - frontend
```

## Testing the Configuration

### Validate Nginx Configuration

```bash
docker-compose -f docker-compose.prod.yml run --rm nginx nginx -t
```

### Test HTTP to HTTPS Redirect

```bash
curl -I http://localhost
# Should return 301 redirect to https://
```

### Test Rate Limiting

```bash
# Send rapid requests to trigger rate limit
for i in {1..15}; do curl -I http://localhost/api/health; done
# Should eventually return 429 Too Many Requests
```

### Test Security Headers

```bash
curl -I https://localhost
# Check for security headers in response
```

## Customization

### Adjusting Rate Limits

Edit the `limit_req_zone` directives in `nginx.conf`:

```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
```

Change `rate=10r/s` to your desired rate (e.g., `rate=20r/s` for 20 requests/second).

### Adding Custom Routes

Add new location blocks in the HTTPS server section:

```nginx
location /custom-path {
    proxy_pass http://backend/custom-path;
    # ... proxy settings
}
```

### Modifying Security Headers

Edit the `add_header` directives in the HTTPS server block. Be careful with CSP as it can break functionality if too restrictive.

### Custom Error Pages

Edit the HTML files in `nginx/errors/` to match your branding. The pages are responsive and mobile-friendly.

## Troubleshooting

### 502 Bad Gateway

- Backend service is not running or not accessible
- Check backend health: `docker-compose -f docker-compose.prod.yml logs backend`
- Verify backend is listening on port 8000

### 404 Not Found for API Routes

- Check that backend service name matches upstream configuration
- Verify API routes in backend application

### SSL Certificate Errors

- Ensure certificates exist in `/etc/nginx/ssl/`
- Check certificate validity: `openssl x509 -in cert.pem -text -noout`
- Verify certificate paths in nginx.conf

### Rate Limiting Too Aggressive

- Increase burst values in location blocks
- Adjust rate in `limit_req_zone` directives
- Check Nginx error logs for rate limit messages

## Performance Tuning

### Worker Processes

The configuration uses `worker_processes auto` which automatically sets the number based on CPU cores. For manual control:

```nginx
worker_processes 4;  # Set to number of CPU cores
```

### Worker Connections

Default is 1024 connections per worker. For high-traffic sites:

```nginx
events {
    worker_connections 2048;
}
```

### Keepalive Connections

Upstream keepalive is set to 32. Increase for high-traffic:

```nginx
upstream backend {
    server backend:8000;
    keepalive 64;
}
```

## Monitoring

### Access Logs

Location: `/var/log/nginx/access.log`

Format includes: IP, timestamp, request, status, size, referrer, user agent

### Error Logs

Location: `/var/log/nginx/error.log`

Level: `warn` (change to `info` or `debug` for more detail)

### Log Rotation

Logs should be rotated using logrotate or Docker logging drivers. See task 11 in the implementation plan.

## Security Best Practices

1. **Keep Nginx Updated**: Use latest stable version
2. **Restrict Access**: Use firewall rules to limit access to ports 80, 443, 22
3. **Monitor Logs**: Regularly review access and error logs for suspicious activity
4. **Rate Limiting**: Adjust limits based on legitimate traffic patterns
5. **SSL Configuration**: Regularly update cipher suites and protocols
6. **Hide Version**: Add `server_tokens off;` to hide Nginx version

## References

- [Nginx Documentation](https://nginx.org/en/docs/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [OWASP Secure Headers Project](https://owasp.org/www-project-secure-headers/)
