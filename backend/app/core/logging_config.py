"""
Structured logging configuration with correlation IDs and PII redaction.
"""
import logging
import json
import re
from typing import Any, Dict, Optional
from contextvars import ContextVar
from datetime import datetime
import uuid

# Context variable for correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class PIIRedactor:
    """Redacts personally identifiable information from log messages."""
    
    # Patterns for PII detection
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    DISCORD_ID_PATTERN = re.compile(r'\b\d{17,19}\b')  # Discord IDs are 17-19 digits
    UUID_PATTERN = re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', re.IGNORECASE)
    
    @classmethod
    def redact(cls, text: str) -> str:
        """Redact PII from text."""
        if not isinstance(text, str):
            return text
        
        # Redact emails
        text = cls.EMAIL_PATTERN.sub('[EMAIL_REDACTED]', text)
        
        # Redact Discord IDs (but not other numbers)
        text = cls.DISCORD_ID_PATTERN.sub('[DISCORD_ID_REDACTED]', text)
        
        # Redact UUIDs (user IDs, etc.)
        text = cls.UUID_PATTERN.sub('[UUID_REDACTED]', text)
        
        return text
    
    @classmethod
    def redact_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact PII from dictionary."""
        if not isinstance(data, dict):
            return data
        
        redacted = {}
        for key, value in data.items():
            if isinstance(value, str):
                redacted[key] = cls.redact(value)
            elif isinstance(value, dict):
                redacted[key] = cls.redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [cls.redact_dict(item) if isinstance(item, dict) else cls.redact(str(item)) if isinstance(item, str) else item for item in value]
            else:
                redacted[key] = value
        
        return redacted


class StructuredFormatter(logging.Formatter):
    """JSON formatter with correlation IDs and PII redaction."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with structured fields."""
        correlation_id = correlation_id_var.get()
        
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': PIIRedactor.redact(record.getMessage()),
            'correlation_id': correlation_id,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        if hasattr(record, 'extra_fields'):
            log_data.update(PIIRedactor.redact_dict(record.extra_fields))
        
        return json.dumps(log_data)


class CorrelationIdFilter(logging.Filter):
    """Filter that adds correlation ID to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get()
        return True


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler with structured formatter
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(StructuredFormatter())
    console_handler.addFilter(CorrelationIdFilter())
    
    root_logger.addHandler(console_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('anthropic').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Set correlation ID for current context.
    
    Args:
        correlation_id: Optional correlation ID. If not provided, generates a new UUID.
    
    Returns:
        The correlation ID that was set.
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    
    correlation_id_var.set(correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID from context."""
    return correlation_id_var.get()


def clear_correlation_id() -> None:
    """Clear correlation ID from context."""
    correlation_id_var.set(None)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)


def log_with_context(logger: logging.Logger, level: str, message: str, **extra_fields) -> None:
    """
    Log a message with additional context fields.
    
    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        **extra_fields: Additional fields to include in structured log
    """
    log_func = getattr(logger, level.lower())
    
    # Create a log record with extra fields
    record = logger.makeRecord(
        logger.name,
        getattr(logging, level.upper()),
        "(unknown file)",
        0,
        message,
        (),
        None
    )
    record.extra_fields = extra_fields
    
    logger.handle(record)
