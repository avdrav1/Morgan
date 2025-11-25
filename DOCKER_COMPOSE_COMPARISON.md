# Docker Compose: Development vs Production

This document highlights the key differences between the development (`docker-compose.yml`) and production (`docker-compose.prod.yml`) configurations.

## Key Differences

### 1. Volume Mounts

**Development:**
- Code directories mounted for hot-reload
- `./backend:/app` - Backend code changes reflected immediately
- `./frontend:/app` - Frontend code changes reflected immediately
- `./discord-bot:/app` - Bot code changes reflected immediately

**Production:**
- No code volume mounts
- Code baked into Docker images
- Only data volumes (postgres_data, redis_data, nginx_logs)

### 2. Resource Limits

**Development:**
- No resource limits configured
- Services can use unlimited CPU and memory

**Production:**
- CPU limits: 0.25-2.0 cores per service
- Memory limits: 128MB-2GB per service
- Resource reservations ensure minimum allocation
- Total minimum: 4 CPU cores, 8GB RAM

### 3. Restart Policies

**Development:**
- No restart policy (default: `no`)
- Services don't restart on failure

**Production:**
- `restart: unless-stopped` on all services
- Automatic restart on failure
- Services persist across host reboots

### 4. Health Checks

**Development:**
- Basic health checks on postgres and redis only
- 10-second intervals

**Production:**
- Comprehensive health checks on all services
- 30-60 second intervals
- Start period configured for slow-starting services
- Automatic restart on health check failure

### 5. Networking

**Development:**
- Default bridge network
- All services can communicate

**Production:**
- Explicit networks defined:
  - `backend-network`: Database, cache, backend services
  - `frontend-network`: Frontend-facing services
- Network isolation for security

### 6. Logging

**Development:**
- Default logging (unlimited)
- Logs stored in Docker's default location

**Production:**
- JSON-formatted logs
- Log rotation configured (10MB max, 3-5 files)
- Structured logging for analysis

### 7. Application Servers

**Development:**
- Backend: `uvicorn` with `--reload` flag
- Frontend: Vite dev server (`npm run dev`)

**Production:**
- Backend: `gunicorn` with 4 workers + uvicorn workers
- Frontend: Production build served by Nginx
- No hot-reload or development features

### 8. Environment Variables

**Development:**
- Hardcoded development values
- Weak passwords acceptable
- `ENVIRONMENT=development`

**Production:**
- All values from `.env.production`
- Strong passwords required
- `ENVIRONMENT=production`
- Additional security variables (CORS, JWT)

### 9. Port Exposure

**Development:**
- Multiple ports exposed:
  - 5432 (PostgreSQL)
  - 6379 (Redis)
  - 8000 (Backend)
  - 5173 (Frontend)

**Production:**
- Only ports 80 and 443 exposed (Nginx)
- All other services internal only
- Reverse proxy handles all external traffic

### 10. Service Configuration

**Development:**
- Celery: Single worker, no concurrency limit
- Redis: Default configuration
- PostgreSQL: Default configuration

**Production:**
- Celery: 2 concurrent workers
- Redis: AOF persistence enabled
- PostgreSQL: Optimized for production
- Gunicorn: 4 workers with 120s timeout

### 11. Build Process

**Development:**
- Simple builds
- Development dependencies included
- No optimization

**Production:**
- Multi-stage builds (frontend)
- Production dependencies only
- Minification and optimization
- Smaller image sizes

### 12. Additional Services

**Development:**
- No reverse proxy
- No SSL termination

**Production:**
- Nginx reverse proxy
- SSL/TLS termination
- Security headers
- Rate limiting
- Static file serving

## Migration Checklist

When moving from development to production:

- [ ] Create `.env.production` from `.env.production.example`
- [ ] Generate strong passwords and secrets
- [ ] Configure domain name and DNS
- [ ] Set up SSL certificates
- [ ] Configure Nginx reverse proxy
- [ ] Review and adjust resource limits
- [ ] Set up backup procedures
- [ ] Configure monitoring and alerting
- [ ] Test deployment in staging environment
- [ ] Plan rollback procedures

## Commands

### Development

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Rebuild after code changes
docker-compose up -d --build
```

### Production

```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop all services
docker-compose -f docker-compose.prod.yml down

# Rebuild and deploy
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

## Resource Requirements

### Development
- Minimum: 2 CPU cores, 4GB RAM
- Recommended: 4 CPU cores, 8GB RAM

### Production
- Minimum: 4 CPU cores, 8GB RAM
- Recommended: 8 CPU cores, 16GB RAM
- For high traffic: 16+ CPU cores, 32GB+ RAM

## Security Considerations

### Development
- Weak passwords acceptable
- All ports exposed
- Debug mode enabled
- No SSL required

### Production
- Strong passwords required
- Only ports 80/443 exposed
- Debug mode disabled
- SSL/TLS required
- Security headers configured
- Rate limiting enabled
- Network isolation
- Log monitoring
