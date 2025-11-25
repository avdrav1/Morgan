# Logging Configuration Guide

## Overview

This document describes the comprehensive logging and log rotation configuration for the Proactive Accountability Assistant production deployment. The system uses structured JSON logging with automatic rotation, compression, and retention policies.

## Architecture

### Logging Components

1. **Docker Container Logs**: JSON-formatted logs from all containers
2. **Application Logs**: Structured JSON logs from backend services
3. **Nginx Logs**: Access and error logs from the reverse proxy
4. **Persistent Log Volume**: Shared volume for application logs

### Log Flow

```
Application → Structured Logger → Docker JSON Driver → Log Files
                                                      ↓
                                              Persistent Volume
                                                      ↓
                                              Log Rotation Script
                                                      ↓
                                          Compressed Archives
```

## Configuration Details

### Docker Logging Configuration

All services in `docker-compose.prod.yml` use the `json-file` logging driver with the following configuration:

#### Backend Services (backend, celery-worker)
- **Max Size**: 100MB per log file
- **Max Files**: 10 files (1GB total)
- **Compression**: Enabled
- **Rotation**: Automatic when size limit reached

#### Database Services (postgres, redis)
- **Max Size**: 50MB per log file
- **Max Files**: 5 files (250MB total)
- **Compression**: Enabled

#### Frontend & Bot Services
- **Max Size**: 50MB per log file
- **Max Files**: 5 files (250MB total)
- **Compression**: Enabled

#### Nginx
- **Max Size**: 100MB per log file
- **Max Files**: 10 files (1GB total)
- **Compression**: Enabled

### Persistent Log Volume

A dedicated Docker volume `accountability-app-logs` is mounted to all services at `/var/log/app` for centralized log storage.

**Volume Configuration:**
```yaml
volumes:
  app_logs:
    name: accountability-app-logs
```

**Mounted Services:**
- backend
- celery-worker
- celery-beat
- discord-bot
- postgres
- redis

### Application Logging (Backend)

The backend uses structured JSON logging configured in `backend/app/core/logging_config.py`.

**Features:**
- JSON-formatted log messages
- Correlation IDs for request tracking
- PII redaction (emails, Discord IDs, UUIDs)
- Configurable log levels via `LOG_LEVEL` environment variable
- Automatic context propagation

**Log Format:**
```json
{
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "level": "INFO",
  "logger": "app.api.projects",
  "message": "Project created successfully",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "[UUID_REDACTED]",
  "project_name": "My Project"
}
```

**Log Levels:**
- **DEBUG**: Detailed diagnostic information (development only)
- **INFO**: General informational messages (production default)
- **WARNING**: Warning messages for potentially harmful situations
- **ERROR**: Error messages for serious problems
- **CRITICAL**: Critical messages for very serious errors

### Environment Variables

Configure logging behavior with these environment variables:

```bash
# Log level for all services
LOG_LEVEL=INFO  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL

# Log format (backend only)
LOG_FORMAT=json  # Options: json, text
```

## Log Rotation

### Automatic Rotation

Docker automatically rotates logs when they reach the configured size limit. Rotated logs are compressed and stored with a numeric suffix.

**Example:**
```
container.log
container.log.1.gz
container.log.2.gz
```

### Manual Rotation Script

The `scripts/rotate-logs.sh` script provides additional log management:

**Features:**
- Compresses logs older than 7 days
- Deletes logs older than 30 days
- Provides log statistics
- Safe cleanup with temporary containers

**Usage:**
```bash
# Run manual log rotation
./scripts/rotate-logs.sh
```

**Retention Policy:**
- Keep logs for 30 days
- Compress logs older than 7 days
- Delete logs older than 30 days

### Automated Rotation with Cron

Set up daily automated log rotation:

```bash
# Setup cron job (runs daily at 2 AM)
sudo ./scripts/setup-log-rotation-cron.sh
```

**Cron Schedule:**
- **Frequency**: Daily at 2:00 AM
- **Log Output**: `/var/log/log-rotation.log`

**View Cron Logs:**
```bash
tail -f /var/log/log-rotation.log
```

## Viewing Logs

### View Container Logs

Use the `scripts/view-logs.sh` script for easy log access:

```bash
# View backend logs (last 50 lines)
./scripts/view-logs.sh backend

# View backend logs (last 100 lines)
./scripts/view-logs.sh backend --tail 100

# Follow backend logs in real-time
./scripts/view-logs.sh backend --follow

# View logs since specific time
./scripts/view-logs.sh backend --since 2024-01-01T00:00:00

# View all service logs
./scripts/view-logs.sh --all

# View logs from persistent volume
./scripts/view-logs.sh --volume
```

### Direct Docker Commands

```bash
# View logs for a specific service
docker-compose -f docker-compose.prod.yml logs backend

# Follow logs in real-time
docker-compose -f docker-compose.prod.yml logs -f backend

# View last 100 lines
docker-compose -f docker-compose.prod.yml logs --tail 100 backend

# View logs from all services
docker-compose -f docker-compose.prod.yml logs

# View logs with timestamps
docker-compose -f docker-compose.prod.yml logs -t backend
```

### Access Persistent Volume Logs

```bash
# Create temporary container to access logs
docker run --rm \
  --mount source=accountability-app-logs,target=/var/log/app \
  alpine:latest \
  sh -c "ls -lah /var/log/app && tail -n 50 /var/log/app/*.log"
```

## Log Analysis

### Search Logs

```bash
# Search for specific text in backend logs
docker-compose -f docker-compose.prod.yml logs backend | grep "error"

# Search with context (5 lines before and after)
docker-compose -f docker-compose.prod.yml logs backend | grep -C 5 "error"

# Search for correlation ID
docker-compose -f docker-compose.prod.yml logs backend | grep "550e8400-e29b-41d4-a716-446655440000"
```

### Filter by Time

```bash
# Logs since 1 hour ago
docker-compose -f docker-compose.prod.yml logs --since 1h backend

# Logs since specific timestamp
docker-compose -f docker-compose.prod.yml logs --since 2024-01-01T00:00:00 backend

# Logs until specific timestamp
docker-compose -f docker-compose.prod.yml logs --until 2024-01-01T23:59:59 backend
```

### Export Logs

```bash
# Export logs to file
docker-compose -f docker-compose.prod.yml logs backend > backend-logs.txt

# Export logs with timestamps
docker-compose -f docker-compose.prod.yml logs -t backend > backend-logs-$(date +%Y%m%d).txt

# Export all logs
docker-compose -f docker-compose.prod.yml logs > all-logs-$(date +%Y%m%d).txt
```

## Log Aggregation (Optional)

For production deployments, consider integrating with log aggregation services:

### Option 1: ELK Stack (Elasticsearch, Logstash, Kibana)

1. Install Filebeat on the host
2. Configure Filebeat to read Docker logs
3. Send logs to Elasticsearch
4. Visualize with Kibana

### Option 2: Cloud Services

- **AWS CloudWatch**: Use CloudWatch Logs driver
- **Google Cloud Logging**: Use Google Cloud Logging driver
- **Datadog**: Use Datadog agent
- **Splunk**: Use Splunk logging driver

### Example: CloudWatch Configuration

```yaml
logging:
  driver: "awslogs"
  options:
    awslogs-region: "us-east-1"
    awslogs-group: "accountability-assistant"
    awslogs-stream: "backend"
```

## Monitoring and Alerts

### Log-Based Alerts

Set up alerts for critical log patterns:

1. **Error Rate Alerts**: Alert when error rate exceeds threshold
2. **Critical Errors**: Immediate alert for CRITICAL level logs
3. **Disk Space**: Alert when log volume approaches capacity
4. **Service Failures**: Alert on service restart patterns

### Log Metrics

Track these metrics:

- **Log Volume**: Bytes written per service per hour
- **Error Rate**: Errors per minute
- **Response Time**: From correlation ID tracking
- **Service Health**: Based on health check logs

## Troubleshooting

### Issue: Logs Not Appearing

**Check:**
1. Verify service is running: `docker-compose -f docker-compose.prod.yml ps`
2. Check log driver configuration in docker-compose.prod.yml
3. Verify volume mount: `docker volume inspect accountability-app-logs`

**Solution:**
```bash
# Restart service
docker-compose -f docker-compose.prod.yml restart backend

# Check service logs
docker-compose -f docker-compose.prod.yml logs backend
```

### Issue: Disk Space Full

**Check:**
```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df

# Check log volume size
docker system df -v | grep accountability-app-logs
```

**Solution:**
```bash
# Run log rotation
./scripts/rotate-logs.sh

# Clean up old Docker logs
docker system prune -a --volumes
```

### Issue: Cannot Access Logs

**Check:**
```bash
# Verify volume exists
docker volume ls | grep accountability-app-logs

# Check volume permissions
docker run --rm \
  --mount source=accountability-app-logs,target=/var/log/app \
  alpine:latest \
  ls -la /var/log/app
```

**Solution:**
```bash
# Recreate volume if needed
docker volume rm accountability-app-logs
docker volume create accountability-app-logs

# Restart services
docker-compose -f docker-compose.prod.yml restart
```

### Issue: High Log Volume

**Check:**
```bash
# Check log sizes
docker system df -v | grep accountability

# Check service log levels
docker-compose -f docker-compose.prod.yml exec backend env | grep LOG_LEVEL
```

**Solution:**
```bash
# Increase log level to reduce volume
# Edit .env file
LOG_LEVEL=WARNING

# Restart services
docker-compose -f docker-compose.prod.yml restart

# Reduce log retention
# Edit scripts/rotate-logs.sh
RETENTION_DAYS=14
```

## Best Practices

### Production Logging

1. **Use INFO level**: Balance between detail and volume
2. **Enable compression**: Save disk space
3. **Set retention policies**: Prevent disk exhaustion
4. **Monitor log volume**: Track growth trends
5. **Use correlation IDs**: Track requests across services
6. **Redact PII**: Protect user privacy
7. **Centralize logs**: Use log aggregation for large deployments

### Development Logging

1. **Use DEBUG level**: Get detailed information
2. **Disable compression**: Easier to read
3. **Shorter retention**: Save disk space
4. **Local file logging**: Faster access

### Security

1. **Redact sensitive data**: Passwords, tokens, API keys
2. **Limit log access**: Use proper file permissions
3. **Encrypt logs**: For compliance requirements
4. **Audit log access**: Track who views logs
5. **Secure log transmission**: Use TLS for remote logging

## Performance Considerations

### Log Volume Impact

- **High log volume**: Can impact disk I/O and application performance
- **Compression**: Reduces disk usage but adds CPU overhead
- **Rotation frequency**: Balance between disk usage and file management

### Optimization Tips

1. **Adjust log levels**: Use WARNING or ERROR in production if volume is high
2. **Filter noisy loggers**: Reduce third-party library logging
3. **Async logging**: Use async handlers for high-throughput services
4. **Batch writes**: Buffer log writes to reduce I/O
5. **Separate volumes**: Use different volumes for different services

## Compliance and Retention

### Regulatory Requirements

Different industries have different log retention requirements:

- **GDPR**: 30 days to 6 months
- **HIPAA**: 6 years
- **PCI DSS**: 1 year
- **SOX**: 7 years

### Implementing Compliance

1. **Configure retention**: Adjust `RETENTION_DAYS` in rotation script
2. **Backup logs**: Archive logs to long-term storage
3. **Encrypt archives**: Use encryption for sensitive logs
4. **Document policy**: Maintain log retention policy document
5. **Audit compliance**: Regular reviews of log management

## Summary

The logging configuration provides:

✅ **Structured JSON logging** for easy parsing and analysis  
✅ **Automatic log rotation** to prevent disk exhaustion  
✅ **Compression** to save disk space  
✅ **Persistent storage** for log retention  
✅ **Easy log access** with helper scripts  
✅ **PII redaction** for privacy protection  
✅ **Correlation IDs** for request tracking  
✅ **Flexible configuration** via environment variables  

For questions or issues, refer to the troubleshooting section or consult the deployment documentation.
