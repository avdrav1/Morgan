from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Proactive Accountability Assistant"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "postgresql://accountability:accountability_dev@localhost:5432/accountability_db"
    
    # Database Connection Pool Settings (production optimized)
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600  # 1 hour
    DB_POOL_PRE_PING: bool = True
    DB_CONNECT_TIMEOUT: int = 10
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT Authentication
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Anthropic API
    ANTHROPIC_API_KEY: str
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    
    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]
    
    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
    # Discord OAuth
    DISCORD_CLIENT_ID: Optional[str] = None
    DISCORD_CLIENT_SECRET: Optional[str] = None
    DISCORD_REDIRECT_URI: str = "http://localhost:8000/api/auth/discord/callback"
    
    # Frontend URL
    FRONTEND_URL: str = "http://localhost:5173"
    
    # Encryption
    ENCRYPTION_KEY: Optional[str] = None
    
    # Webhooks
    WEBHOOK_SECRET: Optional[str] = None
    
    # Gunicorn Settings
    GUNICORN_WORKERS: int = 4
    GUNICORN_TIMEOUT: int = 120
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set Celery URLs to Redis URL if not specified
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL
        
        # Production-specific settings
        if self.ENVIRONMENT == "production":
            self.DEBUG = False
            # Ensure production has higher log level
            if self.LOG_LEVEL == "DEBUG":
                self.LOG_LEVEL = "INFO"


settings = Settings()
