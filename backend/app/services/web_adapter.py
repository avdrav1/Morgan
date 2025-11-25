import logging
import re
from typing import Dict, Any, Optional, List
from app.services.messaging_adapter import MessagingAdapter

logger = logging.getLogger(__name__)


class WebAdapter(MessagingAdapter):
    """Web interface messaging adapter.
    
    Handles message delivery through the web interface.
    Converts markdown to plain text for web display.
    Messages are stored in the database and retrieved via API.
    """
    
    def __init__(self, max_retries: int = 5, base_delay: float = 1.0):
        """Initialize Web adapter.
        
        Args:
            max_retries: Maximum number of retry attempts (default: 5)
            base_delay: Base delay in seconds for exponential backoff (default: 1.0)
        """
        super().__init__(max_retries=max_retries, base_delay=base_delay)
        # In-memory storage for pending messages
        # In production, this would be stored in the database
        self._pending_messages: Dict[str, List[Dict[str, str]]] = {}
    
    async def send_message(
        self,
        user_identifier: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send a message to a web user.
        
        For web interface, messages are stored and retrieved via API
        rather than pushed in real-time.
        
        Args:
            user_identifier: User ID (UUID string)
            message: The message content to send
            metadata: Optional metadata (e.g., check_in_id, task_id)
            
        Returns:
            bool: True if message was stored successfully, False otherwise
        """
        try:
            formatted_message = self.format_message(message)
            
            # Store message for retrieval
            if user_identifier not in self._pending_messages:
                self._pending_messages[user_identifier] = []
            
            message_data = {
                "message": formatted_message,
                "timestamp": self._get_current_timestamp(),
            }
            
            if metadata:
                message_data.update(metadata)
            
            self._pending_messages[user_identifier].append(message_data)
            
            logger.info(f"Stored web message for user {user_identifier}")
            return True
        
        except Exception as e:
            logger.error(f"Error storing web message: {str(e)}")
            return False
    
    async def handle_incoming_message(
        self,
        user_identifier: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Handle an incoming message from the web interface.
        
        This method would be called by the web API endpoint
        when a user submits a response.
        
        Args:
            user_identifier: User ID (UUID string)
            message: The message content received
            metadata: Optional metadata (e.g., check_in_id, task_id)
        """
        logger.info(f"Received web message from user {user_identifier}: {message}")
        
        # This would typically route to the appropriate handler
        # based on the message content and user state
        # TODO: Implement routing to check-in response handler, etc.
    
    def format_message(self, message: str) -> str:
        """Format a message for web interface.
        
        Converts markdown to plain text by removing markdown syntax.
        
        Args:
            message: The raw message content (may contain markdown)
            
        Returns:
            str: Plain text message with markdown removed
        """
        # Remove markdown formatting for plain text display
        text = message
        
        # Remove code blocks first (```code```)
        text = re.sub(r'```[\s\S]*?```', '', text)
        
        # Remove bold (**text** or __text__) - match content or empty
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text, flags=re.DOTALL)
        text = re.sub(r'__(.+?)__', r'\1', text, flags=re.DOTALL)
        # Remove any remaining ** or __ markers
        text = re.sub(r'\*\*', '', text)
        text = re.sub(r'__', '', text)
        
        # Remove strikethrough (~~text~~) - match content or empty
        text = re.sub(r'~~(.+?)~~', r'\1', text, flags=re.DOTALL)
        # Remove any remaining ~~ markers
        text = re.sub(r'~~', '', text)
        
        # Remove inline code (`code`)
        text = re.sub(r'`(.+?)`', r'\1', text)
        # Remove any remaining ` markers
        text = re.sub(r'`', '', text)
        
        # Remove italic (*text* or _text_) - be careful not to remove underscores in words
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)
        # Remove any remaining * markers
        text = re.sub(r'\*', '', text)
        
        # Remove blockquotes (> text)
        text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
        
        # Remove list markers (- or * at start of line) - already handled * above
        text = re.sub(r'^[\-]\s+', '', text, flags=re.MULTILINE)
        
        # Remove links [text](url) -> text
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
        
        # Clean up extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()
        
        return text
    
    def get_pending_messages(self, user_identifier: str) -> List[Dict[str, str]]:
        """Retrieve pending messages for a user.
        
        Args:
            user_identifier: User ID (UUID string)
            
        Returns:
            List of pending messages
        """
        messages = self._pending_messages.get(user_identifier, [])
        # Clear after retrieval
        if user_identifier in self._pending_messages:
            self._pending_messages[user_identifier] = []
        return messages
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat()
