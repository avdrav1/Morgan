"""
Middleware for request tracking and logging.
"""
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logging_config import set_correlation_id, clear_correlation_id, get_logger

logger = get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation IDs to all requests."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with correlation ID tracking.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
        
        Returns:
            HTTP response with correlation ID header
        """
        # Get or generate correlation ID
        correlation_id = request.headers.get('X-Correlation-ID')
        correlation_id = set_correlation_id(correlation_id)
        
        # Track request timing
        start_time = time.time()
        
        # Log incoming request
        logger.info(
            f"Incoming request: {request.method} {request.url.path}",
            extra={
                'extra_fields': {
                    'method': request.method,
                    'path': request.url.path,
                    'query_params': str(request.query_params),
                    'client_host': request.client.host if request.client else None,
                }
            }
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            logger.info(
                f"Request completed: {request.method} {request.url.path}",
                extra={
                    'extra_fields': {
                        'method': request.method,
                        'path': request.url.path,
                        'status_code': response.status_code,
                        'duration_ms': round(duration_ms, 2),
                    }
                }
            )
            
            # Add correlation ID to response headers
            response.headers['X-Correlation-ID'] = correlation_id
            
            return response
            
        except Exception as e:
            # Log error
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    'extra_fields': {
                        'method': request.method,
                        'path': request.url.path,
                        'duration_ms': round(duration_ms, 2),
                        'error': str(e),
                    }
                },
                exc_info=True
            )
            raise
        
        finally:
            # Clear correlation ID from context
            clear_correlation_id()
