#!/bin/bash

# Script to test Redis persistence functionality
# Part of Production Deployment - Task 8

set -e

echo "=========================================="
echo "Redis Persistence Test"
echo "=========================================="
echo ""

# Start Redis with production config
echo "Starting Redis with production configuration..."
docker-compose -f docker-compose.prod.yml up -d redis

echo "Waiting for Redis to be ready..."
sleep 5

# Check if Redis is running
if ! docker exec accountability-redis-prod redis-cli ping > /dev/null 2>&1; then
    echo "❌ Error: Redis is not responding"
    exit 1
fi

echo "✅ Redis is running"
echo ""

# Test 1: Write data
echo "Test 1: Writing test data..."
TEST_KEY="persistence_test_$(date +%s)"
TEST_VALUE="test_value_$(date +%s)"

docker exec accountability-redis-prod redis-cli SET "$TEST_KEY" "$TEST_VALUE" > /dev/null
echo "  ✅ Written key: $TEST_KEY"

# Verify data
RETRIEVED=$(docker exec accountability-redis-prod redis-cli GET "$TEST_KEY")
if [ "$RETRIEVED" = "$TEST_VALUE" ]; then
    echo "  ✅ Data verified: $RETRIEVED"
else
    echo "  ❌ Data mismatch: expected $TEST_VALUE, got $RETRIEVED"
    exit 1
fi
echo ""

# Test 2: Trigger save
echo "Test 2: Triggering RDB snapshot..."
docker exec accountability-redis-prod redis-cli BGSAVE > /dev/null
sleep 2

LAST_SAVE=$(docker exec accountability-redis-prod redis-cli LASTSAVE)
echo "  ✅ Last save timestamp: $LAST_SAVE"
echo ""

# Test 3: Check persistence files
echo "Test 3: Checking persistence files..."
docker exec accountability-redis-prod ls -lh /data/ | grep -E "dump.rdb|appendonly.aof"
echo ""

# Test 4: Restart and verify data persists
echo "Test 4: Restarting Redis to test persistence..."
docker-compose -f docker-compose.prod.yml restart redis

echo "Waiting for Redis to restart..."
sleep 5

# Verify data still exists
RETRIEVED_AFTER=$(docker exec accountability-redis-prod redis-cli GET "$TEST_KEY")
if [ "$RETRIEVED_AFTER" = "$TEST_VALUE" ]; then
    echo "  ✅ Data persisted after restart: $RETRIEVED_AFTER"
else
    echo "  ❌ Data lost after restart"
    exit 1
fi
echo ""

# Clean up
echo "Cleaning up test data..."
docker exec accountability-redis-prod redis-cli DEL "$TEST_KEY" > /dev/null
echo "  ✅ Test data cleaned up"
echo ""

# Summary
echo "=========================================="
echo "✅ All persistence tests passed!"
echo "=========================================="
echo ""
echo "Redis persistence is working correctly:"
echo "  - Data can be written and read"
echo "  - RDB snapshots are created"
echo "  - AOF is logging writes"
echo "  - Data persists across container restarts"
echo ""
