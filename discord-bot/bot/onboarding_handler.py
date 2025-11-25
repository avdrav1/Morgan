"""
Discord bot handler for onboarding flow.

This module handles Discord DM interactions during the onboarding process,
routing messages to the backend onboarding service and managing message delivery.
"""

import discord
import asyncio
import logging
from typing import Optional, Dict, Any
from collections import deque
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class OnboardingBotHandler:
    """
    Handler for Discord DM onboarding interactions.
    
    Routes incoming DMs to the onboarding service and manages
    outgoing message delivery with rate limiting, queuing, and exponential backoff.
    
    Features:
    - Message queuing per user
    - Rate limiting (1 message/second per user)
    - Exponential backoff on Discord API errors
    - Automatic retry with backoff on transient failures
    """
    
    def __init__(
        self,
        bot: discord.Client,
        api_base_url: str,
        rate_limit_delay: float = 1.0,
        max_retries: int = 5,
        base_backoff_delay: float = 1.0
    ):
        """
        Initialize the onboarding bot handler.
        
        Args:
            bot: Discord bot client instance
            api_base_url: Base URL for backend API
            rate_limit_delay: Delay between messages to same user (seconds)
            max_retries: Maximum retry attempts for failed messages
            base_backoff_delay: Base delay for exponential backoff (seconds)
        """
        self.bot = bot
        self.api_base_url = api_base_url
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.base_backoff_delay = base_backoff_delay
        
        # Message queue: user_id -> deque of message data
        self.message_queues: Dict[str, deque] = {}
        
        # Track last message time per user for rate limiting
        self.last_message_time: Dict[str, datetime] = {}
        
        # Queue processing tasks
        self.queue_tasks: Dict[str, asyncio.Task] = {}
        
        # Track retry counts per message
        self.retry_counts: Dict[str, int] = {}
    
    async def on_message(self, message: discord.Message) -> None:
        """
        Handle incoming Discord DM messages during onboarding.
        
        Routes messages to the backend onboarding service for processing.
        Handles errors gracefully and provides user feedback.
        
        Args:
            message: Discord message object
            
        Validates: Requirements 1.2, 2.1
        """
        # Ignore messages from the bot itself
        if message.author == self.bot.user:
            return
        
        # Only handle DMs
        if not isinstance(message.channel, discord.DMChannel):
            return
        
        user_id = str(message.author.id)
        content = message.content
        
        logger.info(
            f"Onboarding handler received DM from {message.author.name} "
            f"(ID: {user_id}): {content[:50]}..."
        )
        
        try:
            # Send message to backend onboarding service
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_base_url}/api/webhooks/onboarding/message",
                    json={
                        "discord_user_id": user_id,
                        "message": content,
                        "author_name": message.author.name
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    reply = data.get("reply")
                    
                    if reply:
                        # Queue the reply message
                        await self.send_onboarding_message(user_id, reply)
                        logger.info(f"Queued onboarding reply for {message.author.name}")
                    
                elif response.status_code == 404:
                    # No active onboarding session
                    logger.info(f"No active onboarding session for user {user_id}")
                    await message.channel.send(
                        "I don't have an active onboarding session for you. "
                        "If you just signed up, please wait a moment and try again!"
                    )
                    
                elif response.status_code == 400:
                    # Invalid input or validation error
                    data = response.json()
                    error_message = data.get("message", "I didn't understand that.")
                    await message.channel.send(error_message)
                    logger.warning(
                        f"Validation error for user {user_id}: {error_message}"
                    )
                    
                else:
                    logger.error(
                        f"Onboarding API error: {response.status_code} - {response.text}"
                    )
                    await message.channel.send(
                        "Sorry, I'm having trouble processing your message right now. "
                        "Please try again in a moment."
                    )
        
        except httpx.TimeoutException:
            logger.error(f"Timeout processing onboarding message from {user_id}")
            await message.channel.send(
                "Sorry, that took too long to process. Please try again."
            )
        
        except httpx.RequestError as e:
            logger.error(f"Network error in onboarding handler: {str(e)}")
            await message.channel.send(
                "Sorry, I'm having connection issues. Please try again later."
            )
        
        except Exception as e:
            logger.error(
                f"Unexpected error in onboarding handler: {str(e)}",
                exc_info=True
            )
            await message.channel.send(
                "Sorry, something unexpected went wrong. Please try again later."
            )
    
    async def send_onboarding_message(
        self,
        discord_user_id: str,
        message: str
    ) -> bool:
        """
        Send an onboarding message to a Discord user with rate limiting.
        
        Messages are queued and sent with rate limiting to respect Discord's
        API limits. Handles Discord-specific errors including blocked users
        and disabled DMs.
        
        Args:
            discord_user_id: Discord user ID as string
            message: Message content to send (supports Discord markdown)
            
        Returns:
            bool: True if message was queued successfully, False otherwise
            
        Validates: Requirements 1.2, 2.1
        """
        logger.info(f"Queueing onboarding message for user {discord_user_id}")
        
        # Initialize queue for this user if needed
        if discord_user_id not in self.message_queues:
            self.message_queues[discord_user_id] = deque()
        
        # Add message to queue
        self.message_queues[discord_user_id].append({
            "message": message,
            "timestamp": datetime.utcnow()
        })
        
        # Start queue processor if not already running
        if discord_user_id not in self.queue_tasks or self.queue_tasks[discord_user_id].done():
            self.queue_tasks[discord_user_id] = asyncio.create_task(
                self._process_message_queue(discord_user_id)
            )
        
        return True
    
    async def _process_message_queue(self, discord_user_id: str) -> None:
        """
        Process queued messages for a user with rate limiting.
        
        Sends messages from the queue one at a time, respecting the
        rate limit delay between messages. Implements exponential backoff
        for failed messages through _send_message_direct.
        
        Features:
        - Rate limiting: 1 message per second per user
        - Automatic retry with exponential backoff for transient failures
        - Graceful handling of permanent failures (user blocked, not found)
        - Queue cleanup on completion
        
        Args:
            discord_user_id: Discord user ID as string
        """
        logger.info(
            f"Starting message queue processor for user {discord_user_id} "
            f"with {len(self.message_queues.get(discord_user_id, []))} messages"
        )
        
        consecutive_failures = 0
        max_consecutive_failures = 3
        
        while discord_user_id in self.message_queues and self.message_queues[discord_user_id]:
            # Check rate limit
            if discord_user_id in self.last_message_time:
                time_since_last = (
                    datetime.utcnow() - self.last_message_time[discord_user_id]
                ).total_seconds()
                
                if time_since_last < self.rate_limit_delay:
                    # Wait before sending next message
                    wait_time = self.rate_limit_delay - time_since_last
                    logger.debug(
                        f"Rate limiting: waiting {wait_time:.2f}s before sending "
                        f"to user {discord_user_id}"
                    )
                    await asyncio.sleep(wait_time)
            
            # Get next message from queue
            message_data = self.message_queues[discord_user_id].popleft()
            message = message_data["message"]
            queued_at = message_data["timestamp"]
            
            # Check message age (warn if message is old)
            message_age = (datetime.utcnow() - queued_at).total_seconds()
            if message_age > 60:
                logger.warning(
                    f"Processing old message for user {discord_user_id}: "
                    f"queued {message_age:.1f}s ago"
                )
            
            # Send the message (with automatic retry and exponential backoff)
            success = await self._send_message_direct(discord_user_id, message)
            
            if success:
                # Update last message time
                self.last_message_time[discord_user_id] = datetime.utcnow()
                consecutive_failures = 0
                logger.debug(
                    f"Successfully sent queued message to user {discord_user_id}. "
                    f"Remaining in queue: {len(self.message_queues.get(discord_user_id, []))}"
                )
            else:
                # Message failed after all retries
                consecutive_failures += 1
                logger.warning(
                    f"Failed to send queued message to user {discord_user_id} "
                    f"(consecutive failures: {consecutive_failures})"
                )
                
                # If too many consecutive failures, stop processing queue
                # This prevents wasting resources on a user who can't receive messages
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(
                        f"Stopping queue processor for user {discord_user_id} "
                        f"after {consecutive_failures} consecutive failures. "
                        f"Remaining messages: {len(self.message_queues.get(discord_user_id, []))}"
                    )
                    # Clear the queue to prevent further attempts
                    if discord_user_id in self.message_queues:
                        remaining = len(self.message_queues[discord_user_id])
                        self.message_queues[discord_user_id].clear()
                        logger.warning(
                            f"Cleared {remaining} remaining messages for user {discord_user_id}"
                        )
                    break
        
        # Clean up empty queue
        if discord_user_id in self.message_queues and not self.message_queues[discord_user_id]:
            del self.message_queues[discord_user_id]
            logger.debug(f"Cleaned up empty queue for user {discord_user_id}")
        
        # Clean up task reference
        if discord_user_id in self.queue_tasks:
            del self.queue_tasks[discord_user_id]
        
        logger.info(f"Message queue processor finished for user {discord_user_id}")
    
    async def _send_message_direct(
        self,
        discord_user_id: str,
        message: str,
        retry_count: int = 0
    ) -> bool:
        """
        Send a message directly to a Discord user with exponential backoff retry.
        
        Implements exponential backoff for transient failures:
        - Retry delays: 1s, 2s, 4s, 8s, 16s
        - Permanent failures (Forbidden, NotFound) are not retried
        - Rate limiting uses Discord's retry_after value
        
        Handles Discord API errors including:
        - User blocking the bot (Forbidden) - permanent failure
        - Missing permissions - permanent failure
        - Rate limiting (429) - retry with Discord's suggested delay
        - User not found (404) - permanent failure
        - Transient errors (500, 502, 503) - retry with exponential backoff
        
        Args:
            discord_user_id: Discord user ID as string
            message: Message content to send
            retry_count: Current retry attempt (for exponential backoff)
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        message_key = f"{discord_user_id}:{hash(message)}"
        
        try:
            user = await self.bot.fetch_user(int(discord_user_id))
            if not user:
                logger.error(f"User {discord_user_id} not found")
                return False
            
            # Format message for Discord (preserve markdown)
            formatted_message = self._format_message(message)
            
            await user.send(formatted_message)
            logger.info(
                f"Successfully sent onboarding message to {user.name} "
                f"(ID: {discord_user_id})"
            )
            
            # Clear retry count on success
            if message_key in self.retry_counts:
                del self.retry_counts[message_key]
            
            return True
        
        except discord.Forbidden as e:
            # User has blocked the bot or DMs are disabled - PERMANENT FAILURE
            logger.warning(
                f"Cannot send onboarding message to user {discord_user_id}: "
                f"User has blocked bot or disabled DMs (Forbidden: {e})"
            )
            # Clear retry count - no point retrying
            if message_key in self.retry_counts:
                del self.retry_counts[message_key]
            return False
        
        except discord.HTTPException as e:
            if e.status == 429:
                # Rate limited - use Discord's retry_after value
                retry_after = e.retry_after if hasattr(e, 'retry_after') else 60
                logger.warning(
                    f"Rate limited sending onboarding message to user {discord_user_id}. "
                    f"Retry after {retry_after} seconds (attempt {retry_count + 1}/{self.max_retries})"
                )
                
                # Check if we should retry
                if retry_count < self.max_retries:
                    await asyncio.sleep(retry_after)
                    return await self._send_message_direct(
                        discord_user_id,
                        message,
                        retry_count + 1
                    )
                else:
                    logger.error(
                        f"Max retries exceeded for rate-limited message to user {discord_user_id}"
                    )
                    if message_key in self.retry_counts:
                        del self.retry_counts[message_key]
                    return False
            
            elif e.status == 404:
                # User not found - PERMANENT FAILURE
                logger.error(f"User {discord_user_id} not found (404)")
                if message_key in self.retry_counts:
                    del self.retry_counts[message_key]
                return False
            
            elif e.status in [500, 502, 503, 504]:
                # Transient server errors - retry with exponential backoff
                if retry_count < self.max_retries:
                    delay = self.base_backoff_delay * (2 ** retry_count)
                    logger.warning(
                        f"Transient error (HTTP {e.status}) sending to user {discord_user_id}. "
                        f"Retrying in {delay}s (attempt {retry_count + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    return await self._send_message_direct(
                        discord_user_id,
                        message,
                        retry_count + 1
                    )
                else:
                    logger.error(
                        f"Max retries exceeded for transient error to user {discord_user_id}"
                    )
                    if message_key in self.retry_counts:
                        del self.retry_counts[message_key]
                    return False
            
            else:
                # Other HTTP errors - log and fail
                logger.error(
                    f"HTTP error sending onboarding message to user {discord_user_id}: "
                    f"Status {e.status}, {str(e)}"
                )
                if message_key in self.retry_counts:
                    del self.retry_counts[message_key]
                return False
        
        except discord.NotFound:
            # User doesn't exist - PERMANENT FAILURE
            logger.error(f"User {discord_user_id} does not exist (NotFound)")
            if message_key in self.retry_counts:
                del self.retry_counts[message_key]
            return False
        
        except ValueError as e:
            # Invalid user ID format - PERMANENT FAILURE
            logger.error(
                f"Invalid Discord user ID format: {discord_user_id} - {str(e)}"
            )
            if message_key in self.retry_counts:
                del self.retry_counts[message_key]
            return False
        
        except asyncio.TimeoutError:
            # Timeout - retry with exponential backoff
            if retry_count < self.max_retries:
                delay = self.base_backoff_delay * (2 ** retry_count)
                logger.warning(
                    f"Timeout sending to user {discord_user_id}. "
                    f"Retrying in {delay}s (attempt {retry_count + 1}/{self.max_retries})"
                )
                await asyncio.sleep(delay)
                return await self._send_message_direct(
                    discord_user_id,
                    message,
                    retry_count + 1
                )
            else:
                logger.error(
                    f"Max retries exceeded for timeout to user {discord_user_id}"
                )
                if message_key in self.retry_counts:
                    del self.retry_counts[message_key]
                return False
        
        except Exception as e:
            # Catch-all for unexpected errors - retry with exponential backoff
            if retry_count < self.max_retries:
                delay = self.base_backoff_delay * (2 ** retry_count)
                logger.error(
                    f"Unexpected error sending to user {discord_user_id}: {str(e)}. "
                    f"Retrying in {delay}s (attempt {retry_count + 1}/{self.max_retries})",
                    exc_info=True
                )
                await asyncio.sleep(delay)
                return await self._send_message_direct(
                    discord_user_id,
                    message,
                    retry_count + 1
                )
            else:
                logger.error(
                    f"Max retries exceeded for unexpected error to user {discord_user_id}: {str(e)}",
                    exc_info=True
                )
                if message_key in self.retry_counts:
                    del self.retry_counts[message_key]
                return False
    
    def _format_message(self, message: str) -> str:
        """
        Format a message for Discord with markdown support.
        
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
        # Could add additional formatting or sanitization here if needed
        return message
    
    def get_queue_stats(self) -> dict:
        """
        Get statistics about message queues for monitoring.
        
        Returns:
            dict: Queue statistics including:
                - total_queues: Number of active queues
                - total_messages: Total messages across all queues
                - queues: Per-user queue details
        """
        stats = {
            "total_queues": len(self.message_queues),
            "total_messages": sum(len(q) for q in self.message_queues.values()),
            "active_processors": len([t for t in self.queue_tasks.values() if not t.done()]),
            "queues": {}
        }
        
        for user_id, queue in self.message_queues.items():
            stats["queues"][user_id] = {
                "message_count": len(queue),
                "oldest_message_age": (
                    (datetime.utcnow() - queue[0]["timestamp"]).total_seconds()
                    if queue else 0
                ),
                "processor_active": (
                    user_id in self.queue_tasks and not self.queue_tasks[user_id].done()
                )
            }
        
        return stats
    
    async def handle_dm_failure(
        self,
        discord_user_id: str,
        error: Exception
    ) -> None:
        """
        Handle DM delivery failure.
        
        Logs the failure with detailed context. The backend webhook will
        detect DM failures and redirect users to web onboarding.
        
        Args:
            discord_user_id: Discord user ID as string
            error: The exception that occurred
            
        Validates: Requirements 1.3, 1.5, 7.1, 7.2
        """
        error_type = type(error).__name__
        error_message = str(error)
        
        logger.error(
            f"DM delivery failed for user {discord_user_id}",
            extra={
                'discord_user_id': discord_user_id,
                'error_type': error_type,
                'error_message': error_message,
                'is_forbidden': isinstance(error, discord.Forbidden)
            },
            exc_info=True
        )
        
        # Log specific failure reasons
        if isinstance(error, discord.Forbidden):
            logger.warning(
                f"User {discord_user_id} has DMs disabled or has blocked the bot",
                extra={
                    'discord_user_id': discord_user_id,
                    'failure_reason': 'dms_disabled_or_blocked'
                }
            )
        elif isinstance(error, discord.NotFound):
            logger.warning(
                f"User {discord_user_id} not found",
                extra={
                    'discord_user_id': discord_user_id,
                    'failure_reason': 'user_not_found'
                }
            )
        elif isinstance(error, discord.HTTPException):
            logger.warning(
                f"Discord API error for user {discord_user_id}: {error.status}",
                extra={
                    'discord_user_id': discord_user_id,
                    'failure_reason': 'discord_api_error',
                    'status_code': error.status
                }
            )
