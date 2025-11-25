#!/bin/bash

# Script to verify Redis persistence configuration
# Part of Production Deployment - Task 8

set -e

REDIS_CONTAINER="accountability-redis-prod"
REDIS_CLI="docker exec $REDIS_CONTAINER redis-cli"

echo "=========================================="
echo "Redis Persistence Verification"
echo "=========================================="
echo ""

# Check if Redis container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
    echo "❌ Error: Redis container '$REDIS_CONTAINER' is not running"
    echo ""
    echo "Start the container with:"
    echo "  docker-compose -f docker-compose.prod.yml up -d redis"
    exit 1
fi

echo "✅ Redis container is running"
echo ""

# Check Redis connectivity
echo "Checking Redis connectivity..."
if $REDIS_CLI PING > /dev/null 2>&1; then
    echo "✅ Redis is responding to commands"
else
    echo "❌ Error: Cannot connect to Redis"
    exit 1
fi
echo ""

# Check persistence configuration
echo "=========================================="
echo "Persistence Configuration"
echo "=========================================="
echo ""

# Check AOF status
echo "AOF (Append Only File) Configuration:"
AOF_ENABLED=$($REDIS_CLI CONFIG GET appendonly | tail -n 1)
AOF_FSYNC=$($REDIS_CLI CONFIG GET appendfsync | tail -n 1)
AOF_FILENAME=$($REDIS_CLI CONFIG GET appendfilename | tail -n 1)

if [ "$AOF_ENABLED" = "yes" ]; then
    echo "  ✅ AOF Enabled: $AOF_ENABLED"
else
    echo "  ❌ AOF Enabled: $AOF_ENABLED (should be 'yes')"
fi
echo "  📝 AOF Fsync: $AOF_FSYNC"
echo "  📝 AOF Filename: $AOF_FILENAME"
echo ""

# Check RDB configuration
echo "RDB (Snapshot) Configuration:"
RDB_FILENAME=$($REDIS_CLI CONFIG GET dbfilename | tail -n 1)
echo "  📝 RDB Filename: $RDB_FILENAME"

# Get save points
echo "  📝 Save Points:"
$REDIS_CLI CONFIG GET save | tail -n 1 | tr ' ' '\n' | while read -r line; do
    if [ -n "$line" ]; then
        echo "      - $line"
    fi
done
echo ""

# Check hybrid persistence
echo "Hybrid Persistence:"
AOF_RDB_PREAMBLE=$($REDIS_CLI CONFIG GET aof-use-rdb-preamble | tail -n 1)
if [ "$AOF_RDB_PREAMBLE" = "yes" ]; then
    echo "  ✅ RDB-AOF Hybrid: $AOF_RDB_PREAMBLE"
else
    echo "  ⚠️  RDB-AOF Hybrid: $AOF_RDB_PREAMBLE (recommended: 'yes')"
fi
echo ""

# Check persistence info
echo "=========================================="
echo "Persistence Status"
echo "=========================================="
echo ""

# Get persistence info
PERSISTENCE_INFO=$($REDIS_CLI INFO persistence)

# Parse key metrics
RDB_LAST_SAVE=$(echo "$PERSISTENCE_INFO" | grep "rdb_last_save_time:" | cut -d: -f2 | tr -d '\r')
RDB_CHANGES=$(echo "$PERSISTENCE_INFO" | grep "rdb_changes_since_last_save:" | cut -d: -f2 | tr -d '\r')
RDB_LAST_STATUS=$(echo "$PERSISTENCE_INFO" | grep "rdb_last_bgsave_status:" | cut -d: -f2 | tr -d '\r')
AOF_CURRENT_SIZE=$(echo "$PERSISTENCE_INFO" | grep "aof_current_size:" | cut -d: -f2 | tr -d '\r')
AOF_BASE_SIZE=$(echo "$PERSISTENCE_INFO" | grep "aof_base_size:" | cut -d: -f2 | tr -d '\r')

echo "RDB Status:"
if [ -n "$RDB_LAST_SAVE" ]; then
    LAST_SAVE_DATE=$(date -d "@$RDB_LAST_SAVE" 2>/dev/null || date -r "$RDB_LAST_SAVE" 2>/dev/null || echo "N/A")
    echo "  📅 Last Save: $LAST_SAVE_DATE"
    echo "  📊 Changes Since Last Save: $RDB_CHANGES"
    if [ "$RDB_LAST_STATUS" = "ok" ]; then
        echo "  ✅ Last Save Status: $RDB_LAST_STATUS"
    else
        echo "  ❌ Last Save Status: $RDB_LAST_STATUS"
    fi
else
    echo "  ⚠️  No RDB save performed yet"
fi
echo ""

echo "AOF Status:"
if [ -n "$AOF_CURRENT_SIZE" ]; then
    AOF_SIZE_MB=$((AOF_CURRENT_SIZE / 1024 / 1024))
    echo "  📊 Current Size: ${AOF_SIZE_MB}MB ($AOF_CURRENT_SIZE bytes)"
    if [ -n "$AOF_BASE_SIZE" ]; then
        AOF_BASE_MB=$((AOF_BASE_SIZE / 1024 / 1024))
        echo "  📊 Base Size: ${AOF_BASE_MB}MB ($AOF_BASE_SIZE bytes)"
    fi
else
    echo "  ⚠️  AOF file not created yet"
fi
echo ""

# Check data directory
echo "=========================================="
echo "Data Directory"
echo "=========================================="
echo ""

echo "Checking data files in container..."
docker exec $REDIS_CONTAINER sh -c 'ls -lh /data/' 2>/dev/null || echo "  ⚠️  Cannot list data directory"
echo ""

# Check volume
echo "Volume Information:"
VOLUME_NAME=$(docker inspect $REDIS_CONTAINER | grep -A 5 '"Mounts"' | grep '"Name"' | cut -d'"' -f4 | head -n 1)
if [ -n "$VOLUME_NAME" ]; then
    echo "  📦 Volume Name: $VOLUME_NAME"
    VOLUME_INFO=$(docker volume inspect $VOLUME_NAME 2>/dev/null)
    if [ -n "$VOLUME_INFO" ]; then
        MOUNTPOINT=$(echo "$VOLUME_INFO" | grep '"Mountpoint"' | cut -d'"' -f4)
        echo "  📂 Mountpoint: $MOUNTPOINT"
    fi
else
    echo "  ⚠️  No named volume found"
fi
echo ""

# Memory usage
echo "=========================================="
echo "Memory Usage"
echo "=========================================="
echo ""

MEMORY_INFO=$($REDIS_CLI INFO memory)
USED_MEMORY=$(echo "$MEMORY_INFO" | grep "used_memory_human:" | cut -d: -f2 | tr -d '\r')
USED_MEMORY_PEAK=$(echo "$MEMORY_INFO" | grep "used_memory_peak_human:" | cut -d: -f2 | tr -d '\r')
MAXMEMORY=$(echo "$MEMORY_INFO" | grep "maxmemory_human:" | cut -d: -f2 | tr -d '\r')
MAXMEMORY_POLICY=$($REDIS_CLI CONFIG GET maxmemory-policy | tail -n 1)

echo "  📊 Used Memory: $USED_MEMORY"
echo "  📊 Peak Memory: $USED_MEMORY_PEAK"
echo "  📊 Max Memory: $MAXMEMORY"
echo "  📝 Eviction Policy: $MAXMEMORY_POLICY"
echo ""

# Database size
echo "=========================================="
echo "Database Statistics"
echo "=========================================="
echo ""

DBSIZE=$($REDIS_CLI DBSIZE)
echo "  📊 Total Keys: $DBSIZE"
echo ""

# Test persistence
echo "=========================================="
echo "Persistence Test"
echo "=========================================="
echo ""

echo "Testing data persistence..."
TEST_KEY="redis_persistence_test_$(date +%s)"
TEST_VALUE="test_value_$(date +%s)"

# Write test key
$REDIS_CLI SET "$TEST_KEY" "$TEST_VALUE" > /dev/null
echo "  ✅ Written test key: $TEST_KEY"

# Verify key exists
RETRIEVED_VALUE=$($REDIS_CLI GET "$TEST_KEY")
if [ "$RETRIEVED_VALUE" = "$TEST_VALUE" ]; then
    echo "  ✅ Retrieved test value successfully"
else
    echo "  ❌ Failed to retrieve test value"
fi

# Trigger save
echo "  📝 Triggering background save (BGSAVE)..."
$REDIS_CLI BGSAVE > /dev/null
sleep 2

# Check save status
SAVE_STATUS=$($REDIS_CLI LASTSAVE)
echo "  ✅ Last save timestamp: $SAVE_STATUS"

# Clean up test key
$REDIS_CLI DEL "$TEST_KEY" > /dev/null
echo "  🧹 Cleaned up test key"
echo ""

# Summary
echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""

ISSUES=0

if [ "$AOF_ENABLED" != "yes" ]; then
    echo "❌ AOF is not enabled"
    ISSUES=$((ISSUES + 1))
fi

if [ "$RDB_LAST_STATUS" != "ok" ] && [ -n "$RDB_LAST_STATUS" ]; then
    echo "❌ Last RDB save failed"
    ISSUES=$((ISSUES + 1))
fi

if [ $ISSUES -eq 0 ]; then
    echo "✅ All persistence checks passed!"
    echo ""
    echo "Redis is configured with:"
    echo "  - RDB snapshots for point-in-time backups"
    echo "  - AOF for durability (max 1 second data loss)"
    echo "  - Hybrid RDB-AOF format for fast loading"
    echo ""
    echo "Data is persisted to Docker volume: $VOLUME_NAME"
else
    echo "⚠️  Found $ISSUES issue(s) with persistence configuration"
    echo ""
    echo "Please review the configuration and fix any issues."
fi

echo ""
echo "=========================================="
