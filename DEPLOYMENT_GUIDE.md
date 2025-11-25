# Production Deployment Guide

This guide provides comprehensive instructions for deploying the Proactive Accountability Assistant to a production server.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Deployment Script Usage](#deployment-script-usage)
4. [Step-by-Step Deployment](#step-by-step-deployment)
5. [Post-Deployment](#post-deployment)
6. [Rollback Procedures](#rollback-procedures)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### Server Requirements

- **Operating System**: Ubuntu 22.04 LTS (recommended) or similar Linux distribution
- **CPU**: Minimum 2 cores, recommended 4 cores
- **RAM**: Minimum 4GB, recommended 8GB
- **Disk**: Minimum 50GB SSD
- **Network**: Public IP address with ports 80, 443, and 22 accessible

### Software Requirements

- Docker 20.10 or later
- Docker Compose 2.0 or later
- Git
- Bash 4.0 or later

### Required Credentials

Before deployment, ensure you have:

- Anthropic API key (for Claude AI)
- Discord bot token and OAuth credentials
- Domain name (for SSL certificates)
- Email address (for Let's Encrypt notifications)

## Quick Start

For experienced users who have already configured their environment:

```bash
# 1. Clone the repository
git clone <repository-url>
cd accountability-assistant

# 2. Create and configure environment file
cp .env.production.example .env.production
nano .env.production  # Edit with your values

# 3. Run deployment script
./deploy.sh
```

## Deployment Script Usage

The `deploy.sh` script automates the entire deployment process with comprehensive checks and rollback capability.

### Basic Usage

```bash
./deploy.sh [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--skip-backup` | Skip pre-deployment database backup |
| `--skip-build` | Skip Docker image building (use existing images) |
| `--skip-health` | Skip post-deployment health checks |
| `--force` | Force deployment even with warnings |
| `--rollback` | Rollback to previous deployment |
| `--help` | Show help message |

### Examples

```bash
# Full deployment with all checks (recommended)
./deploy.sh

# Deploy without creating backup (faster, but risky)
./deploy.sh --skip-backup

# Deploy using existing images (for quick updates)
./deploy.sh --skip-build

# Force deployment despite warnings
./deploy.sh --force

# Rollback to previous deployment
./deploy.sh --rollback
```

## Step-by-Step Deployment

### Step 1: Server Preparation

1. **Update system packages**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Install Docker**:
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   ```

3. **Install Docker Compose**:
   ```bash
   sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

4. **Configure firewall**:
   ```bash
   sudo ufw allow 22/tcp   # SSH
   sudo ufw allow 80/tcp   # HTTP
   sudo ufw allow 443/tcp  # HTTPS
   sudo ufw enable
   ```

### Step 2: Environment Configuration

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd accountability-assistant
   ```

2. **Create production environment file**:
   ```bash
   cp .env.production.example .env.production
   ```

3. **Edit environment file**:
   ```bash
   nano .env.production
   ```

4. **Generate secure secrets**:
   ```bash
   # Generate JWT secret (64 characters)
   openssl rand -hex 32
   
   # Generate Fernet encryption key
   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   
   # Generate webhook secret
   openssl rand -hex 32
   
   # Generate database password
   openssl rand -base64 32
   ```

5. **Validate environment configuration**:
   ```bash
   bash scripts/validate-env.sh .env.production
   ```

### Step 3: Run Deployment

1. **Make deployment script executable** (if not already):
   ```bash
   chmod +x deploy.sh
   ```

2. **Run deployment**:
   ```bash
   ./deploy.sh
   ```

3. **Monitor deployment progress**:
   The script will:
   - Check prerequisites (Docker, disk space, etc.)
   - Validate environment configuration
   - Check port availability
   - Create pre-deployment backup
   - Build Docker images
   - Stop existing services (if any)
   - Start services in dependency order
   - Perform health checks
   - Test API endpoints
   - Display deployment status

### Step 4: SSL Certificate Setup

After successful deployment, configure SSL certificates:

```bash
# For production with Let's Encrypt
bash nginx/setup-ssl-prod.sh

# For development with self-signed certificates
bash nginx/setup-ssl-dev.sh
```

### Step 5: Configure Automated Backups

Set up automated database backups:

```bash
bash scripts/setup-backup-cron.sh
```

## Post-Deployment

### Verify Deployment

1. **Check service status**:
   ```bash
   docker-compose -f docker-compose.prod.yml ps
   ```

2. **Test health endpoints**:
   ```bash
   # Backend health
   curl http://localhost/api/health
   
   # Nginx health
   curl http://localhost/health
   ```

3. **View logs**:
   ```bash
   # All services
   docker-compose -f docker-compose.prod.yml logs -f
   
   # Specific service
   docker-compose -f docker-compose.prod.yml logs -f backend
   ```

### DNS Configuration

Point your domain to the server's IP address:

```
A Record: yourdomain.com → <server-ip>
A Record: www.yourdomain.com → <server-ip>
```

### Monitoring

1. **Check resource usage**:
   ```bash
   docker stats
   ```

2. **Monitor logs**:
   ```bash
   tail -f deployment.log
   ```

3. **Set up monitoring** (optional):
   - Configure Prometheus and Grafana
   - Set up log aggregation (ELK stack)
   - Configure alerting

## Rollback Procedures

### Automatic Rollback

The deployment script automatically rolls back on failure:

- If health checks fail
- If services fail to start
- If API endpoints are unreachable

### Manual Rollback

If you need to manually rollback:

```bash
./deploy.sh --rollback
```

This will:
1. Stop all running services
2. Display available backups
3. Provide instructions for restoration

### Complete Rollback Process

1. **Stop current deployment**:
   ```bash
   docker-compose -f docker-compose.prod.yml down
   ```

2. **Restore database from backup**:
   ```bash
   bash scripts/restore-database.sh backups/daily/<backup-file>
   ```

3. **Checkout previous code version**:
   ```bash
   git log --oneline  # Find previous commit
   git checkout <previous-commit-hash>
   ```

4. **Rebuild and restart**:
   ```bash
   docker-compose -f docker-compose.prod.yml build
   docker-compose -f docker-compose.prod.yml up -d
   ```

## Troubleshooting

### Common Issues

#### 1. Port Already in Use

**Error**: `Port 80 or 443 is already in use`

**Solution**:
```bash
# Find process using the port
sudo lsof -i :80
sudo lsof -i :443

# Stop the process
sudo systemctl stop apache2  # or nginx, or other service
```

#### 2. Environment Validation Failed

**Error**: `Environment validation failed`

**Solution**:
- Review the validation output
- Fix any missing or invalid environment variables
- Ensure all secrets are properly generated
- Run validation again: `bash scripts/validate-env.sh .env.production`

#### 3. Docker Build Failed

**Error**: `Failed to build Docker images`

**Solution**:
```bash
# Check Docker disk space
docker system df

# Clean up if needed
docker system prune -a

# Rebuild with verbose output
docker-compose -f docker-compose.prod.yml build --no-cache --progress=plain
```

#### 4. Health Checks Failing

**Error**: `Service health check failed`

**Solution**:
```bash
# Check service logs
docker-compose -f docker-compose.prod.yml logs <service-name>

# Check service status
docker-compose -f docker-compose.prod.yml ps

# Restart specific service
docker-compose -f docker-compose.prod.yml restart <service-name>
```

#### 5. Database Connection Failed

**Error**: `Backend cannot connect to database`

**Solution**:
```bash
# Check if PostgreSQL is running
docker-compose -f docker-compose.prod.yml ps postgres

# Check PostgreSQL logs
docker-compose -f docker-compose.prod.yml logs postgres

# Verify DATABASE_URL in .env.production matches POSTGRES_* variables
```

#### 6. Insufficient Disk Space

**Error**: `Insufficient disk space`

**Solution**:
```bash
# Check disk usage
df -h

# Clean up Docker resources
docker system prune -a --volumes

# Clean up old backups
bash scripts/cleanup-backups.sh

# Remove old logs
sudo journalctl --vacuum-time=7d
```

### Getting Help

If you encounter issues not covered here:

1. Check the deployment log: `cat deployment.log`
2. Review service logs: `docker-compose -f docker-compose.prod.yml logs`
3. Check Docker status: `docker ps -a`
4. Review system resources: `htop` or `docker stats`

### Useful Commands

```bash
# View all container logs
docker-compose -f docker-compose.prod.yml logs -f

# View specific service logs
docker-compose -f docker-compose.prod.yml logs -f backend

# Restart a service
docker-compose -f docker-compose.prod.yml restart backend

# Stop all services
docker-compose -f docker-compose.prod.yml down

# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Check service status
docker-compose -f docker-compose.prod.yml ps

# Execute command in container
docker exec -it accountability-backend-prod bash

# View resource usage
docker stats

# Clean up unused resources
docker system prune -a
```

## Security Best Practices

1. **Keep secrets secure**:
   - Never commit `.env.production` to version control
   - Use strong, randomly generated passwords
   - Rotate secrets regularly

2. **Keep software updated**:
   ```bash
   # Update system packages
   sudo apt update && sudo apt upgrade -y
   
   # Update Docker images
   docker-compose -f docker-compose.prod.yml pull
   docker-compose -f docker-compose.prod.yml up -d
   ```

3. **Monitor logs**:
   - Regularly review application logs
   - Set up alerts for errors
   - Monitor for suspicious activity

4. **Backup regularly**:
   - Verify automated backups are running
   - Test backup restoration periodically
   - Store backups in multiple locations

5. **Use SSL/TLS**:
   - Always use HTTPS in production
   - Keep SSL certificates up to date
   - Use strong cipher suites

## Maintenance

### Regular Maintenance Tasks

**Daily**:
- Monitor service health
- Check error logs
- Verify backups completed

**Weekly**:
- Review resource usage
- Check disk space
- Review security logs

**Monthly**:
- Update dependencies
- Test backup restoration
- Review and rotate logs
- Security audit

### Updating the Application

```bash
# 1. Pull latest code
git pull origin main

# 2. Review changes
git log --oneline -10

# 3. Update environment if needed
nano .env.production

# 4. Deploy update
./deploy.sh

# 5. Verify deployment
curl http://localhost/api/health
```

## Support

For additional support:

- Review the [Architecture Documentation](ARCHITECTURE.md)
- Check the [Environment Variables Guide](docs/ENVIRONMENT_VARIABLES.md)
- Review the [Backup System Documentation](scripts/BACKUP_SYSTEM.md)
- Consult the [Nginx Configuration Guide](nginx/README.md)
