# Scripts Directory

This directory contains utility scripts for deployment, configuration validation, and maintenance.

## Available Scripts

### Database Backup System

Comprehensive backup automation system for PostgreSQL database. See [BACKUP_SYSTEM.md](BACKUP_SYSTEM.md) for detailed documentation.

**Quick Start**:
```bash
# Set up automated backups
./scripts/setup-backup-cron.sh

# Run manual backup
./scripts/backup-database.sh

# Restore from backup
./scripts/restore-database.sh backups/daily/backup_file.sql.gz

# Test backup system
./scripts/test-backup-system.sh
```

**Features**:
- Automated daily backups via cron
- Retention policy: 7 daily, 4 weekly, 3 monthly
- Compression and optional encryption
- Remote backup support
- Easy restoration procedures

---

### validate-env.sh

Bash script for validating environment variable configuration.

**Usage**:
```bash
./scripts/validate-env.sh [env-file]
```

**Examples**:
```bash
# Validate production environment
./scripts/validate-env.sh .env.production

# Validate staging environment
./scripts/validate-env.sh .env.staging

# Validate default (.env.production)
./scripts/validate-env.sh
```

**Features**:
- Checks all required variables are set
- Validates security requirements (minimum lengths, no defaults)
- Verifies URL formats (HTTPS in production)
- Checks pattern matching (database URLs, API keys)
- Color-coded output (errors in red, warnings in yellow, success in green)

**Exit Codes**:
- `0`: Validation passed (with or without warnings)
- `1`: Validation failed (errors found)

---

### validate-env.py

Python script for validating environment variable configuration (cross-platform alternative to bash version).

**Usage**:
```bash
python scripts/validate-env.py [env-file]
```

**Examples**:
```bash
# Validate production environment
python scripts/validate-env.py .env.production

# Validate staging environment
python scripts/validate-env.py .env.staging

# Validate default (.env.production)
python scripts/validate-env.py
```

**Features**:
- Same validation logic as bash version
- Better cross-platform compatibility
- More detailed error messages
- Easier to extend and maintain

**Requirements**:
- Python 3.6+
- No external dependencies (uses only standard library)

**Exit Codes**:
- `0`: Validation passed (with or without warnings)
- `1`: Validation failed (errors found)

---

## Pre-Deployment Checklist

Before deploying to production, run through this checklist:

1. **Create production environment file**:
   ```bash
   cp .env.production.example .env.production
   ```

2. **Fill in all required values** (see [ENVIRONMENT_VARIABLES.md](../docs/ENVIRONMENT_VARIABLES.md))

3. **Validate configuration**:
   ```bash
   ./scripts/validate-env.sh .env.production
   ```

4. **Fix any errors** reported by validation

5. **Secure the file**:
   ```bash
   chmod 600 .env.production
   ```

6. **Verify file is not tracked by Git**:
   ```bash
   git status .env.production
   # Should show: "Untracked files" or not appear at all
   ```

7. **Review security checklist** in [SECRET_MANAGEMENT.md](../docs/SECRET_MANAGEMENT.md)

---

## Adding New Scripts

When adding new scripts to this directory:

1. **Make scripts executable**:
   ```bash
   chmod +x scripts/your-script.sh
   ```

2. **Add shebang line** at the top:
   ```bash
   #!/bin/bash
   # or
   #!/usr/bin/env python3
   ```

3. **Document the script** in this README

4. **Include usage examples** and exit codes

5. **Add error handling** and validation

6. **Test on multiple platforms** if possible

---

## Troubleshooting

### Permission Denied

If you get "Permission denied" when running a script:

```bash
chmod +x scripts/script-name.sh
```

### Script Not Found

Ensure you're running from the project root:

```bash
cd /path/to/accountability-assistant
./scripts/validate-env.sh
```

### Python Not Found

If `python` command is not found, try:

```bash
python3 scripts/validate-env.py
```

---

## Related Documentation

- [Environment Variables Reference](../docs/ENVIRONMENT_VARIABLES.md)
- [Secret Management Guidelines](../docs/SECRET_MANAGEMENT.md)
- [Production Deployment Guide](../PRODUCTION_DEPLOYMENT.md)
