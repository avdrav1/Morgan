from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, DBAPIError
from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.alerts import record_database_failure
import time
from typing import Optional

logger = get_logger(__name__)

# Database engine with connection pooling and health checks
# pool_pre_ping ensures connections are tested before use
# This helps handle transient connection failures automatically
# Settings are configurable via environment variables for production tuning
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    connect_args={
        "connect_timeout": settings.DB_CONNECT_TIMEOUT,
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def check_database_health() -> bool:
    """
    Check if database connection is healthy.
    
    Returns:
        bool: True if database is accessible, False otherwise
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        
        # Record failure for alerting
        record_database_failure('health_check', str(e))
        
        return False


def get_db_with_retry(max_retries: int = 3, retry_delay: float = 1.0) -> Optional[Session]:
    """
    Get a database session with retry logic for transient failures.
    
    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        Session: Database session if successful, None if all retries failed
    """
    for attempt in range(max_retries):
        try:
            db = SessionLocal()
            # Test the connection
            db.execute(text("SELECT 1"))
            return db
        except (OperationalError, DBAPIError) as e:
            logger.warning(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
            if db:
                db.close()
            
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
            else:
                logger.error(f"Failed to connect to database after {max_retries} attempts")
                
                # Record failure for alerting on final attempt
                record_database_failure('get_db_with_retry', str(e))
                
                return None
        except Exception as e:
            logger.error(f"Unexpected error getting database session: {e}")
            if db:
                db.close()
            return None


# Dependency for FastAPI
def get_db():
    """
    FastAPI dependency for database sessions.
    
    Provides automatic connection management and cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    except (OperationalError, DBAPIError) as e:
        logger.error(f"Database error during request: {e}")
        
        # Record failure for alerting
        record_database_failure('request_handler', str(e))
        
        db.rollback()
        raise
    finally:
        db.close()
