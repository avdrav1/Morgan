# Redis Configuration

This directory contains the Redis configuration for the Proactive Accountability Assistant production deployment.

## Persistence Strategy

Redis is configured with **hybrid persistence** combining both RDB snapshots and AOF (Append Only File) for maximum data durability.

### RDB Snapshots

RDB creates point-in-time snapshots of your dataset at specified intervals.

**Configuration:**
- Save after 15 minutes if at least 1 key changed
- Save after 5 minutes if at least 10 keys changed  
- Save after 1 minute if at least 10,000 keys changed

**Benefits:**
- Compact single-file backups
- Faster restarts with large datasets
- Good for disaster recovery

**File:** `/data/dump.rdb`

### AOF (Append Only File)

AOF logs every write operation received by the server, allowing reconstruction of the dataset.

**Configuration:**
- `appendfsync everysec`: Fsync every second (recommended balance of performance and durability)
- Automatic rewrite when file grows by 100% and is at least 64MB
- RDB-AOF hybrid format enabled for faster loading

**Benefits:**
- Better durability (at most 1 second of data loss)
- Append-only format is more durable
- Automatic background rewriting prevents file from growing indefinitely

**File:** `/data/appendonly.aof`

### Hybrid Persistence (RDB-AOF)

Redis 4.0+ supports hybrid persistence where AOF rewrites use RDB format for the initial snapshot, then append AOF for subsequent changes.

**Benefits:**
- Fast loading (RDB format)
- Durability of AOF
- Best of both worlds

## Memory Management

**Max Memory:** 256MB (configurable via `maxmemory` in redis.conf)

**Eviction Policy:** `allkeys-lru` (Least Recently Used)
- When max memory is reached, Redis will evict the least recently used keys
- Suitable for cache-like workloads

## Security

### Disabled Commands

The following dangerous commands are disabled in production:
- `FLUSHDB` - Prevents accidental database deletion
- `FLUSHALL` - Prevents accidental deletion of all databases
- `CONFIG` - Prevents runtime configuration changes

### Authentication

To enable Redis authentication, uncomment and set the `requirepass` directive in `redis.conf`:

```conf
requirepass your_strong_password_here
```

Then update the `REDIS_URL` environment variable in your services:

```
REDIS_URL=redis://:your_strong_password_here@redis:6379/0
```

## Data Directory

All Redis data is stored in `/data` inside the container, which is mounted to the `redis_data` Docker volume.

**Files:**
- `/data/dump.rdb` - RDB snapshot file
- `/data/appendonly.aof` - AOF log file

## Monitoring

### Check Persistence Status

```bash
# Connect to Redis container
docker exec -it accountability-redis-prod redis-cli

# Check last save time
LASTSAVE

# Check AOF status
INFO persistence

# Check memory usage
INFO memory
```

### Key Metrics

```bash
# Get all persistence-related info
INFO persistence

# Key metrics to monitor:
# - rdb_last_save_time: Unix timestamp of last successful RDB save
# - rdb_changes_since_last_save: Number of changes since last save
# - aof_enabled: Whether AOF is enabled (should be 1)
# - aof_current_size: Current AOF file size
# - aof_base_size: AOF size at last rewrite
```

## Backup and Recovery

### Manual Backup

```bash
# Trigger immediate RDB snapshot
docker exec accountability-redis-prod redis-cli BGSAVE

# Copy RDB file from volume
docker cp accountability-redis-prod:/data/dump.rdb ./backup/redis-dump-$(date +%Y%m%d-%H%M%S).rdb

# Copy AOF file from volume
docker cp accountability-redis-prod:/data/appendonly.aof ./backup/redis-aof-$(date +%Y%m%d-%H%M%S).aof
```

### Restore from Backup

```bash
# Stop Redis container
docker-compose -f docker-compose.prod.yml stop redis

# Copy backup files to volume
docker cp ./backup/dump.rdb accountability-redis-prod:/data/dump.rdb
docker cp ./backup/appendonly.aof accountability-redis-prod:/data/appendonly.aof

# Start Redis container
docker-compose -f docker-compose.prod.yml start redis

# Verify data restored
docker exec accountability-redis-prod redis-cli DBSIZE
```

## Troubleshooting

### Redis Won't Start

Check logs:
```bash
docker logs accountability-redis-prod
```

Common issues:
- Configuration syntax errors
- Permission issues with data directory
- Port already in use

### Data Not Persisting

1. Check if AOF is enabled:
```bash
docker exec accountability-redis-prod redis-cli CONFIG GET appendonly
```

2. Check last save status:
```bash
docker exec accountability-redis-prod redis-cli INFO persistence
```

3. Verify volume is mounted:
```bash
docker inspect accountability-redis-prod | grep -A 10 Mounts
```

### High Memory Usage

1. Check memory stats:
```bash
docker exec accountability-redis-prod redis-cli INFO memory
```

2. Check key count:
```bash
docker exec accountability-redis-prod redis-cli DBSIZE
```

3. Find large keys:
```bash
docker exec accountability-redis-prod redis-cli --bigkeys
```

### AOF File Corruption

If AOF file is corrupted, Redis provides a repair tool:

```bash
# Stop Redis
docker-compose -f docker-compose.prod.yml stop redis

# Run repair tool
docker run --rm -v accountability-redis-data:/data redis:7-alpine redis-check-aof --fix /data/appendonly.aof

# Start Redis
docker-compose -f docker-compose.prod.yml start redis
```

## Performance Tuning

### For Cache Workload

If using Redis primarily as a cache:

```conf
maxmemory 512mb
maxmemory-policy allkeys-lru
save ""  # Disable RDB snapshots
appendonly no  # Disable AOF
```

### For Queue Workload (Celery)

If using Redis primarily for Celery task queue:

```conf
maxmemory 256mb
maxmemory-policy noeviction  # Don't evict keys
appendonly yes
appendfsync everysec
```

### For Session Store

If using Redis for session storage:

```conf
maxmemory 512mb
maxmemory-policy volatile-lru  # Only evict keys with TTL
appendonly yes
appendfsync everysec
```

## Configuration Reference

| Setting | Value | Description |
|---------|-------|-------------|
| `save 900 1` | 15 min, 1 change | RDB snapshot trigger |
| `save 300 10` | 5 min, 10 changes | RDB snapshot trigger |
| `save 60 10000` | 1 min, 10k changes | RDB snapshot trigger |
| `appendonly yes` | Enabled | Enable AOF persistence |
| `appendfsync everysec` | Every second | AOF fsync frequency |
| `aof-use-rdb-preamble yes` | Enabled | Hybrid RDB-AOF format |
| `maxmemory 256mb` | 256 MB | Maximum memory limit |
| `maxmemory-policy allkeys-lru` | LRU eviction | Eviction policy |

## Further Reading

- [Redis Persistence Documentation](https://redis.io/docs/management/persistence/)
- [Redis Configuration Documentation](https://redis.io/docs/management/config/)
- [Redis Security Documentation](https://redis.io/docs/management/security/)
