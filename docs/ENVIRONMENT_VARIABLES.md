# Environment Variables Reference

## Overview

This document provides a complete reference for all environment variables used in the Proactive Accountability Assistant application. Each variable is documented with its purpose, format, default value, and whether it's required.

## Quick Start

1. Copy `.env.production.example` to `.env.production`
2. Fill in all required values (marked with ⚠️)
3. Run validation: `./scripts/validate-env.sh .env.production`
4. Review security checklist in [SECRET_MANAGEMENT.md](./SECRET_MANAGEMENT.md)

## Variable Categories

- [Application Configuration](#application-configuration)
- [Database Configuration](#database-configuration)
- [Redis Configuration](#redis-configuration)
- [Security & Authentication](#security--authentication)
- [URL Configuration](#url-configuration)
- [External APIs](#external-apis)
- [Discord Integration](#discord-integration)
- [Deployment Configuration](#deployment-configuration)
- [Optional Advanced Settings](#optional-advanced-settings)

---

## Application Configuration

### APP_NAME

**Description**: Application name displayed in logs and monitoring

**Required**: Yes

**Format**: String

**Default**: `Proactive Accountability Assistant`

**Example**: `Proactive Accountability Assistant`

**Notes**: Can be customized for branding purposes

---

### ENVIRONMENT

**Description**: Deployment environment identifier

**Required**: ⚠️ Yes (MUST be "production" for production)

**Format**: String (enum)

**Allowed Values**: `development`, `staging`, `production`

**Default**: `development`

**Production Value**: `production`

**Notes**: 
- Controls debug mode and logging levels
- Enables production optimizations
- MUST be set to `production` for production deployments

---

### DEBUG

**Description**: Enable/disable debug mode

**Required**: ⚠️ Yes (MUST be False for production)

**Format**: Boolean

**Allowed Values**: `True`, `False`

**Default**: `True`

**Production Value**: `False`

**Notes**:
- When `True`, exposes detailed error messages and stack traces
- SECURITY: MUST be `False` in production to prevent information disclosure
- Affects logging verbosity

---

## Database Configuration

### POSTGRES_USER

**Description**: PostgreSQL database username

**Required**: ⚠️ Yes

**Format**: String (alphanumeric, underscores)

**Default**: `accountability`

**Example**: `accountability_prod`

**Notes**:
- Use different usernames for different environments
- Avoid generic names like "admin" or "root"

---

### POSTGRES_PASSWORD

**Description**: PostgreSQL database password

**Required**: ⚠️ Yes

**Format**: String

**Minimum Length**: 16 characters (32+ recommended)

**Security**: CRITICAL

**Generate With**:
```bash
openssl rand -base64 32
```

**Example**: `xK9mP2nQ7vR4sT8wY3zA6bC1dE5fG0hJ`

**Notes**:
- MUST be changed from default value
- Use cryptographically random generation
- Store securely and never commit to version control
- Rotate every 90 days

---

### POSTGRES_DB

**Description**: PostgreSQL database name

**Required**: ⚠️ Yes

**Format**: String (alphanumeric, underscores)

**Default**: `accountability_db`

**Example**: `accountability_production`

**Notes**: Use descriptive names that indicate environment

---

### DATABASE_URL

**Description**: Full PostgreSQL connection string

**Required**: ⚠️ Yes

**Format**: `postgresql://username:password@host:port/database`

**Example**: `postgresql://accountability:xK9mP2nQ7vR4sT8wY3zA6bC1dE5fG0hJ@postgres:5432/accountability_db`

**Notes**:
- In Docker Compose, use service name `postgres` as host
- Must match POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB values
- Used by backend application and Celery workers

---

## Redis Configuration

### REDIS_URL

**Description**: Redis connection string for caching and message broker

**Required**: ⚠️ Yes

**Format**: `redis://host:port/database`

**Example**: `redis://redis:6379/0`

**Notes**:
- In Docker Compose, use service name `redis` as host
- Database number (0-15) can be used to separate concerns
- Used for caching, Celery broker, and session storage

---

### CELERY_BROKER_URL

**Description**: Celery message broker URL

**Required**: No (defaults to REDIS_URL)

**Format**: `redis://host:port/database`

**Example**: `redis://redis:6379/1`

**Notes**:
- Only set if using separate Redis instance for Celery
- Defaults to REDIS_URL if not specified

---

### CELERY_RESULT_BACKEND

**Description**: Celery result backend URL

**Required**: No (defaults to REDIS_URL)

**Format**: `redis://host:port/database`

**Example**: `redis://redis:6379/2`

**Notes**:
- Only set if using separate Redis instance for results
- Defaults to REDIS_URL if not specified

---

## Security & Authentication

### JWT_SECRET_KEY

**Description**: Secret key for signing JWT authentication tokens

**Required**: ⚠️ Yes

**Format**: String (hex recommended)

**Minimum Length**: 32 characters (64+ recommended)

**Security**: CRITICAL

**Generate With**:
```bash
openssl rand -hex 32
```

**Example**: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2`

**Notes**:
- MUST be changed from default value
- Compromise allows impersonation of any user
- Rotation requires all users to re-authenticate
- Use different keys for each environment
- Rotate every 180 days

---

### JWT_ALGORITHM

**Description**: Algorithm used for JWT signing

**Required**: No

**Format**: String

**Default**: `HS256`

**Allowed Values**: `HS256`, `HS384`, `HS512`

**Notes**: Do not change unless you understand JWT algorithms

---

### ACCESS_TOKEN_EXPIRE_MINUTES

**Description**: JWT token expiration time in minutes

**Required**: No

**Format**: Integer

**Default**: `10080` (7 days)

**Example**: `1440` (1 day)

**Notes**:
- Shorter expiration = more secure but less convenient
- Longer expiration = more convenient but higher risk if compromised
- Consider your security requirements

---

### ENCRYPTION_KEY

**Description**: Fernet key for encrypting sensitive data at rest

**Required**: ⚠️ Yes

**Format**: 44-character base64-encoded string

**Security**: CRITICAL

**Generate With**:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Example**: `xK9mP2nQ7vR4sT8wY3zA6bC1dE5fG0hJiKlMnOpQrStU=`

**Notes**:
- MUST be a valid Fernet key
- Used to encrypt Discord tokens and other sensitive data
- Backup securely before rotation (needed to decrypt existing data)
- Rotation requires re-encrypting all data

---

### WEBHOOK_SECRET

**Description**: Secret for validating incoming webhooks

**Required**: No (recommended for production)

**Format**: String (hex recommended)

**Minimum Length**: 32 characters

**Generate With**:
```bash
openssl rand -hex 32
```

**Example**: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

**Notes**:
- Used to verify webhook requests are legitimate
- Share with webhook sender
- Rotate every 90 days

---

## URL Configuration

### FRONTEND_URL

**Description**: Full URL where frontend is accessible

**Required**: ⚠️ Yes

**Format**: URL (HTTPS in production)

**Example**: `https://yourdomain.com`

**Notes**:
- MUST use HTTPS in production
- Used for CORS configuration
- Used in OAuth redirect URIs
- No trailing slash

---

### BACKEND_URL

**Description**: Full URL where backend API is accessible

**Required**: No (derived from FRONTEND_URL)

**Format**: URL (HTTPS in production)

**Example**: `https://yourdomain.com/api`

**Notes**:
- MUST use HTTPS in production
- Typically FRONTEND_URL + `/api`
- Used for internal service communication

---

### VITE_API_URL

**Description**: API URL for frontend builds (Vite environment variable)

**Required**: ⚠️ Yes

**Format**: URL (HTTPS in production)

**Example**: `https://yourdomain.com/api`

**Notes**:
- MUST match BACKEND_URL
- Embedded in frontend build
- MUST use HTTPS in production

---

### CORS_ORIGINS

**Description**: Allowed origins for CORS requests

**Required**: ⚠️ Yes

**Format**: JSON array of URLs

**Example**: `["https://yourdomain.com","https://www.yourdomain.com"]`

**Notes**:
- SECURITY: Only include trusted domains
- Must include FRONTEND_URL
- Can include multiple domains for multi-domain setups
- MUST use HTTPS in production

---

## External APIs

### ANTHROPIC_API_KEY

**Description**: API key for Anthropic Claude AI service

**Required**: ⚠️ Yes

**Format**: String starting with `sk-ant-`

**Security**: HIGH

**Obtain From**: https://console.anthropic.com/

**Example**: `sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

**Notes**:
- Required for AI-powered features
- Monitor usage to prevent unexpected costs
- Set usage limits in Anthropic dashboard
- Rotate if compromised

---

### ANTHROPIC_MODEL

**Description**: Anthropic model to use for AI requests

**Required**: No

**Format**: String

**Default**: `claude-sonnet-4-20250514`

**Allowed Values**: 
- `claude-sonnet-4-20250514` (balanced)
- `claude-opus-4-20250514` (most capable)
- `claude-haiku-4-20250514` (fastest)

**Notes**:
- Different models have different costs and capabilities
- Sonnet recommended for production (good balance)

---

## Discord Integration

### DISCORD_TOKEN

**Description**: Discord bot authentication token

**Required**: ⚠️ Yes

**Format**: String

**Security**: CRITICAL

**Obtain From**: https://discord.com/developers/applications

**Example**: `MTxxxxxxxxxxxxxxxxxx.xxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

**Notes**:
- Provides full access to your Discord bot
- NEVER share or commit to version control
- Regenerate immediately if compromised
- Different token for each environment

---

### DISCORD_CLIENT_ID

**Description**: Discord OAuth application client ID

**Required**: ⚠️ Yes

**Format**: Numeric string (18-19 digits)

**Security**: LOW (public identifier)

**Obtain From**: https://discord.com/developers/applications

**Example**: `1441388791196680332`

**Notes**:
- Public identifier, not sensitive
- Used for OAuth flow
- Same for all environments (or separate apps per environment)

---

### DISCORD_CLIENT_SECRET

**Description**: Discord OAuth application client secret

**Required**: ⚠️ Yes

**Format**: String

**Security**: HIGH

**Obtain From**: https://discord.com/developers/applications

**Example**: `kbsE1XMHoGt8TtCG9qpfXFe7ugpFR20o`

**Notes**:
- Keep secret, never expose to frontend
- Used for OAuth token exchange
- Regenerate if compromised

---

### DISCORD_REDIRECT_URI

**Description**: OAuth redirect URI after Discord authentication

**Required**: ⚠️ Yes

**Format**: URL (HTTPS in production)

**Example**: `https://yourdomain.com/api/auth/discord/callback`

**Notes**:
- MUST match URI configured in Discord Developer Portal
- MUST use HTTPS in production
- Typically BACKEND_URL + `/auth/discord/callback`

---

### DISCORD_WEBHOOK_URL

**Description**: Discord webhook URL for notifications (optional)

**Required**: No

**Format**: Discord webhook URL

**Security**: MEDIUM

**Obtain From**: Discord Server Settings > Integrations > Webhooks

**Example**: `https://discord.com/api/webhooks/123456789/abcdefghijklmnop`

**Notes**:
- Optional feature for sending notifications to Discord
- Anyone with URL can send messages to channel
- Can be regenerated in Discord if compromised

---

## Deployment Configuration

### DOMAIN

**Description**: Primary domain name for the application

**Required**: Yes (for SSL certificates)

**Format**: Domain name (no protocol)

**Example**: `yourdomain.com`

**Notes**:
- Used by Certbot for SSL certificate generation
- Should match FRONTEND_URL domain
- Required for Let's Encrypt

---

### LETSENCRYPT_EMAIL

**Description**: Email address for Let's Encrypt notifications

**Required**: Yes (for SSL certificates)

**Format**: Email address

**Example**: `admin@yourdomain.com`

**Notes**:
- Receives certificate expiration warnings
- Used for account recovery
- Should be monitored regularly

---

## Optional Advanced Settings

### LOG_LEVEL

**Description**: Application logging level

**Required**: No

**Format**: String (enum)

**Default**: `INFO`

**Allowed Values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

**Recommended**: 
- Production: `INFO` or `WARNING`
- Staging: `INFO`
- Development: `DEBUG`

**Notes**:
- Higher levels = less verbose logging
- DEBUG can expose sensitive information

---

### CLIENT_MAX_BODY_SIZE

**Description**: Maximum request body size (Nginx)

**Required**: No

**Format**: String with unit (K, M, G)

**Default**: `10M`

**Example**: `50M`

**Notes**:
- Limits upload size
- Prevents DoS attacks via large uploads
- Adjust based on your needs

---

### RATE_LIMIT_PER_MINUTE

**Description**: Maximum requests per minute per IP

**Required**: No

**Format**: Integer

**Default**: `60`

**Example**: `100`

**Notes**:
- Prevents abuse and DoS attacks
- Adjust based on expected traffic
- Too low = legitimate users blocked
- Too high = less protection

---

## Environment-Specific Examples

### Development (.env)

```bash
ENVIRONMENT=development
DEBUG=True
DATABASE_URL=postgresql://dev:dev@localhost:5432/dev_db
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=dev-secret-not-for-production
FRONTEND_URL=http://localhost:5173
VITE_API_URL=http://localhost:8000/api
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

### Production (.env.production)

```bash
ENVIRONMENT=production
DEBUG=False
DATABASE_URL=postgresql://prod_user:STRONG_RANDOM_PASSWORD@postgres:5432/prod_db
REDIS_URL=redis://redis:6379/0
JWT_SECRET_KEY=64_CHAR_CRYPTOGRAPHICALLY_RANDOM_HEX_STRING
FRONTEND_URL=https://yourdomain.com
VITE_API_URL=https://yourdomain.com/api
CORS_ORIGINS=["https://yourdomain.com"]
ANTHROPIC_API_KEY=sk-ant-api03-YOUR_REAL_KEY
DISCORD_TOKEN=YOUR_REAL_BOT_TOKEN
DISCORD_CLIENT_ID=YOUR_CLIENT_ID
DISCORD_CLIENT_SECRET=YOUR_CLIENT_SECRET
DISCORD_REDIRECT_URI=https://yourdomain.com/api/auth/discord/callback
ENCRYPTION_KEY=YOUR_FERNET_KEY
DOMAIN=yourdomain.com
LETSENCRYPT_EMAIL=admin@yourdomain.com
```

---

## Validation

### Automated Validation

Run the validation script before deployment:

```bash
# Bash version
./scripts/validate-env.sh .env.production

# Python version
python scripts/validate-env.py .env.production
```

### Manual Validation Checklist

- [ ] All required variables are set
- [ ] No default/placeholder values remain
- [ ] All secrets meet minimum length requirements
- [ ] ENVIRONMENT is set to "production"
- [ ] DEBUG is set to False
- [ ] All URLs use HTTPS
- [ ] CORS_ORIGINS only includes trusted domains
- [ ] Database credentials are strong and unique
- [ ] JWT_SECRET_KEY is cryptographically random
- [ ] ENCRYPTION_KEY is a valid Fernet key
- [ ] API keys are valid and active
- [ ] Discord credentials are correct
- [ ] Domain and email are set for SSL

---

## Troubleshooting

### Common Issues

**Issue**: Services fail to start with "environment variable not set" error

**Solution**: Ensure all required variables are set in `.env.production`

---

**Issue**: Database connection fails

**Solution**: 
- Verify DATABASE_URL matches POSTGRES_* variables
- Check database service is running
- Verify network connectivity between services

---

**Issue**: CORS errors in browser

**Solution**:
- Ensure FRONTEND_URL is in CORS_ORIGINS
- Verify CORS_ORIGINS is valid JSON array format
- Check for trailing slashes (should not have them)

---

**Issue**: JWT authentication fails

**Solution**:
- Verify JWT_SECRET_KEY is set and consistent across all backend instances
- Check token hasn't expired (ACCESS_TOKEN_EXPIRE_MINUTES)
- Ensure ENVIRONMENT and DEBUG are set correctly

---

**Issue**: Discord bot doesn't respond

**Solution**:
- Verify DISCORD_TOKEN is correct and not expired
- Check bot has necessary permissions in Discord
- Verify API_BASE_URL is accessible from discord-bot service

---

## Security Best Practices

1. **Never commit** `.env.production` to version control
2. **Use different secrets** for each environment
3. **Rotate secrets regularly** (see SECRET_MANAGEMENT.md)
4. **Restrict file permissions**: `chmod 600 .env.production`
5. **Backup secrets securely** in encrypted storage
6. **Monitor for leaks** using tools like git-secrets
7. **Use strong, random values** for all secrets
8. **Validate configuration** before deployment
9. **Document changes** to environment variables
10. **Review access** to production secrets regularly

---

## Additional Resources

- [Secret Management Guidelines](./SECRET_MANAGEMENT.md)
- [Production Deployment Guide](../PRODUCTION_DEPLOYMENT.md)
- [Docker Compose Configuration](../docker-compose.prod.yml)
- [Nginx Configuration](../nginx/nginx.conf)

---

**Last Updated**: 2024-01-15  
**Maintained By**: DevOps Team  
**Review Schedule**: Quarterly
