# Production Deployment Guide

This document provides an overview of the production Docker Compose configuration for the Proactive Accountability Assistant.

## Documentation Index

- **[Environment Variables Reference](docs/ENVIRONMENT_VARIABLES.md)** - Complete reference for all environment variables
- **[Secret Management Guidelines](docs/SECRET_MANAGEMENT.md)** - Best practices for managing secrets and credentials
- **[Scripts Documentation](scripts/README.md)** - Utility scripts for validation and deployment

## Overview

The production deployment uses `docker-compose.prod.yml` which includes:

- **Production-optimized service configurations**
- **Resource limits (CPU and memory) for all services**
- **Automatic restart policies** (`unless-stopped`)
- **Network isolation** (separate backend and frontend networks)
- **Health checks** for all services
- **Structured logging** with rotation
- **Persistent volumes** for data storage

## Architecture

### Services

1. **PostgreSQL** - Database with persistent storage
2. **Redis** - Cache and message broker with AOF persistence
3. **Backend** - FastAPI application with Gunicorn (4 workers)
4. **Celery Worker** - Background task processor
5. **Celery Beat** - Task scheduler
6. **Discord Bot** - Discord integration service
7. **Frontend** - React application served by Nginx
8. **Nginx** - Reverse proxy with SSL termination

### Networks

- **backend-network**: Isolated network for backend services (postgres, redis, backend, celery, discord-bot)
- **frontend-network**: Network for frontend-facing services (nginx, backend, frontend)

### Volumes

- **postgres_data**: PostgreSQL database files
- **redis_data**: Redis persistence files (RDB snapshots + AOF)
- **nginx_logs**: Nginx access and error logs
- **nginx_certs**: SSL/TLS certificates
- **certbot_www**: Certbot webroot for certificate challenges

See [Redis Persistence Documentation](redis/README.md) for details on Redis data persistence configuration.

## Resource Limits

### PostgreSQL
- CPU: 0.5-1.0 cores
- Memory: 512MB-1GB

### Redis
- CPU: 0.25-0.5 cores
- Memory: 256MB-512MB

### Backend
- CPU: 1.0-2.0 cores
- Memory: 1GB-2GB

### Celery Worker
- CPU: 0.5-1.0 cores
- Memory: 512MB-1GB

### Celery Beat
- CPU: 0.25-0.5 cores
- Memory: 256MB-512MB

### Discord Bot
- CPU: 0.25-0.5 cores
- Memory: 256MB-512MB

### Frontend
- CPU: 0.25-0.5 cores
- Memory: 128MB-256MB

### Nginx
- CPU: 0.5-1.0 cores
- Memory: 256MB-512MB

**Total Minimum Requirements**: 4 CPU cores, 8GB RAM

## Configuration

### Environment Variables

Copy `.env.production.example` to `.env.production` and configure:

#### Required Variables

- `POSTGRES_USER` - Database username
- `POSTGRES_PASSWORD` - Database password (use strong password)
- `POSTGRES_DB` - Database name
- `JWT_SECRET_KEY` - Secret key for JWT tokens (generate with `openssl rand -hex 32`)
- `ANTHROPIC_API_KEY` - Anthropic API key for LLM features
- `DISCORD_TOKEN` - Discord bot token
- `DISCORD_CLIENT_ID` - Discord OAuth client ID
- `DISCORD_CLIENT_SECRET` - Discord OAuth client secret
- `FRONTEND_URL` - Public URL of your application (e.g., https://yourdomain.com)
- `BACKEND_URL` - Public URL of your API (e.g., https://yourdomain.com/api)
- `VITE_API_URL` - API URL for frontend (same as BACKEND_URL)
- `CORS_ORIGINS` - Allowed CORS origins (same as FRONTEND_URL)
- `DISCORD_REDIRECT_URI` - Discord OAuth redirect URI
- `DISCORD_WEBHOOK_URL` - Discord webhook URL for notifications

### Health Checks

All services include health checks with automatic restart on failure:

- **PostgreSQL**: `pg_isready` check every 30s
- **Redis**: `redis-cli ping` check every 30s
- **Backend**: HTTP check on `/health` endpoint every 30s
- **Celery Worker**: Celery inspect ping every 60s
- **Celery Beat**: PID file check every 60s
- **Discord Bot**: Process check every 60s
- **Frontend**: HTTP check on root endpoint every 30s
- **Nginx**: HTTP check on `/health` endpoint every 30s

### Logging

All services use JSON-formatted logging with rotation:

- **Max file size**: 10MB (5MB for high-traffic services)
- **Max files**: 3-5 files retained
- **Format**: JSON for structured logging

## Deployment

### Prerequisites

1. Docker Engine 20.10+
2. Docker Compose 2.0+
3. Domain name with DNS configured
4. SSL certificates (Let's Encrypt recommended)

### Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Configure environment**
   ```bash
   cp .env.production.example .env.production
   # Edit .env.production with your values
   nano .env.production
   ```

3. **Build images**
   ```bash
   docker-compose -f docker-compose.prod.yml build
   ```

4. **Start services**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

5. **Verify deployment**
   ```bash
   docker-compose -f docker-compose.prod.yml ps
   docker-compose -f docker-compose.prod.yml logs
   ```

6. **Check health**
   ```bash
   curl http://localhost/health
   ```

## Monitoring

### View Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend

# Last 100 lines
docker-compose -f docker-compose.prod.yml logs --tail=100
```

### Check Service Status

```bash
docker-compose -f docker-compose.prod.yml ps
```

### Resource Usage

```bash
docker stats
```

## Maintenance

### Update Application

```bash
# Pull latest code
git pull

# Rebuild images
docker-compose -f docker-compose.prod.yml build

# Restart services
docker-compose -f docker-compose.prod.yml up -d
```

### Database Migrations

Migrations run automatically on backend startup. To run manually:

```bash
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### Backup Database

```bash
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} > backup.sql
```

### Restore Database

```bash
docker-compose -f docker-compose.prod.yml exec -T postgres psql -U ${POSTGRES_USER} ${POSTGRES_DB} < backup.sql
```

### Backup Redis

```bash
# Trigger immediate snapshot
docker exec accountability-redis-prod redis-cli BGSAVE

# Copy backup files
docker cp accountability-redis-prod:/data/dump.rdb ./backup/redis-dump-$(date +%Y%m%d).rdb
docker cp accountability-redis-prod:/data/appendonly.aof ./backup/redis-aof-$(date +%Y%m%d).aof
```

See [Redis Persistence Quick Reference](redis/PERSISTENCE_QUICK_REFERENCE.md) for more backup and restore procedures.

## Troubleshooting

### Service Won't Start

1. Check logs: `docker-compose -f docker-compose.prod.yml logs <service-name>`
2. Verify environment variables in `.env.production`
3. Check resource availability: `docker stats`
4. Verify network connectivity: `docker network ls`

### Database Connection Issues

1. Verify PostgreSQL is healthy: `docker-compose -f docker-compose.prod.yml ps postgres`
2. Check database logs: `docker-compose -f docker-compose.prod.yml logs postgres`
3. Test connection: `docker-compose -f docker-compose.prod.yml exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}`

### High Memory Usage

1. Check resource usage: `docker stats`
2. Review service logs for memory leaks
3. Adjust resource limits in `docker-compose.prod.yml`
4. Consider scaling horizontally

### SSL/HTTPS Issues

1. Verify Nginx configuration
2. Check SSL certificate validity
3. Review Nginx logs: `docker-compose -f docker-compose.prod.yml logs nginx`

## Security Notes

- Never commit `.env.production` to version control
- Use strong passwords for database and JWT secret
- Keep SSL certificates secure and up to date
- Regularly update Docker images for security patches
- Monitor logs for suspicious activity
- Use firewall rules to restrict access to ports 80, 443, and 22 only

## Scaling

To scale services horizontally:

```bash
# Scale celery workers
docker-compose -f docker-compose.prod.yml up -d --scale celery-worker=3

# Scale backend (requires load balancer)
docker-compose -f docker-compose.prod.yml up -d --scale backend=2
```

Note: Scaling backend requires additional Nginx configuration for load balancing.

## Next Steps

1. Configure Nginx reverse proxy (Task 2)
2. Set up SSL/TLS certificates (Task 3)
3. Implement backup automation (Task 9)
4. Configure monitoring and alerting (Task 15)
