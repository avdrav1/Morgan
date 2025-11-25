from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum
import asyncio
from app.core.logging_config import get_logger
from app.core.alerts import record_message_delivery_failure

logger = get_logger(__name__)


class MessagePlatform(str, Enum):
    """Supported messaging platforms."""
    DISCORD = "discord"
    WEB = "web"


class MessagingAdapter(ABC):
    """Abstract base class for platform-specific messaging adapters.
    
    This interface provides a unified way to send and receive messages
    across different platforms (Discord, web, SMS, etc.) while handling
    platform-specific formatting and delivery requirements.
    """
    
    def __init__(self, max_retries: int = 5, base_delay: float = 1.0):
        """Initialize the messaging adapter.
        
        Args:
            max_retries: Maximum number of retry attempts (default: 5)
            base_delay: Base delay in seconds for exponential backoff (default: 1.0)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    async def send_message_with_retry(
        self,
        user_identifier: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send a message with exponential backoff retry logic.
        
        Implements retry with exponential backoff: 1s, 2s, 4s, 8s, 16s
        
        Args:
            user_identifier: Platform-specific user identifier
            message: The message content to send
            metadata: Optional platform-specific metadata
            
        Returns:
            bool: True if message was sent successfully, False after all retries failed
        """
        logger.info(
            "Attempting to send message",
            extra={
                'extra_fields': {
                    'operation': 'send_message_with_retry',
                    'platform': self.__class__.__name__,
                    'message_length': len(message),
                }
            }
        )
        
        for attempt in range(self.max_retries):
            try:
                success = await self.send_message(user_identifier, message, metadata)
                
                if success:
                    logger.info(
                        "Message sent successfully",
                        extra={
                            'extra_fields': {
                                'operation': 'send_message_with_retry',
                                'platform': self.__class__.__name__,
                                'attempt': attempt + 1,
                                'success': True,
                            }
                        }
                    )
                    return True
                
                # If send_message returned False, retry
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(
                        "Message delivery failed, retrying",
                        extra={
                            'extra_fields': {
                                'operation': 'send_message_with_retry',
                                'platform': self.__class__.__name__,
                                'attempt': attempt + 1,
                                'max_retries': self.max_retries,
                                'retry_delay_seconds': delay,
                            }
                        }
                    )
                    await asyncio.sleep(delay)
            
            except Exception as e:
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.error(
                        "Error sending message, retrying",
                        extra={
                            'extra_fields': {
                                'operation': 'send_message_with_retry',
                                'platform': self.__class__.__name__,
                                'attempt': attempt + 1,
                                'max_retries': self.max_retries,
                                'retry_delay_seconds': delay,
                                'error': str(e),
                            }
                        },
                        exc_info=True
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Failed to send message after {self.max_retries} attempts: {str(e)}"
                    )
                    
                    # Record failure for alerting on final attempt
                    record_message_delivery_failure(
                        platform=self.__class__.__name__,
                        user_identifier=user_identifier,
                        error=str(e)
                    )
        
        logger.error(
            f"Message delivery failed after {self.max_retries} attempts "
            f"to user {user_identifier}"
        )
        
        # Record failure for alerting
        record_message_delivery_failure(
            platform=self.__class__.__name__,
            user_identifier=user_identifier,
            error="Max retries exceeded"
        )
        
        return False
    
    @abstractmethod
    async def send_message(
        self,
        user_identifier: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send a message to a user on this platform.
        
        Args:
            user_identifier: Platform-specific user identifier (e.g., Discord user ID, email)
            message: The message content to send
            metadata: Optional platform-specific metadata (e.g., channel ID, formatting options)
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def handle_incoming_message(
        self,
        user_identifier: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Handle an incoming message from a user on this platform.
        
        Args:
            user_identifier: Platform-specific user identifier
            message: The message content received
            metadata: Optional platform-specific metadata
        """
        pass
    
    @abstractmethod
    def format_message(self, message: str) -> str:
        """Format a message for this platform.
        
        Args:
            message: The raw message content
            
        Returns:
            str: Platform-formatted message
        """
        pass
