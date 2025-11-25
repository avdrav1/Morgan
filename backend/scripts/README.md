# Database Scripts

This directory contains scripts for database initialization, migration management, and maintenance.

## Scripts Overview

### `init_db.py` - Production Database Initialization

The main database initialization script used in production. It provides:

- **Database availability checking** - Waits for PostgreSQL to be ready
- **Migration locking** - Uses PostgreSQL advisory locks to prevent concurrent migrations
- **Automatic migration execution** - Runs pending Alembic migrations
- **Schema verification** - Validates that essential tables exist

**Usage:**
```bash
python scripts/init_db.py
```

This script is automatically run when the backend container starts in production (see `Dockerfile`).

**Features:**
- Retries database connection up to 30 times with 2-second intervals
- Acquires a distributed lock with 5-minute timeout
- Prevents multiple containers from running migrations simultaneously
- Verifies schema after migration
- Comprehensive logging

**Exit Codes:**
- `0` - Success
- `1` - Failure (database unavailable, lock timeout, migration error, or schema verification failure)

### `init_db.sh` - Shell-based Initialization (Alternative)

A bash-based alternative to `init_db.py` with similar functionality. Useful for environments where Python dependencies are not yet available.

**Usage:**
```bash
bash scripts/init_db.sh
```

**Requirements:**
- `pg_isready` - PostgreSQL client tools
- `psql` - PostgreSQL command-line client
- `alembic` - Python migration tool

### `run_migrations.py` - Manual Migration Runner

A standalone script for manually running migrations or checking migration status. Does not use locking, so use with caution.

**Usage:**
```bash
# Run pending migrations
python scripts/run_migrations.py upgrade

# Show current migration version
python scripts/run_migrations.py current

# Show migration history
python scripts/run_migrations.py history

# Downgrade one version
python scripts/run_migrations.py downgrade

# Show available heads
python scripts/run_migrations.py heads
```

**When to use:**
- Local development
- Manual migration management
- Troubleshooting migration issues
- When you're certain no other processes are running migrations

**Warning:** This script does not use locking. Never use it in production when multiple containers might be starting simultaneously.

## Migration Locking Mechanism

The initialization scripts use PostgreSQL advisory locks to prevent concurrent migrations. This is critical in production environments where multiple containers might start simultaneously.

### How it works:

1. **Lock Acquisition**: The script attempts to acquire a PostgreSQL advisory lock with ID `123456789`
2. **Timeout**: If the lock cannot be acquired within 5 minutes, the script fails
3. **Migration Execution**: Once locked, migrations run safely
4. **Lock Release**: The lock is automatically released when the script exits (even on error)

### Advisory Lock Benefits:

- **Database-level coordination** - Works across multiple containers/hosts
- **Automatic cleanup** - Locks are released when the connection closes
- **Non-blocking check** - Uses `pg_try_advisory_lock()` to avoid hanging
- **No external dependencies** - Uses PostgreSQL's built-in functionality

## Production Deployment Flow

When a backend container starts in production:

```
1. Container starts
   ↓
2. init_db.py runs
   ↓
3. Wait for database (up to 60 seconds)
   ↓
4. Acquire migration lock (up to 5 minutes)
   ↓
5. Check if database is initialized
   ↓
6. Run pending migrations
   ↓
7. Verify schema
   ↓
8. Release lock
   ↓
9. Start Gunicorn server
```

If any step fails, the container exits with code 1 and Docker will restart it (based on restart policy).

## Troubleshooting

### Database not ready

**Symptom:** Script fails with "Database failed to become ready"

**Solutions:**
- Check that PostgreSQL container is running
- Verify database credentials in environment variables
- Check network connectivity between containers
- Increase `MAX_RETRIES` if database takes longer to start

### Lock timeout

**Symptom:** Script fails with "Failed to acquire migration lock within timeout"

**Cause:** Another container is running migrations and hasn't released the lock

**Solutions:**
- Wait for the other migration to complete
- Check if a migration process is stuck (check PostgreSQL locks)
- Manually release the lock if needed:
  ```sql
  SELECT pg_advisory_unlock(123456789);
  ```

### Migration failure

**Symptom:** Script fails with "Migration failed"

**Solutions:**
- Check migration logs for specific error
- Verify database schema is in expected state
- Check for data conflicts or constraint violations
- Consider rolling back to previous version
- Review migration files for errors

### Schema verification failure

**Symptom:** Script fails with "Required table 'X' not found"

**Cause:** Migration completed but expected tables are missing

**Solutions:**
- Check that all migrations ran successfully
- Verify migration files are present
- Check for partial migration execution
- Review database logs for errors

## Environment Variables

The scripts use the following environment variables:

- `DATABASE_URL` - PostgreSQL connection string (required)
- `ENVIRONMENT` - Application environment (development/production)
- `POSTGRES_USER` - Database user (for pg_isready check)
- `DB_HOST` - Database host (default: postgres)
- `DB_PORT` - Database port (default: 5432)

## Best Practices

1. **Always use init_db.py in production** - It has proper locking and error handling
2. **Never run migrations manually in production** - Use the automated initialization
3. **Test migrations locally first** - Use `run_migrations.py` in development
4. **Monitor migration logs** - Check container logs for migration status
5. **Have a rollback plan** - Know how to downgrade if needed
6. **Backup before major migrations** - Especially for schema changes

## Development Workflow

For local development, you can use either approach:

**Option 1: Automatic (like production)**
```bash
# Let Docker handle it
docker-compose up backend
```

**Option 2: Manual**
```bash
# Run migrations manually
python scripts/run_migrations.py upgrade

# Start the server
uvicorn app.main:app --reload
```

## Testing Migrations

Before deploying to production:

1. **Test locally:**
   ```bash
   python scripts/run_migrations.py upgrade
   ```

2. **Test in staging:**
   ```bash
   docker-compose -f docker-compose.prod.yml up backend
   ```

3. **Verify schema:**
   ```bash
   python scripts/run_migrations.py current
   ```

4. **Test rollback:**
   ```bash
   python scripts/run_migrations.py downgrade
   python scripts/run_migrations.py upgrade
   ```

## Additional Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL Advisory Locks](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)
- [Docker Health Checks](https://docs.docker.com/engine/reference/builder/#healthcheck)
