# Production Deployment Design Document

## Overview

This design document outlines the architecture and implementation strategy for deploying the Proactive Accountability Assistant to a production server. The deployment uses Docker Compose for container orchestration, Nginx as a reverse proxy with SSL termination, and includes comprehensive monitoring, logging, and backup strategies.

The deployment supports both single-server and cloud-based deployments, with configuration for popular platforms like DigitalOcean, AWS, or any VPS provider.

## Architecture

### Deployment Architecture Diagram

```
                                    Internet
                                       │
                                       ▼
                            ┌──────────────────┐
                            │   Nginx Proxy    │
                            │  (SSL/TLS Term)  │
                            │   Port 80/443    │
                            └──────────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │   Frontend   │   │   Backend    │   │  Discord Bot │
            │  (React/Nginx│   │  (FastAPI)   │   │  (Discord.py)│
            │   Port 3000) │   │  Port 8000)  │   │              │
            └──────────────┘   └──────────────┘   └──────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │  PostgreSQL  │   │    Redis     │   │Celery Worker │
            │  (Persistent │   │  (Persistent │   │  & Beat      │
            │   Volume)    │   │   Volume)    │   │              │
            └──────────────┘   └──────────────┘   └──────────────┘
                    │                  │
                    ▼                  ▼
            ┌──────────────────────────────────┐
            │      Persistent Volumes          │
            │  - postgres_data                 │
            │  - redis_data                    │
            │  - nginx_certs                   │
            │  - logs                          │
            └──────────────────────────────────┘
```

### Network Architecture

- **External Network**: Public internet access via ports 80 (HTTP) and 443 (HTTPS)
- **Internal Network**: Docker bridge network for inter-service communication
- **Service Discovery**: Services communicate using Docker DNS (service names)
- **SSL Termination**: Nginx handles HTTPS, forwards HTTP to backend services

## Components and Interfaces

### 1. Nginx Reverse Proxy

**Purpose**: SSL termination, request routing, static file serving, security headers

**Configuration**:
- Listens on ports 80 (redirect to HTTPS) and 443 (HTTPS)
- Routes `/api/*` to backend service
- Routes `/docs` and `/openapi.json` to backend
- Serves frontend static files for all other routes
- Implements rate limiting and security headers
- Handles WebSocket upgrades for real-time features

**Key Features**:
- Automatic HTTP to HTTPS redirect
- SSL certificate management with Let's Encrypt
- Gzip compression for text assets
- Client body size limits
- Custom error pages

### 2. Production Docker Compose

**Differences from Development**:
- No volume mounts for code (uses built images)
- Production environment variables
- Resource limits configured
- Restart policies set to `unless-stopped`
- Health checks enabled
- Logging drivers configured
- Networks explicitly defined

**Services**:
- `nginx`: Reverse proxy (ports 80, 443)
- `frontend`: Production-built React app
- `backend`: FastAPI with Gunicorn
- `celery-worker`: Background task processor
- `celery-beat`: Task scheduler
- `discord-bot`: Discord integration
- `postgres`: Database with persistent volume
- `redis`: Cache/queue with persistent volume

### 3. Environment Configuration

**Production Environment Variables**:

Backend:
```
ENVIRONMENT=production
DATABASE_URL=postgresql://user:pass@postgres:5432/db
REDIS_URL=redis://redis:6379/0
ANTHROPIC_API_KEY=<secret>
JWT_SECRET_KEY=<secret>
DISCORD_WEBHOOK_URL=<secret>
FRONTEND_URL=https://yourdomain.com
BACKEND_URL=https://yourdomain.com/api
CORS_ORIGINS=https://yourdomain.com
```

Frontend:
```
VITE_API_URL=https://yourdomain.com/api
NODE_ENV=production
```

Discord Bot:
```
DISCORD_TOKEN=<secret>
API_BASE_URL=http://backend:8000
DATABASE_URL=postgresql://user:pass@postgres:5432/db
```

### 4. SSL/TLS Configuration

**Certificate Management**:
- Use Certbot for Let's Encrypt certificates
- Automatic renewal via cron job or Certbot timer
- Certificate storage in persistent volume
- Support for multiple domains/subdomains

**SSL Configuration**:
- TLS 1.2 and 1.3 only
- Strong cipher suites
- HSTS headers enabled
- OCSP stapling
- Perfect forward secrecy

### 5. Database Management

**PostgreSQL Configuration**:
- Persistent volume for data directory
- Connection pooling via SQLAlchemy
- Automated backups via pg_dump
- Point-in-time recovery capability
- Performance tuning for production workload

**Migration Strategy**:
- Alembic migrations run on backend startup
- Migration lock to prevent concurrent runs
- Rollback capability for failed migrations
- Migration history tracking

### 6. Logging and Monitoring

**Logging Strategy**:
- JSON-formatted logs for structured logging
- Log levels: INFO for production, DEBUG for troubleshooting
- Log rotation with size and time limits
- Centralized log collection (optional)

**Log Locations**:
- Application logs: `/var/log/app/`
- Nginx access logs: `/var/log/nginx/access.log`
- Nginx error logs: `/var/log/nginx/error.log`
- Database logs: PostgreSQL container logs

**Monitoring**:
- Health check endpoints for all services
- Docker health checks with restart policies
- Resource usage monitoring (CPU, memory, disk)
- Application metrics via FastAPI middleware
- Optional: Prometheus + Grafana integration

### 7. Backup and Recovery

**Backup Strategy**:
- Daily automated PostgreSQL dumps
- Retention: 7 daily, 4 weekly, 3 monthly
- Backup storage: Local + remote (S3, Backblaze, etc.)
- Backup verification via test restores

**Backup Script**:
- Runs via cron job
- Creates compressed SQL dumps
- Uploads to remote storage
- Cleans up old backups
- Sends notifications on failure

**Recovery Procedures**:
- Database restore from dump file
- Container recreation from images
- Volume restoration from backups
- Configuration restoration from version control

## Data Models

### Deployment Configuration Files

**docker-compose.prod.yml**:
- Production service definitions
- Resource limits and reservations
- Health checks and restart policies
- Network and volume configurations
- Environment variable references

**nginx.conf**:
- Server blocks for HTTP and HTTPS
- Upstream backend definitions
- SSL configuration
- Security headers
- Rate limiting rules
- Caching policies

**.env.production**:
- All production environment variables
- Secrets (not committed to version control)
- Service URLs and ports
- Feature flags

**backup.sh**:
- Database backup script
- Compression and encryption
- Remote upload logic
- Cleanup and retention

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Service Dependency Ordering

*For any* deployment execution, when services are started, dependent services (backend, celery) should only start after their dependencies (postgres, redis) are healthy.

**Validates: Requirements 1.2**

### Property 2: Environment Variable Validation

*For any* service startup, if required environment variables are missing, the service should fail to start with a clear error message.

**Validates: Requirements 2.5**

### Property 3: SSL Redirect Consistency

*For any* HTTP request to the application, the response should be a redirect to the HTTPS equivalent URL.

**Validates: Requirements 3.1**

### Property 4: Data Persistence Across Restarts

*For any* data written to the database, if the database container is restarted, the data should still be accessible after restart.

**Validates: Requirements 4.1, 4.3**

### Property 5: Migration Idempotency

*For any* database state, running migrations multiple times should produce the same final schema as running them once.

**Validates: Requirements 5.1, 5.5**

### Property 6: Health Check Responsiveness

*For any* healthy service, the health check endpoint should return a success status within the configured timeout period.

**Validates: Requirements 7.1, 7.3**

### Property 7: Log Persistence

*For any* log message generated by a service, the message should be written to persistent storage and remain accessible after container restart.

**Validates: Requirements 8.1, 8.5**

### Property 8: Backup Completeness

*For any* database backup operation, the resulting backup file should contain all tables and data present in the database at backup time.

**Validates: Requirements 10.1, 10.5**

### Property 9: Resource Limit Enforcement

*For any* container with configured memory limits, the container should not be able to allocate memory beyond the specified limit.

**Validates: Requirements 12.1**

### Property 10: Reverse Proxy Routing

*For any* request to `/api/*`, the reverse proxy should forward the request to the backend service and return the backend's response.

**Validates: Requirements 6.1**

## Error Handling

### Deployment Errors

**Missing Environment Variables**:
- Detection: Service startup validation
- Response: Fail fast with clear error message
- Recovery: Update .env file and restart

**Port Conflicts**:
- Detection: Docker Compose startup failure
- Response: Error message indicating conflicting port
- Recovery: Stop conflicting service or change port mapping

**Certificate Errors**:
- Detection: Nginx startup failure or SSL handshake errors
- Response: Log certificate validation errors
- Recovery: Regenerate certificates or fix configuration

### Runtime Errors

**Service Crashes**:
- Detection: Docker health checks
- Response: Automatic restart via restart policy
- Escalation: Alert after 3 failed restarts

**Database Connection Failures**:
- Detection: Backend health check failure
- Response: Retry with exponential backoff
- Recovery: Restart database service if persistent

**Disk Space Exhaustion**:
- Detection: Monitoring alerts
- Response: Trigger log rotation and cleanup
- Prevention: Automated cleanup scripts

**Memory Exhaustion**:
- Detection: Container OOM kills
- Response: Restart with resource limits
- Investigation: Review memory usage patterns

### Backup Errors

**Backup Failure**:
- Detection: Backup script exit code
- Response: Send alert notification
- Recovery: Manual backup initiation

**Remote Upload Failure**:
- Detection: Upload command exit code
- Response: Retry with exponential backoff
- Fallback: Keep local backup, alert administrator

## Testing Strategy

### Pre-Deployment Testing

**Local Production Simulation**:
- Build production Docker images locally
- Run docker-compose.prod.yml locally
- Test with production-like environment variables
- Verify all services start and communicate
- Test SSL with self-signed certificates

**Configuration Validation**:
- Validate all environment variables are set
- Check Nginx configuration syntax
- Verify Docker Compose file syntax
- Test database connection strings
- Validate API keys and tokens

### Deployment Testing

**Smoke Tests**:
- Verify all containers are running
- Check health endpoints return 200
- Test frontend loads in browser
- Verify API responds to requests
- Confirm Discord bot connects

**Integration Tests**:
- Test user registration and login
- Create a project via API
- Verify database persistence
- Test Discord bot message sending
- Confirm Celery tasks execute

**Security Tests**:
- Verify HTTP redirects to HTTPS
- Check SSL certificate validity
- Test CORS configuration
- Verify rate limiting works
- Check security headers present

### Post-Deployment Monitoring

**Health Monitoring**:
- Continuous health check monitoring
- Resource usage tracking
- Error rate monitoring
- Response time tracking

**Functional Monitoring**:
- Synthetic user transactions
- API endpoint availability
- Database query performance
- Background task execution

### Property-Based Testing

We will use **pytest** with **Hypothesis** for property-based testing of deployment scripts and configurations.

**Test Configuration**:
- Minimum 100 iterations per property test
- Each test tagged with property reference
- Tests run in CI/CD pipeline before deployment

**Test Coverage**:
- Environment variable validation
- Configuration file parsing
- Backup and restore procedures
- Health check logic
- Resource limit calculations

## Deployment Options

### Option 1: Single VPS Deployment

**Best For**: Small to medium deployments, cost-conscious projects

**Providers**: DigitalOcean, Linode, Vultr, Hetzner

**Specifications**:
- Minimum: 2 CPU, 4GB RAM, 50GB SSD
- Recommended: 4 CPU, 8GB RAM, 100GB SSD

**Steps**:
1. Provision VPS with Ubuntu 22.04 LTS
2. Install Docker and Docker Compose
3. Configure firewall (UFW)
4. Clone repository
5. Configure environment variables
6. Run deployment script
7. Configure DNS
8. Obtain SSL certificates

### Option 2: Cloud Platform Deployment

**Best For**: Scalable deployments, managed services

**Providers**: AWS, Google Cloud, Azure

**Services Used**:
- Compute: EC2/Compute Engine/VM
- Database: RDS/Cloud SQL/Azure Database (optional)
- Storage: S3/Cloud Storage/Blob Storage
- Load Balancer: ALB/Cloud Load Balancing/Azure LB

**Benefits**:
- Managed database backups
- Auto-scaling capabilities
- Better monitoring and logging
- Higher availability options

### Option 3: Container Platform Deployment

**Best For**: Kubernetes-ready deployments, microservices

**Providers**: DigitalOcean Kubernetes, AWS EKS, Google GKE

**Approach**:
- Convert Docker Compose to Kubernetes manifests
- Use Helm charts for deployment
- Implement horizontal pod autoscaling
- Use managed database services

## Security Considerations

### Network Security

- Firewall rules: Only ports 80, 443, and 22 (SSH) open
- SSH key-based authentication only
- Fail2ban for brute force protection
- Regular security updates via unattended-upgrades

### Application Security

- Environment variables for all secrets
- No secrets in Docker images or version control
- JWT tokens with short expiration
- Rate limiting on API endpoints
- Input validation on all endpoints
- SQL injection prevention via ORM
- XSS prevention via React and CSP headers

### Data Security

- Encrypted database connections
- Encrypted backups
- Encrypted data at rest (optional)
- Regular security audits
- GDPR compliance for user data

## Performance Optimization

### Frontend Optimization

- Production build with minification
- Code splitting for faster initial load
- Asset compression (gzip/brotli)
- CDN for static assets (optional)
- Browser caching headers
- Image optimization

### Backend Optimization

- Gunicorn with multiple workers
- Connection pooling for database
- Redis caching for frequent queries
- Query optimization and indexing
- Async endpoints where beneficial
- Response compression

### Database Optimization

- Proper indexing on frequently queried columns
- Connection pooling
- Query result caching
- Regular VACUUM and ANALYZE
- Monitoring slow queries

## Maintenance Procedures

### Regular Maintenance

**Daily**:
- Automated backups
- Log rotation
- Health check monitoring

**Weekly**:
- Review error logs
- Check disk space usage
- Verify backup integrity
- Review security alerts

**Monthly**:
- Security updates
- Dependency updates
- Performance review
- Backup restoration test

### Update Procedures

**Application Updates**:
1. Pull latest code
2. Build new Docker images
3. Run database migrations
4. Perform rolling restart
5. Verify deployment
6. Monitor for errors

**Dependency Updates**:
1. Update requirements.txt / package.json
2. Test locally
3. Build new images
4. Deploy to staging
5. Deploy to production

**System Updates**:
1. Schedule maintenance window
2. Notify users
3. Create backup
4. Apply updates
5. Restart services
6. Verify functionality

## Rollback Procedures

### Application Rollback

1. Stop current containers
2. Restore previous Docker images
3. Rollback database migrations (if needed)
4. Start containers with previous version
5. Verify functionality
6. Investigate failure cause

### Database Rollback

1. Stop application services
2. Restore database from backup
3. Verify data integrity
4. Restart services
5. Test critical functionality

### Configuration Rollback

1. Restore previous configuration files from git
2. Restart affected services
3. Verify configuration applied correctly
4. Monitor for issues

## Cost Estimation

### Single VPS Deployment

**Monthly Costs**:
- VPS (4 CPU, 8GB RAM): $40-80
- Domain name: $1-2
- Backup storage (optional): $5-10
- Monitoring (optional): $0-20
- **Total**: $46-112/month

### Cloud Platform Deployment

**Monthly Costs** (AWS example):
- EC2 t3.large: $60
- RDS PostgreSQL: $50
- S3 storage: $5
- Load Balancer: $20
- Data transfer: $10
- **Total**: $145-200/month

## Documentation Requirements

### Deployment Documentation

- Step-by-step deployment guide
- Environment variable reference
- Troubleshooting guide
- Architecture diagrams
- Security best practices

### Operations Documentation

- Backup and restore procedures
- Update and rollback procedures
- Monitoring and alerting setup
- Incident response procedures
- Maintenance schedules

### Developer Documentation

- Local development setup
- CI/CD pipeline configuration
- Deployment automation scripts
- Testing procedures
- Contributing guidelines
