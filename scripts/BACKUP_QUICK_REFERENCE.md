# Backup System Quick Reference

## Common Commands

### Setup
```bash
# Initial setup with automated backups
./scripts/setup-backup-cron.sh

# Custom backup time (3:30 AM)
BACKUP_HOUR=3 BACKUP_MINUTE=30 ./scripts/setup-backup-cron.sh
```

### Backup Operations
```bash
# Manual backup
./scripts/backup-database.sh

# Check backup status
ls -lh backups/daily/
ls -lh backups/weekly/
ls -lh backups/monthly/

# View backup logs
tail -f backups/backup.log
```

### Restore Operations
```bash
# List available backups
find backups -name "*.sql.gz*" -printf '%T+ %p\n' | sort

# Restore from backup
./scripts/restore-database.sh backups/daily/backup_file.sql.gz

# Restore from encrypted backup
./scripts/restore-database.sh backups/weekly/backup_file.sql.gz.enc
```

### Maintenance
```bash
# Run cleanup manually
./scripts/cleanup-backups.sh

# Test backup system
./scripts/test-backup-system.sh

# Check cron job
crontab -l | grep backup
```

## Environment Variables

```bash
# Required
POSTGRES_DB=accountability_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Optional
DB_CONTAINER=postgres
BACKUP_DIR=/path/to/backups
ENCRYPT_BACKUPS=true
BACKUP_ENCRYPTION_KEY=your_key
REMOTE_BACKUP=true
REMOTE_BACKUP_PATH=/path/to/remote
NOTIFY_ON_FAILURE=true
NOTIFICATION_EMAIL=admin@example.com
```

## Retention Policy

| Type    | Retention | Frequency           |
|---------|-----------|---------------------|
| Daily   | 7 days    | Every day           |
| Weekly  | 4 weeks   | Every Sunday        |
| Monthly | 3 months  | 1st of each month   |

## Troubleshooting

### Backup fails
```bash
# Check Docker is running
docker ps

# Check database container
docker ps | grep postgres

# Check logs
tail -n 50 backups/backup.log
```

### Restore fails
```bash
# Verify backup file exists
ls -lh backups/daily/backup_file.sql.gz

# Check database is running
docker exec postgres psql -U postgres -d accountability_db -c "SELECT 1;"

# Set encryption key if needed
export BACKUP_ENCRYPTION_KEY=your_key
```

### Cron not running
```bash
# Check cron service
sudo systemctl status cron

# View cron logs
grep CRON /var/log/syslog | tail -n 20
```

## Emergency Procedures

### Quick Restore
```bash
# 1. Stop services
docker-compose down backend celery-worker celery-beat discord-bot

# 2. Restore database
./scripts/restore-database.sh backups/daily/latest_backup.sql.gz

# 3. Restart services
docker-compose up -d

# 4. Verify
curl http://localhost:8000/health
```

### Backup Before Major Changes
```bash
# Create immediate backup
./scripts/backup-database.sh

# Verify backup created
ls -lh backups/daily/ | tail -1
```

## File Locations

- Backup scripts: `scripts/backup-*.sh`, `scripts/cleanup-backups.sh`, `scripts/restore-database.sh`
- Backup directory: `backups/` (or `$BACKUP_DIR`)
- Logs: `backups/backup.log`, `backups/restore.log`
- Documentation: `scripts/BACKUP_SYSTEM.md`

## Support

For detailed documentation, see [BACKUP_SYSTEM.md](BACKUP_SYSTEM.md)
