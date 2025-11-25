#!/usr/bin/env python3
"""
Database initialization script with migration locking.

This script ensures migrations run safely in production environments by:
1. Waiting for database availability
2. Acquiring a distributed lock to prevent concurrent migrations
3. Running Alembic migrations
4. Verifying the database schema
"""

import os
import sys
import time
import logging
import subprocess
from typing import Optional
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from app.core.config import settings

# Configuration
MAX_RETRIES = 30
RETRY_INTERVAL = 2
LOCK_TIMEOUT = 300  # 5 minutes
MIGRATION_LOCK_ID = 123456789  # Unique ID for advisory lock

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s [%(asctime)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class MigrationLockError(Exception):
    """Raised when migration lock cannot be acquired."""
    pass


class DatabaseInitializer:
    """Handles database initialization with locking."""
    
    def __init__(self):
        self.database_url = settings.DATABASE_URL
        self.engine = None
        self.lock_acquired = False
        
    def wait_for_database(self) -> bool:
        """Wait for database to be ready."""
        logger.info("Waiting for database to be ready...")
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                engine = create_engine(
                    self.database_url,
                    pool_pre_ping=True,
                    connect_args={"connect_timeout": 5}
                )
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.info("Database is ready!")
                engine.dispose()
                return True
            except OperationalError as e:
                if attempt < MAX_RETRIES:
                    logger.warning(
                        f"Database not ready yet (attempt {attempt}/{MAX_RETRIES}). "
                        f"Retrying in {RETRY_INTERVAL}s... Error: {e}"
                    )
                    time.sleep(RETRY_INTERVAL)
                else:
                    logger.error(
                        f"Database failed to become ready after {MAX_RETRIES} attempts"
                    )
                    return False
        
        return False
    
    def acquire_migration_lock(self) -> bool:
        """
        Acquire PostgreSQL advisory lock for migrations.
        
        Returns:
            bool: True if lock acquired, False otherwise
        """
        logger.info("Attempting to acquire migration lock...")
        
        try:
            self.engine = create_engine(self.database_url, pool_pre_ping=True)
            start_time = time.time()
            timeout_time = start_time + LOCK_TIMEOUT
            
            while True:
                with self.engine.connect() as conn:
                    # Try to acquire advisory lock (non-blocking)
                    result = conn.execute(
                        text(f"SELECT pg_try_advisory_lock({MIGRATION_LOCK_ID})")
                    )
                    lock_acquired = result.scalar()
                    
                    if lock_acquired:
                        logger.info("Migration lock acquired successfully")
                        self.lock_acquired = True
                        return True
                
                current_time = time.time()
                if current_time >= timeout_time:
                    logger.error(
                        f"Failed to acquire migration lock within {LOCK_TIMEOUT}s timeout"
                    )
                    return False
                
                logger.warning("Migration lock held by another process. Waiting...")
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"Error acquiring migration lock: {e}")
            return False
    
    def release_migration_lock(self):
        """Release PostgreSQL advisory lock."""
        if self.lock_acquired and self.engine:
            try:
                logger.info("Releasing migration lock...")
                with self.engine.connect() as conn:
                    conn.execute(
                        text(f"SELECT pg_advisory_unlock({MIGRATION_LOCK_ID})")
                    )
                logger.info("Migration lock released")
                self.lock_acquired = False
            except Exception as e:
                logger.warning(f"Error releasing migration lock: {e}")
            finally:
                if self.engine:
                    self.engine.dispose()
    
    def check_database_initialized(self) -> bool:
        """Check if database has been initialized."""
        logger.info("Checking if database is initialized...")
        
        try:
            engine = create_engine(self.database_url, pool_pre_ping=True)
            with engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT EXISTS ("
                    "  SELECT FROM information_schema.tables "
                    "  WHERE table_name = 'alembic_version'"
                    ")"
                ))
                exists = result.scalar()
                
                if exists:
                    logger.info("Database is already initialized")
                else:
                    logger.info("Database is not initialized")
                
                engine.dispose()
                return exists
        except Exception as e:
            logger.error(f"Error checking database initialization: {e}")
            return False
    
    def run_migrations(self) -> bool:
        """Run Alembic migrations."""
        logger.info("Running database migrations...")
        
        try:
            # Get current version
            result = subprocess.run(
                ["alembic", "current"],
                capture_output=True,
                text=True,
                check=False
            )
            current_version = "none"
            if result.returncode == 0:
                # Extract version from output like "abc123 (head)"
                for line in result.stdout.split('\n'):
                    if line.strip():
                        current_version = line.split()[0] if line.split() else "none"
                        break
            
            logger.info(f"Current migration version: {current_version}")
            
            # Run migrations
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                # Get new version
                result = subprocess.run(
                    ["alembic", "current"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                new_version = "unknown"
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            new_version = line.split()[0] if line.split() else "unknown"
                            break
                
                logger.info(f"Migrations completed successfully. New version: {new_version}")
                return True
            else:
                logger.error(f"Migration failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error running migrations: {e}")
            return False
    
    def verify_database_schema(self) -> bool:
        """Verify that essential tables exist."""
        logger.info("Verifying database schema...")
        
        required_tables = [
            "users",
            "projects",
            "tasks",
            "check_ins",
            "alembic_version"
        ]
        
        try:
            engine = create_engine(self.database_url, pool_pre_ping=True)
            with engine.connect() as conn:
                for table in required_tables:
                    result = conn.execute(text(
                        f"SELECT EXISTS ("
                        f"  SELECT FROM information_schema.tables "
                        f"  WHERE table_name = '{table}'"
                        f")"
                    ))
                    exists = result.scalar()
                    
                    if not exists:
                        logger.error(f"Required table '{table}' not found in database")
                        engine.dispose()
                        return False
            
            logger.info("Database schema verification passed")
            engine.dispose()
            return True
            
        except Exception as e:
            logger.error(f"Error verifying database schema: {e}")
            return False
    
    def initialize(self) -> bool:
        """
        Main initialization function.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        logger.info("Starting database initialization...")
        logger.info(f"Environment: {settings.ENVIRONMENT}")
        
        try:
            # Step 1: Wait for database
            if not self.wait_for_database():
                logger.error("Database initialization failed: database not available")
                return False
            
            # Step 2: Acquire migration lock
            if not self.acquire_migration_lock():
                logger.error("Database initialization failed: could not acquire lock")
                return False
            
            # Step 3: Check if database is initialized
            if self.check_database_initialized():
                logger.info("Database already initialized, checking for pending migrations...")
            else:
                logger.info("Initializing database for the first time...")
            
            # Step 4: Run migrations
            if not self.run_migrations():
                logger.error("Database initialization failed: migration error")
                return False
            
            # Step 5: Verify schema
            if not self.verify_database_schema():
                logger.error("Database initialization failed: schema verification error")
                return False
            
            logger.info("Database initialization completed successfully!")
            return True
            
        finally:
            # Always release lock
            self.release_migration_lock()


def main():
    """Main entry point."""
    initializer = DatabaseInitializer()
    
    try:
        success = initializer.initialize()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("Initialization interrupted by user")
        initializer.release_migration_lock()
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during initialization: {e}", exc_info=True)
        initializer.release_migration_lock()
        sys.exit(1)


if __name__ == "__main__":
    main()
