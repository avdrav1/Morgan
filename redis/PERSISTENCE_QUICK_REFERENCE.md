# Redis Persistence Quick Reference

## Quick Commands

### Check Persistence Status

```bash
# Run verification script
./scripts/verify-redis-persistence.sh

# Or manually check
docker exec accountability-redis-prod redis-cli INFO persistence
```

### Manual Backup

```bash
# Trigger immediate snapshot
docker exec accountability-redis-prod redis-cli BGSAVE

# Check last save time
docker exec accountability-redis-prod redis-cli LASTSAVE

# Copy backup files
docker cp accountability-redis-prod:/data/dump.rdb ./backup/
docker cp accountability-redis-prod:/data/appendonly.aof ./backup/
```

### Restore from Backup

```bash
# Stop Redis
docker-compose -f docker-compose.prod.yml stop redis

# Copy files back
docker cp ./backup/dump.rdb accountability-redis-prod:/data/
docker cp ./backup/appendonly.aof accountability-redis-prod:/data/

# Start Redis
docker-compose -f docker-compose.prod.yml start redis
```

## Persistence Configuration Summary

| Feature | Configuration | Purpose |
|---------|--------------|---------|
| **RDB Snapshots** | Enabled | Point-in-time backups |
| Save Interval 1 | 900s (15min) / 1 change | Infrequent changes |
| Save Interval 2 | 300s (5min) / 10 changes | Moderate activity |
| Save Interval 3 | 60s (1min) / 10000 changes | High activity |
| **AOF** | Enabled | Write-ahead log |
| Fsync Policy | `everysec` | Balance durability/performance |
| Auto Rewrite | 100% growth, 64MB min | Prevent file bloat |
| **Hybrid** | Enabled | RDB + AOF combined |
| **Max Memory** | 256MB | Memory limit |
| **Eviction** | `allkeys-lru` | LRU eviction policy |

## Data Loss Scenarios

| Scenario | Data Loss | Recovery |
|----------|-----------|----------|
| Normal shutdown | None | Automatic |
| Crash (AOF enabled) | Max 1 second | Automatic from AOF |
| Crash (AOF disabled) | Since last RDB | Restore from RDB |
| Volume deleted | All data | Restore from backup |
| Corrupted AOF | Partial | Use `redis-check-aof --fix` |

## Monitoring Checklist

- [ ] AOF is enabled (`appendonly yes`)
- [ ] Last RDB save status is `ok`
- [ ] AOF file is growing (indicates writes)
- [ ] Memory usage is below max memory
- [ ] Volume is properly mounted
- [ ] Backup files exist in `/data`

## Troubleshooting

### Redis Won't Start

```bash
# Check logs
docker logs accountability-redis-prod

# Common fixes:
# 1. Check config syntax
docker run --rm -v $(pwd)/redis/redis.conf:/redis.conf redis:7-alpine redis-server /redis.conf --test-memory 1

# 2. Check volume permissions
docker volume inspect accountability-redis-data

# 3. Remove corrupted files (CAUTION: data loss)
docker volume rm accountability-redis-data
```

### AOF Corruption

```bash
# Stop Redis
docker-compose -f docker-compose.prod.yml stop redis

# Fix AOF file
docker run --rm -v accountability-redis-data:/data redis:7-alpine redis-check-aof --fix /data/appendonly.aof

# Start Redis
docker-compose -f docker-compose.prod.yml start redis
```

### High Memory Usage

```bash
# Check memory
docker exec accountability-redis-prod redis-cli INFO memory

# Find large keys
docker exec accountability-redis-prod redis-cli --bigkeys

# Check key count
docker exec accountability-redis-prod redis-cli DBSIZE

# Manual eviction (if needed)
docker exec accountability-redis-prod redis-cli FLUSHDB  # CAUTION: Deletes all data!
```

## Best Practices

1. **Regular Backups**: Schedule daily backups of RDB and AOF files
2. **Monitor Disk Space**: Ensure sufficient space for AOF rewrites (2x current size)
3. **Test Restores**: Periodically test backup restoration
4. **Monitor Memory**: Set alerts for memory usage > 80%
5. **Review Logs**: Check for persistence errors regularly
6. **Update Redis**: Keep Redis version up to date for bug fixes

## Configuration Files

- **Config**: `redis/redis.conf` - Main Redis configuration
- **Volume**: `accountability-redis-data` - Persistent data storage
- **Data Dir**: `/data` inside container
- **RDB File**: `/data/dump.rdb`
- **AOF File**: `/data/appendonly.aof`

## Environment Variables

No environment variables needed for basic persistence. All configuration is in `redis.conf`.

Optional: Add password authentication by setting in `redis.conf`:
```conf
requirepass your_password_here
```

Then update `REDIS_URL` in services:
```
REDIS_URL=redis://:your_password_here@redis:6379/0
```

## Performance Impact

| Feature | CPU Impact | Disk I/O | Memory Impact |
|---------|-----------|----------|---------------|
| RDB Snapshots | Medium (during save) | High (during save) | Low |
| AOF (everysec) | Low | Medium | Low |
| AOF Rewrite | Medium | High | Medium |
| Hybrid Mode | Low | Medium | Low |

**Recommendation**: Current configuration (`everysec` fsync) provides good balance of durability and performance for most workloads.

## Further Reading

- Full documentation: `redis/README.md`
- Redis Persistence: https://redis.io/docs/management/persistence/
- Redis Configuration: https://redis.io/docs/management/config/
