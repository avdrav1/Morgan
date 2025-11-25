# Deployment Quick Reference

Quick reference guide for the production deployment script.

## Basic Commands

```bash
# Full deployment (recommended)
./deploy.sh

# Deploy without backup
./deploy.sh --skip-backup

# Deploy with existing images
./deploy.sh --skip-build

# Force deployment with warnings
./deploy.sh --force

# Rollback to previous deployment
./deploy.sh --rollback

# Show help
./deploy.sh --help
```

## Pre-Deployment Checklist

- [ ] Server meets minimum requirements (2 CPU, 4GB RAM, 50GB disk)
- [ ] Docker and Docker Compose installed
- [ ] Firewall configured (ports 80, 443, 22)
- [ ] `.env.production` file created and configured
- [ ] All secrets generated (JWT, encryption keys, passwords)
- [ ] Environment validation passed: `bash scripts/validate-env.sh .env.production`
- [ ] Domain DNS configured (if using SSL)

## Deployment Process

The script performs these steps automatically:

1. **Prerequisites Check**
   - Docker installation
   - Docker Compose installation
   - Disk space (minimum 5GB free)
   - Compose and environment files exist

2. **Environment Validation**
   - All required variables set
   - Secrets not using default values
   - URLs properly formatted
   - API keys valid format

3. **Port Availability**
   - Port 80 available
   - Port 443 available

4. **Pre-Deployment Backup**
   - Database backup created
   - Stored in `backups/` directory

5. **Build Docker Images**
   - Backend image
   - Frontend image
   - Discord bot image
   - Nginx image

6. **Service Startup** (in order)
   - PostgreSQL
   - Redis
   - Backend
   - Celery Worker
   - Celery Beat
   - Discord Bot
   - Frontend
   - Nginx

7. **Health Checks**
   - PostgreSQL health
   - Redis health
   - Backend health
   - Frontend health
   - Nginx health

8. **API Tests**
   - Backend health endpoint
   - Nginx routing

## Post-Deployment

### Verify Deployment

```bash
# Check service status
docker-compose -f docker-compose.prod.yml ps

# Test health endpoints
curl http://localhost/api/health
curl http://localhost/health

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

### Next Steps

1. Configure SSL certificates:
   ```bash
   bash nginx/setup-ssl-prod.sh
   ```

2. Set up automated backups:
   ```bash
   bash scripts/setup-backup-cron.sh
   ```

3. Configure DNS to point to server IP

4. Monitor deployment:
   ```bash
   tail -f deployment.log
   ```

## Rollback

### Automatic Rollback

The script automatically rolls back if:
- Health checks fail
- Services fail to start
- API endpoints unreachable

### Manual Rollback

```bash
# Quick rollback
./deploy.sh --rollback

# Manual rollback process
docker-compose -f docker-compose.prod.yml down
bash scripts/restore-database.sh backups/daily/<backup-file>
git checkout <previous-commit>
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Port Conflicts

```bash
# Find process using port
sudo lsof -i :80
sudo lsof -i :443

# Stop conflicting service
sudo systemctl stop <service-name>
```

### Build Failures

```bash
# Clean Docker cache
docker system prune -a

# Rebuild with verbose output
docker-compose -f docker-compose.prod.yml build --no-cache --progress=plain
```

### Health Check Failures

```bash
# Check service logs
docker-compose -f docker-compose.prod.yml logs <service-name>

# Restart service
docker-compose -f docker-compose.prod.yml restart <service-name>

# Check container status
docker ps -a
```

### Database Connection Issues

```bash
# Check PostgreSQL status
docker-compose -f docker-compose.prod.yml ps postgres

# View PostgreSQL logs
docker-compose -f docker-compose.prod.yml logs postgres

# Verify DATABASE_URL matches POSTGRES_* variables in .env.production
```

## Useful Commands

```bash
# View all logs
docker-compose -f docker-compose.prod.yml logs -f

# View specific service logs
docker-compose -f docker-compose.prod.yml logs -f backend

# Restart service
docker-compose -f docker-compose.prod.yml restart backend

# Stop all services
docker-compose -f docker-compose.prod.yml down

# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# Execute command in container
docker exec -it accountability-backend-prod bash

# View resource usage
docker stats

# Clean up
docker system prune -a
```

## Environment Variables

### Required Variables

```bash
# Application
ENVIRONMENT=production
DEBUG=False

# Database
POSTGRES_USER=<username>
POSTGRES_PASSWORD=<secure-password>
POSTGRES_DB=<database-name>
DATABASE_URL=postgresql://<user>:<pass>@postgres:5432/<db>

# Redis
REDIS_URL=redis://redis:6379/0

# Security
JWT_SECRET_KEY=<64-char-secret>
ENCRYPTION_KEY=<fernet-key>
WEBHOOK_SECRET=<32-char-secret>

# URLs
FRONTEND_URL=https://yourdomain.com
BACKEND_URL=https://yourdomain.com/api
VITE_API_URL=https://yourdomain.com/api
CORS_ORIGINS=["https://yourdomain.com"]

# External APIs
ANTHROPIC_API_KEY=sk-ant-...
DISCORD_TOKEN=<bot-token>
DISCORD_CLIENT_ID=<client-id>
DISCORD_CLIENT_SECRET=<client-secret>
DISCORD_REDIRECT_URI=https://yourdomain.com/api/auth/discord/callback

# SSL (optional)
DOMAIN=yourdomain.com
LETSENCRYPT_EMAIL=admin@yourdomain.com
```

### Generate Secrets

```bash
# JWT secret (64 characters)
openssl rand -hex 32

# Fernet encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Webhook secret
openssl rand -hex 32

# Database password
openssl rand -base64 32
```

## Monitoring

### Check Service Health

```bash
# All services
docker-compose -f docker-compose.prod.yml ps

# Specific service
docker inspect --format='{{.State.Health.Status}}' accountability-backend-prod
```

### View Logs

```bash
# Deployment log
tail -f deployment.log

# Service logs
docker-compose -f docker-compose.prod.yml logs -f

# Nginx access logs
docker exec accountability-nginx-prod tail -f /var/log/nginx/access.log

# Nginx error logs
docker exec accountability-nginx-prod tail -f /var/log/nginx/error.log
```

### Resource Usage

```bash
# Real-time stats
docker stats

# Disk usage
docker system df

# Container sizes
docker ps -s
```

## Backup & Restore

### Create Backup

```bash
# Manual backup
bash scripts/backup-database.sh

# Automated backups (cron)
bash scripts/setup-backup-cron.sh
```

### Restore Backup

```bash
# List available backups
ls -lh backups/daily/
ls -lh backups/weekly/
ls -lh backups/monthly/

# Restore from backup
bash scripts/restore-database.sh backups/daily/<backup-file>
```

## Security

### Firewall

```bash
# Configure UFW
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

### SSL Certificates

```bash
# Production (Let's Encrypt)
bash nginx/setup-ssl-prod.sh

# Development (self-signed)
bash nginx/setup-ssl-dev.sh

# Renew certificates
bash nginx/renew-ssl.sh

# Test SSL configuration
bash nginx/test-ssl.sh
```

### Updates

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Docker images
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

# Update application
git pull origin main
./deploy.sh
```

## Support Files

- **Full Guide**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **Environment Variables**: [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md)
- **Backup System**: [scripts/BACKUP_SYSTEM.md](scripts/BACKUP_SYSTEM.md)
- **Nginx Configuration**: [nginx/README.md](nginx/README.md)
- **SSL Setup**: [nginx/SSL_SETUP.md](nginx/SSL_SETUP.md)
