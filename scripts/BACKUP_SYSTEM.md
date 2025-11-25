# Database Backup System

This directory contains scripts for automated database backup, restoration, and maintenance for the Proactive Accountability Assistant application.

## Overview

The backup system provides:
- **Automated daily backups** via cron
- **Retention policies**: 7 daily, 4 weekly, 3 monthly backups
- **Compression** to save storage space
- **Optional encryption** for sensitive data
- **Remote backup support** (S3, rsync, rclone)
- **Easy restoration** from any backup
- **Automatic cleanup** of old backups

## Requirements

**Validates: Requirements 10.1, 10.2, 10.3**

## Scripts

### 1. backup-database.sh

Creates compressed database backups with automatic type detection (daily/weekly/monthly).

**Features:**
- Automatic backup type selection based on date
- Compression with gzip
- Optional encryption with OpenSSL
- Remote backup upload support
- Email notifications on failure
- Detailed logging

**Usage:**
```bash
./scripts/backup-database.sh
```

**Environment Variables:**
```bash
# Required
POSTGRES_DB=accountability_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Optional
DB_CONTAINER=postgres                    # Docker container name
BACKUP_DIR=/path/to/backups             # Backup directory
ENCRYPT_BACKUPS=true                    # Enable encryption
BACKUP_ENCRYPTION_KEY=your_key          # Encryption key
REMOTE_BACKUP=true                      # Enable remote backup
REMOTE_BACKUP_PATH=/path/to/remote      # Remote backup path
NOTIFY_ON_FAILURE=true                  # Enable email notifications
NOTIFICATION_EMAIL=admin@example.com    # Notification email
```

### 2. cleanup-backups.sh

Enforces retention policies by removing old backups.

**Retention Policy:**
- Daily backups: Keep last 7
- Weekly backups: Keep last 4
- Monthly backups: Keep last 3

**Usage:**
```bash
./scripts/cleanup-backups.sh
```

This script is automatically called after each backup.

### 3. restore-database.sh

Restores database from a backup file.

**Features:**
- Supports compressed backups (.sql.gz)
- Supports encrypted backups (.sql.gz.enc)
- Interactive confirmation
- Automatic decompression/decryption
- Verification after restore

**Usage:**
```bash
./scripts/restore-database.sh <backup_file>
```

**Examples:**
```bash
# Restore from daily backup
./scripts/restore-database.sh backups/daily/accountability_db_daily_20240101_120000.sql.gz

# Restore from encrypted backup
./scripts/restore-database.sh backups/weekly/accountability_db_weekly_20240101_120000.sql.gz.enc
```

### 4. setup-backup-cron.sh

Configures automated daily backups via cron.

**Features:**
- Installs cron job for daily backups
- Configurable backup time
- Removes old cron jobs
- Runs test backup
- Verifies installation

**Usage:**
```bash
./scripts/setup-backup-cron.sh
```

**Custom backup time:**
```bash
BACKUP_HOUR=3 BACKUP_MINUTE=30 ./scripts/setup-backup-cron.sh
```

## Setup Instructions

### 1. Initial Setup

```bash
# Make scripts executable
chmod +x scripts/backup-database.sh
chmod +x scripts/cleanup-backups.sh
chmod +x scripts/restore-database.sh
chmod +x scripts/setup-backup-cron.sh

# Create backup directory
mkdir -p backups/{daily,weekly,monthly}
```

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# Database configuration
POSTGRES_DB=accountability_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password

# Backup configuration (optional)
BACKUP_DIR=/path/to/backups
ENCRYPT_BACKUPS=true
BACKUP_ENCRYPTION_KEY=your_encryption_key
REMOTE_BACKUP=true
REMOTE_BACKUP_PATH=/mnt/remote-storage
```

### 3. Set Up Automated Backups

```bash
./scripts/setup-backup-cron.sh
```

This will:
- Configure daily backups at 2:00 AM
- Run a test backup
- Verify the cron job installation

### 4. Verify Backup System

```bash
# Run manual backup
./scripts/backup-database.sh

# Check backup files
ls -lh backups/daily/

# Check logs
tail -f backups/backup.log
```

## Backup Types

The system automatically determines backup type based on the date:

- **Daily**: Every day except Sunday and 1st of month
- **Weekly**: Every Sunday
- **Monthly**: 1st day of each month

## Retention Policy

| Type    | Retention | Example                                    |
|---------|-----------|-------------------------------------------|
| Daily   | 7 days    | Mon-Sat backups from current week         |
| Weekly  | 4 weeks   | Last 4 Sunday backups                     |
| Monthly | 3 months  | Last 3 backups from 1st of month          |

## Encryption

### Enable Encryption

Set environment variables:
```bash
ENCRYPT_BACKUPS=true
BACKUP_ENCRYPTION_KEY=your_secure_encryption_key
```

### Decrypt Manually

```bash
openssl enc -aes-256-cbc -d -in backup.sql.gz.enc -out backup.sql.gz -k your_key
```

## Remote Backup

### Supported Methods

1. **Local Mount** (NFS, SMB)
   ```bash
   REMOTE_BACKUP=true
   REMOTE_BACKUP_PATH=/mnt/nas/backups
   ```

2. **AWS S3** (requires AWS CLI)
   ```bash
   # Modify upload_to_remote() in backup-database.sh:
   aws s3 cp "$backup_file" "s3://your-bucket/backups/$backup_type/"
   ```

3. **rsync** (SSH)
   ```bash
   # Modify upload_to_remote() in backup-database.sh:
   rsync -avz "$backup_file" "user@remote:/backups/$backup_type/"
   ```

4. **rclone** (Multiple cloud providers)
   ```bash
   # Modify upload_to_remote() in backup-database.sh:
   rclone copy "$backup_file" "remote:backups/$backup_type/"
   ```

## Restoration Procedures

### 1. List Available Backups

```bash
# List all backups
find backups -type f -name "*.sql.gz*" -printf '%T+ %p\n' | sort

# List daily backups
ls -lh backups/daily/

# List weekly backups
ls -lh backups/weekly/

# List monthly backups
ls -lh backups/monthly/
```

### 2. Restore from Backup

```bash
# Stop application services
docker-compose down backend celery-worker celery-beat discord-bot

# Restore database
./scripts/restore-database.sh backups/daily/accountability_db_daily_20240101_120000.sql.gz

# Restart services
docker-compose up -d
```

### 3. Verify Restoration

```bash
# Check database
docker exec postgres psql -U postgres -d accountability_db -c "\dt"

# Check application
curl http://localhost:8000/health
```

## Monitoring

### Check Backup Status

```bash
# View recent logs
tail -n 50 backups/backup.log

# Check backup sizes
du -sh backups/*

# Count backups
echo "Daily: $(ls backups/daily/*.sql.gz* 2>/dev/null | wc -l)"
echo "Weekly: $(ls backups/weekly/*.sql.gz* 2>/dev/null | wc -l)"
echo "Monthly: $(ls backups/monthly/*.sql.gz* 2>/dev/null | wc -l)"
```

### Verify Cron Job

```bash
# List cron jobs
crontab -l

# Check cron logs (Ubuntu/Debian)
grep CRON /var/log/syslog | tail -n 20

# Check cron logs (CentOS/RHEL)
grep CRON /var/log/cron | tail -n 20
```

## Troubleshooting

### Backup Fails

**Issue**: Backup script fails with "Database container not found"

**Solution**:
```bash
# Check container name
docker ps --format '{{.Names}}' | grep postgres

# Set correct container name
export DB_CONTAINER=your_postgres_container_name
```

**Issue**: Permission denied

**Solution**:
```bash
# Make scripts executable
chmod +x scripts/*.sh

# Check backup directory permissions
mkdir -p backups
chmod 755 backups
```

### Restore Fails

**Issue**: Decryption fails

**Solution**:
```bash
# Verify encryption key
echo $BACKUP_ENCRYPTION_KEY

# Set encryption key
export BACKUP_ENCRYPTION_KEY=your_key
```

**Issue**: Database connection fails

**Solution**:
```bash
# Check database is running
docker ps | grep postgres

# Check database credentials
docker exec postgres psql -U postgres -d accountability_db -c "SELECT 1;"
```

### Cron Job Not Running

**Issue**: Backups not running automatically

**Solution**:
```bash
# Check cron service
sudo systemctl status cron

# Start cron service
sudo systemctl start cron

# Verify cron job
crontab -l | grep backup

# Check cron logs
tail -f /var/log/syslog | grep CRON
```

## Best Practices

1. **Test Restores Regularly**
   - Perform test restores monthly
   - Verify data integrity after restore

2. **Monitor Disk Space**
   - Check backup directory size regularly
   - Adjust retention policy if needed

3. **Secure Encryption Keys**
   - Store encryption keys securely
   - Use environment variables, not hardcoded values
   - Consider using a secrets manager

4. **Remote Backups**
   - Always maintain off-site backups
   - Test remote backup restoration
   - Verify remote backup integrity

5. **Documentation**
   - Document restoration procedures
   - Keep contact information for emergencies
   - Maintain runbook for disaster recovery

## Maintenance

### Weekly Tasks

- Review backup logs for errors
- Verify backup files are being created
- Check disk space usage

### Monthly Tasks

- Perform test restoration
- Review retention policy
- Update documentation if needed

### Quarterly Tasks

- Test disaster recovery procedures
- Review and update encryption keys
- Audit backup security

## Security Considerations

1. **Encryption**: Always encrypt backups containing sensitive data
2. **Access Control**: Restrict access to backup files and scripts
3. **Key Management**: Store encryption keys securely
4. **Audit Logs**: Monitor backup access and modifications
5. **Network Security**: Use secure protocols for remote backups

## Support

For issues or questions:
1. Check logs: `backups/backup.log`
2. Review this documentation
3. Check application logs: `docker-compose logs postgres`
4. Contact system administrator

## References

- PostgreSQL Backup Documentation: https://www.postgresql.org/docs/current/backup.html
- Docker PostgreSQL: https://hub.docker.com/_/postgres
- OpenSSL Encryption: https://www.openssl.org/docs/
