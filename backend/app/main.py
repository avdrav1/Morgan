from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import check_database_health
from app.core.logging_config import setup_logging, get_logger
from app.core.middleware import CorrelationIdMiddleware
from app.api import auth, projects, tasks, users, check_ins, discord, metrics, webhooks

# Setup structured logging with configurable log level
setup_logging(log_level=settings.LOG_LEVEL)
logger = get_logger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="AI-powered accountability assistant API"
)

# Add correlation ID middleware (before CORS)
app.add_middleware(CorrelationIdMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("Application starting", extra={'extra_fields': {'environment': settings.ENVIRONMENT}})

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(check_ins.router, prefix="/api/check-ins", tags=["Check-ins"])
app.include_router(discord.router, prefix="/api/discord", tags=["Discord"])
app.include_router(metrics.router, prefix="/api", tags=["Metrics"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])


@app.get("/")
async def root():
    return {
        "message": "Proactive Accountability Assistant API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint with database connectivity test.
    
    Returns 200 if healthy, 503 if database is unavailable.
    """
    from fastapi.responses import JSONResponse
    
    db_healthy = check_database_health()
    
    if db_healthy:
        return {
            "status": "healthy",
            "database": "connected"
        }
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected"
            }
        )
