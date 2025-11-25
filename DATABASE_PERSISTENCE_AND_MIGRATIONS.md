# Database Persistence and Migrations

This document describes the database persistence and migration strategy for the Proactive Accountability Assistant in production environments.

## Overview

The application uses PostgreSQL for data persistence and Alembic for database migrations. The production deployment includes:

1. **Persistent volumes** for database data
2. **Automatic migration execution** on container startup
3. **Migration locking** to prevent concurrent migrations
4. **Database initialization scripts** with comprehensive error handling

## Persistent Volumes

### PostgreSQL Data Volume

The PostgreSQL database uses a named Docker volume to persist data across container restarts and updates.

**Configuration in docker-compose.prod.yml:**
```yaml
volumes:
  postgres_data:
    name: accountability-postgres-data

services:
  postgres:
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

**Benefits:**
- Data survives container restarts
- Data survives container recreation
- Data survives host reboots
- Easy to backup and restore

**Volume Location:**
- Docker manages the volume location (typically `/var/lib/docker/volumes/`)
- Access via: `docker volume inspect accountability-postgres-data`

### Redis Data Volume

Redis also uses a persistent volume with AOF (Append Only File) enabled for durability.

**Configuration:**
```yaml
volumes:
  redis_data:
    name: accountability-redis-data

services:
  redis:
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --appendfsync everysec
```

## Migration Strategy

### Automatic Migration Execution

Migrations run automatically when the backend container starts, before the application server starts.

**Dockerfile CMD:**
```dockerfile
CMD python scripts/init_db.py && \
    gunicorn app.main:app ...
```

**Flow:**
1. Container starts
2. `init_db.py` runs and executes migrations
3. If migrations succeed, Gunicorn starts
4. If migrations fail, container exits (Docker will restart based on policy)

### Migration Locking Mechanism

To prevent concurrent migrations when multiple containers start simultaneously, we use PostgreSQL advisory locks.

**How it works:**

1. **Lock Acquisition:**
   - Script attempts to acquire advisory lock with ID `123456789`
   - Uses `pg_try_advisory_lock()` for non-blocking check
   - Retries every 2 seconds for up to 5 minutes

2. **Migration Execution:**
   - Only the container holding the lock runs migrations
   - Other containers wait for the lock to be released

3. **Lock Release:**
   - Lock is automatically released when script exits
   - Even if script crashes, lock is released when connection closes

**Benefits:**
- **Database-level coordination** - Works across multiple hosts
- **No external dependencies** - Uses PostgreSQL built-in feature
- **Automatic cleanup** - Locks don't persist if process dies
- **Prevents race conditions** - Only one migration runs at a time

### Migration Scripts

#### init_db.py (Production)

The main initialization script with full error handling and locking.

**Features:**
- Waits for database availability (up to 60 seconds)
- Acquires migration lock (up to 5 minutes timeout)
- Checks if database is initialized
- Runs pending migrations
- Verifies schema after migration
- Comprehensive logging

**Usage:**
```bash
python scripts/init_db.py
```

**Exit Codes:**
- `0` - Success
- `1` - Failure

#### run_migrations.py (Development/Manual)

A simpler script for manual migration management without locking.

**Usage:**
```bash
# Run migrations
python scripts/run_migrations.py upgrade

# Check current version
python scripts/run_migrations.py current

# View history
python scripts/run_migrations.py history

# Downgrade
python scripts/run_migrations.py downgrade
```

**Warning:** Only use in development or when certain no other processes are running migrations.

## Database Initialization Flow

### First-Time Initialization

When deploying to a fresh database:

```
1. Backend container starts
   ↓
2. init_db.py runs
   ↓
3. Waits for PostgreSQL to be ready
   ↓
4. Acquires migration lock
   ↓
5. Detects database is not initialized
   ↓
6. Runs all migrations from scratch
   ↓
7. Creates all tables and indexes
   ↓
8. Verifies schema
   ↓
9. Releases lock
   ↓
10. Starts Gunicorn
```

### Subsequent Deployments

When deploying updates with new migrations:

```
1. Backend container starts
   ↓
2. init_db.py runs
   ↓
3. Waits for PostgreSQL to be ready
   ↓
4. Acquires migration lock
   ↓
5. Detects database is already initialized
   ↓
6. Checks for pending migrations
   ↓
7. Runs only new migrations
   ↓
8. Verifies schema
   ↓
9. Releases lock
   ↓
10. Starts Gunicorn
```

### Multiple Container Startup

When multiple backend containers start simultaneously:

```
Container 1:                    Container 2:                    Container 3:
    ↓                              ↓                              ↓
Waits for DB                   Waits for DB                   Waits for DB
    ↓                              ↓                              ↓
Acquires lock ✓                Tries lock (blocked)           Tries lock (blocked)
    ↓                              ↓                              ↓
Runs migrations                Waits for lock...              Waits for lock...
    ↓                              ↓                              ↓
Releases lock                  Acquires lock ✓                Waits for lock...
    ↓                              ↓                              ↓
Starts server                  Sees migrations done           Acquires lock ✓
                                   ↓                              ↓
                               Releases lock                  Sees migrations done
                                   ↓                              ↓
                               Starts server                  Releases lock
                                                                  ↓
                                                              Starts server
```

## Health Checks

### Database Health Check

PostgreSQL container includes a health check:

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 40s
```

### Backend Health Check

Backend container health check includes database connectivity:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

The `/health` endpoint checks database connectivity:

```python
@app.get("/health")
async def health_check():
    db_healthy = check_database_health()
    if db_healthy:
        return {"status": "healthy", "database": "connected"}
    else:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "disconnected"}
        )
```

## Backup and Restore

### Manual Backup

**Create a backup:**
```bash
# Using docker exec
docker exec accountability-db-prod pg_dump -U accountability -d accountability_db > backup.sql

# Or using docker-compose
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U accountability -d accountability_db > backup.sql
```

**Compressed backup:**
```bash
docker exec accountability-db-prod pg_dump -U accountability -d accountability_db | gzip > backup.sql.gz
```

### Manual Restore

**Restore from backup:**
```bash
# Stop backend services first
docker-compose -f docker-compose.prod.yml stop backend celery-worker celery-beat discord-bot

# Restore database
cat backup.sql | docker exec -i accountability-db-prod psql -U accountability -d accountability_db

# Or from compressed backup
gunzip -c backup.sql.gz | docker exec -i accountability-db-prod psql -U accountability -d accountability_db

# Restart services
docker-compose -f docker-compose.prod.yml start backend celery-worker celery-beat discord-bot
```

### Volume Backup

**Backup the entire volume:**
```bash
# Create a backup of the volume
docker run --rm \
  -v accountability-postgres-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/postgres-data-backup.tar.gz -C /data .
```

**Restore volume:**
```bash
# Stop database first
docker-compose -f docker-compose.prod.yml stop postgres

# Restore volume
docker run --rm \
  -v accountability-postgres-data:/data \
  -v $(pwd):/backup \
  alpine sh -c "cd /data && tar xzf /backup/postgres-data-backup.tar.gz"

# Start database
docker-compose -f docker-compose.prod.yml start postgres
```

## Troubleshooting

### Migration Failures

**Symptom:** Container keeps restarting, logs show migration errors

**Diagnosis:**
```bash
# Check container logs
docker logs accountability-backend-prod

# Check migration status
docker exec accountability-backend-prod python scripts/run_migrations.py current
```

**Solutions:**

1. **Check for data conflicts:**
   ```bash
   # Connect to database
   docker exec -it accountability-db-prod psql -U accountability -d accountability_db
   
   # Check for constraint violations
   SELECT * FROM alembic_version;
   ```

2. **Manual migration:**
   ```bash
   # Run migrations manually
   docker exec accountability-backend-prod python scripts/run_migrations.py upgrade
   ```

3. **Rollback and retry:**
   ```bash
   # Downgrade one version
   docker exec accountability-backend-prod python scripts/run_migrations.py downgrade
   
   # Try upgrade again
   docker exec accountability-backend-prod python scripts/run_migrations.py upgrade
   ```

### Lock Timeout

**Symptom:** "Failed to acquire migration lock within timeout"

**Cause:** Another container is running migrations or a previous migration is stuck

**Solutions:**

1. **Check for running migrations:**
   ```bash
   # Check container logs
   docker logs accountability-backend-prod
   ```

2. **Check PostgreSQL locks:**
   ```sql
   -- Connect to database
   docker exec -it accountability-db-prod psql -U accountability -d accountability_db
   
   -- Check advisory locks
   SELECT * FROM pg_locks WHERE locktype = 'advisory';
   ```

3. **Manually release lock (if stuck):**
   ```sql
   SELECT pg_advisory_unlock(123456789);
   ```

### Data Loss Prevention

**Before major changes:**

1. **Create a backup:**
   ```bash
   docker exec accountability-db-prod pg_dump -U accountability -d accountability_db | gzip > backup-$(date +%Y%m%d-%H%M%S).sql.gz
   ```

2. **Test in staging first:**
   ```bash
   # Deploy to staging environment
   # Verify migrations work
   # Then deploy to production
   ```

3. **Have a rollback plan:**
   - Keep previous Docker images
   - Keep database backups
   - Document rollback procedure

## Best Practices

### Development

1. **Test migrations locally:**
   ```bash
   python scripts/run_migrations.py upgrade
   ```

2. **Create reversible migrations:**
   - Always implement `downgrade()` function
   - Test both upgrade and downgrade

3. **Use descriptive migration names:**
   ```bash
   alembic revision -m "add_user_preferences_table"
   ```

### Production

1. **Always backup before deploying:**
   - Automated backups before deployment
   - Keep multiple backup versions

2. **Monitor migration logs:**
   - Check container logs during deployment
   - Set up alerts for migration failures

3. **Use rolling deployments:**
   - Deploy to one container at a time
   - Verify health before deploying to next

4. **Never skip migrations:**
   - Always run migrations in order
   - Never manually modify production database

5. **Test in staging:**
   - Replicate production environment
   - Test migrations with production-like data

## Environment Variables

Required environment variables for database operations:

```bash
# Database connection
DATABASE_URL=postgresql://user:password@postgres:5432/dbname
POSTGRES_USER=accountability
POSTGRES_PASSWORD=<secure-password>
POSTGRES_DB=accountability_db

# Database pool settings (optional)
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_RECYCLE=3600
DB_POOL_PRE_PING=true
DB_CONNECT_TIMEOUT=10

# Application
ENVIRONMENT=production
```

## Monitoring

### Key Metrics to Monitor

1. **Migration duration:**
   - Track how long migrations take
   - Alert on unusually long migrations

2. **Database size:**
   - Monitor disk usage
   - Set up alerts for low disk space

3. **Connection pool:**
   - Monitor active connections
   - Alert on connection exhaustion

4. **Query performance:**
   - Track slow queries
   - Monitor query execution time

### Logging

Migration logs include:

- Database availability checks
- Lock acquisition attempts
- Migration execution status
- Schema verification results
- Error details with stack traces

**View logs:**
```bash
# Container logs
docker logs accountability-backend-prod

# Follow logs in real-time
docker logs -f accountability-backend-prod

# Last 100 lines
docker logs --tail 100 accountability-backend-prod
```

## Additional Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL Advisory Locks](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)
- [Docker Volumes](https://docs.docker.com/storage/volumes/)
- [PostgreSQL Backup and Restore](https://www.postgresql.org/docs/current/backup.html)
