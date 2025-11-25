# Logging Quick Reference

## Quick Commands

### View Logs

```bash
# View backend logs
./scripts/view-logs.sh backend

# Follow logs in real-time
./scripts/view-logs.sh backend --follow

# View last 100 lines
./scripts/view-logs.sh backend --tail 100

# View all services
./scripts/view-logs.sh --all

# View persistent volume logs
./scripts/view-logs.sh --volume
```

### Log Rotation

```bash
# Manual log rotation
./scripts/rotate-logs.sh

# Setup automated rotation (daily at 2 AM)
sudo ./scripts/setup-log-rotation-cron.sh

# View rotation logs
tail -f /var/log/log-rotation.log
```

### Search Logs

```bash
# Search for errors
docker-compose -f docker-compose.prod.yml logs backend | grep -i error

# Search with context
docker-compose -f docker-compose.prod.yml logs backend | grep -C 5 "error"

# Search by correlation ID
docker-compose -f docker-compose.prod.yml logs backend | grep "correlation_id"
```

### Export Logs

```bash
# Export to file
docker-compose -f docker-compose.prod.yml logs backend > logs.txt

# Export with timestamp
docker-compose -f docker-compose.prod.yml logs -t backend > logs-$(date +%Y%m%d).txt
```

## Log Locations

| Component | Location | Format |
|-----------|----------|--------|
| Docker Logs | `/var/lib/docker/containers/` | JSON |
| App Logs | Docker volume `accountability-app-logs` | JSON |
| Nginx Logs | Docker volume `accountability-nginx-logs` | Text |
| Rotation Logs | `/var/log/log-rotation.log` | Text |

## Log Retention

| Type | Retention | Compression |
|------|-----------|-------------|
| Backend | 10 files × 100MB | After 7 days |
| Database | 5 files × 50MB | After 7 days |
| Nginx | 10 files × 100MB | After 7 days |
| Persistent | 30 days | After 7 days |

## Environment Variables

```bash
# Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Set log format (json, text)
LOG_FORMAT=json
```

## Common Issues

### Disk Space Full
```bash
# Check disk usage
df -h

# Run log rotation
./scripts/rotate-logs.sh

# Clean Docker system
docker system prune -a
```

### Cannot Access Logs
```bash
# Check volume exists
docker volume ls | grep accountability-app-logs

# Recreate volume
docker volume rm accountability-app-logs
docker volume create accountability-app-logs
```

### High Log Volume
```bash
# Increase log level to reduce volume
LOG_LEVEL=WARNING

# Restart services
docker-compose -f docker-compose.prod.yml restart
```

## Log Format

### JSON Structure
```json
{
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "level": "INFO",
  "logger": "app.api.projects",
  "message": "Project created successfully",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Services

| Service | Container Name | Log Size | Files |
|---------|---------------|----------|-------|
| backend | accountability-backend-prod | 100MB | 10 |
| celery-worker | accountability-celery-worker-prod | 100MB | 7 |
| celery-beat | accountability-celery-beat-prod | 50MB | 5 |
| discord-bot | accountability-discord-bot-prod | 50MB | 5 |
| postgres | accountability-db-prod | 50MB | 5 |
| redis | accountability-redis-prod | 50MB | 5 |
| nginx | accountability-nginx-prod | 100MB | 10 |
| frontend | accountability-frontend-prod | 50MB | 5 |

## Monitoring

### Check Log Volume
```bash
# Docker disk usage
docker system df -v

# Volume size
docker system df -v | grep accountability-app-logs
```

### Check Service Health
```bash
# All services
docker-compose -f docker-compose.prod.yml ps

# Specific service
docker-compose -f docker-compose.prod.yml ps backend
```

## Documentation

- Full Guide: [LOGGING_CONFIGURATION.md](LOGGING_CONFIGURATION.md)
- Deployment: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- Environment: [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md)
