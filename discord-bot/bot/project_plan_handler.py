"""
Discord bot handler for project plan management.

This module handles Discord DM interactions for project plan management,
routing messages to the backend services and managing conversation flow.
"""

import discord
import asyncio
import logging
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)


class ProjectPlanHandler:
    """
    Handler for Discord DM project plan interactions.
    
    Routes incoming DMs to the project plan service, classifies intent,
    and manages conversational flow for viewing and editing project plans.
    
    Validates: Requirements 1.1, 2.1, 3.1, 6.1
    """
    
    def __init__(
        self,
        bot: discord.Client,
        api_base_url: str
    ):
        """
        Initialize the project plan handler.
        
        Args:
            bot: Discord bot client instance
            api_base_url: Base URL for backend API
        """
        self.bot = bot
        self.api_base_url = api_base_url
    
    async def handle_message(
        self,
        user_id: str,
        discord_id: str,
        message: str
    ) -> str:
        """
        Process a message about project plans.
        
        Routes the message to the backend API which will:
        1. Classify the user's intent
        2. Execute the appropriate action
        3. Format the response for Discord
        
        Args:
            user_id: The user's UUID
            discord_id: The user's Discord ID
            message: The message content
            
        Returns:
            The response message to send back
            
        Validates: Requirements 1.1, 2.1, 3.1, 6.1
        """
        logger.info(
            f"Project plan handler received message from user {discord_id}: {message[:50]}..."
        )
        
        try:
            # Send message to backend project plan service
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_base_url}/api/discord/project-plan/message",
                    json={
                        "user_id": user_id,
                        "discord_user_id": discord_id,
                        "message": message
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    reply = data.get("reply", "I received your message!")
                    
                    logger.info(f"Project plan response generated for user {discord_id}")
                    return reply
                
                elif response.status_code == 404:
                    # No project found
                    logger.warning(f"No project found for user {discord_id}")
                    return (
                        "I couldn't find any projects for you. "
                        "Have you completed onboarding yet? "
                        "Use the !start command to get started!"
                    )
                
                elif response.status_code == 400:
                    # Invalid input or validation error
                    data = response.json()
                    error_message = data.get("message", "I didn't understand that.")
                    logger.warning(
                        f"Validation error for user {discord_id}: {error_message}"
                    )
                    return error_message
                
                else:
                    logger.error(
                        f"Project plan API error: {response.status_code} - {response.text}"
                    )
                    return (
                        "Sorry, I'm having trouble processing your message right now. "
                        "Please try again in a moment."
                    )
        
        except httpx.TimeoutException:
            logger.error(f"Timeout processing project plan message from {discord_id}")
            return "Sorry, that took too long to process. Please try again."
        
        except httpx.RequestError as e:
            logger.error(f"Network error in project plan handler: {str(e)}")
            return "Sorry, I'm having connection issues. Please try again later."
        
        except Exception as e:
            logger.error(
                f"Unexpected error in project plan handler: {str(e)}",
                exc_info=True
            )
            return "Sorry, something unexpected went wrong. Please try again later."
