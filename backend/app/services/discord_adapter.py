import httpx
import logging
from typing import Dict, Any, Optional
from app.services.messaging_adapter import MessagingAdapter
from app.core.config import settings

logger = logging.getLogger(__name__)


class DiscordAdapter(MessagingAdapter):
    """Discord-specific messaging adapter.
    
    Handles message sending and receiving through Discord bot integration.
    Supports Discord markdown formatting.
    """
    
    def __init__(
        self, 
        discord_bot_url: Optional[str] = None,
        max_retries: int = 5,
        base_delay: float = 1.0
    ):
        """Initialize Discord adapter.
        
        Args:
            discord_bot_url: URL of the Discord bot HTTP endpoint
            max_retries: Maximum number of retry attempts (default: 5)
            base_delay: Base delay in seconds for exponential backoff (default: 1.0)
        """
        super().__init__(max_retries=max_retries, base_delay=base_delay)
        self.discord_bot_url = discord_bot_url or getattr(
            settings, 
            'DISCORD_BOT_URL', 
            'http://discord-bot:8001'
        )
        self.timeout = 30.0
    
    async def send_message(
        self,
        user_identifier: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send a message to a Discord user.
        
        Handles Discord-specific errors including:
        - User blocking the bot (returns False, logged as warning)
        - Missing permissions (returns False, logged as error)
        - Rate limiting (returns False, logged as error)
        - Network timeouts (returns False, logged as error)
        
        Args:
            user_identifier: Discord user ID
            message: The message content to send
            metadata: Optional metadata (not used for Discord)
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        try:
            formatted_message = self.format_message(message)
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.discord_bot_url}/send_message",
                    json={
                        "discord_user_id": user_identifier,
                        "message": formatted_message
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully sent Discord message to user {user_identifier}")
                    return True
                elif response.status_code == 400:
                    # Bad request - invalid parameters
                    error_data = response.json() if response.text else {}
                    logger.error(
                        f"Bad request sending Discord message to {user_identifier}: "
                        f"{error_data.get('details', response.text)}"
                    )
                    return False
                elif response.status_code == 500:
                    # Discord bot couldn't deliver - user blocked, no DMs, etc.
                    error_data = response.json() if response.text else {}
                    details = error_data.get('details', 'Unknown error')
                    
                    # Log as warning if user blocked (expected behavior)
                    # Log as error for other issues
                    if 'blocked' in details.lower() or 'disabled DMs' in details:
                        logger.warning(
                            f"Cannot send Discord message to {user_identifier}: {details}"
                        )
                    else:
                        logger.error(
                            f"Failed to send Discord message to {user_identifier}: {details}"
                        )
                    return False
                else:
                    logger.error(
                        f"Unexpected status sending Discord message: "
                        f"{response.status_code} - {response.text}"
                    )
                    return False
        
        except httpx.TimeoutException:
            logger.error(
                f"Timeout sending Discord message to user {user_identifier} "
                f"(timeout: {self.timeout}s)"
            )
            return False
        except httpx.RequestError as e:
            logger.error(
                f"Network error sending Discord message to {user_identifier}: {str(e)}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error sending Discord message to {user_identifier}: {str(e)}",
                exc_info=True
            )
            return False
    
    async def handle_incoming_message(
        self,
        user_identifier: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Handle an incoming message from Discord.
        
        This method would be called by the Discord bot webhook handler
        to process incoming messages from users.
        
        Args:
            user_identifier: Discord user ID
            message: The message content received
            metadata: Optional metadata (e.g., author name, channel info)
        """
        logger.info(f"Received Discord message from user {user_identifier}: {message}")
        
        # This would typically route to the appropriate handler
        # based on the message content and user state
        # For now, we just log it
        # TODO: Implement routing to check-in response handler, etc.
    
    def format_message(self, message: str) -> str:
        """Format a message for Discord.
        
        Discord supports markdown formatting including:
        - **bold**
        - *italic*
        - __underline__
        - ~~strikethrough~~
        - `code`
        - ```code blocks```
        - > quotes
        - Lists with - or *
        
        Args:
            message: The raw message content
            
        Returns:
            str: Discord-formatted message (preserves markdown)
        """
        # Discord natively supports markdown, so we preserve it
        # We could add additional formatting here if needed
        return message
