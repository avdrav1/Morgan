import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import httpx
import asyncio
import logging
from onboarding_handler import OnboardingBotHandler
from project_plan_handler import ProjectPlanHandler

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://backend:8000")

# Bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Initialize handlers (will be set after bot is ready)
onboarding_handler: OnboardingBotHandler = None
project_plan_handler: ProjectPlanHandler = None


@bot.event
async def on_ready():
    global onboarding_handler, project_plan_handler
    logger.info(f"{bot.user} has connected to Discord!")
    logger.info(f"Bot is in {len(bot.guilds)} guilds")
    
    # Initialize onboarding handler
    onboarding_handler = OnboardingBotHandler(
        bot=bot,
        api_base_url=API_BASE_URL,
        rate_limit_delay=1.0  # 1 message per second per user
    )
    logger.info("Onboarding handler initialized")
    
    # Initialize project plan handler
    project_plan_handler = ProjectPlanHandler(
        bot=bot,
        api_base_url=API_BASE_URL
    )
    logger.info("Project plan handler initialized")


@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
    
    # Only respond to DMs
    if isinstance(message.channel, discord.DMChannel):
        # Check if user is in onboarding flow
        discord_user_id = str(message.author.id)
        
        # Try to determine if user is in onboarding
        # First, let onboarding handler try to process it
        if onboarding_handler:
            try:
                # Check if user has active onboarding session
                async with httpx.AsyncClient(timeout=5.0) as client:
                    check_response = await client.get(
                        f"{API_BASE_URL}/api/webhooks/onboarding/status/{discord_user_id}"
                    )
                    
                    if check_response.status_code == 200:
                        # User has active onboarding - route to onboarding handler
                        await onboarding_handler.on_message(message)
                        return
            except Exception as e:
                logger.debug(f"Error checking onboarding status: {e}")
                # Fall through to project plan handler
        
        # Not in onboarding - check if user has completed onboarding
        # and route to project plan handler
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Get user info to check if they have completed onboarding
                user_response = await client.get(
                    f"{API_BASE_URL}/api/users/by-discord/{discord_user_id}"
                )
                
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    user_id = user_data.get("id")
                    
                    # User exists and has completed onboarding
                    # Route to project plan handler
                    if project_plan_handler:
                        logger.info(
                            f"Routing message from {discord_user_id} to project plan handler"
                        )
                        reply = await project_plan_handler.handle_message(
                            user_id=user_id,
                            discord_id=discord_user_id,
                            message=message.content
                        )
                        await message.channel.send(reply)
                        return
                else:
                    # User not found - use fallback handler
                    logger.debug(f"User {discord_user_id} not found, using fallback")
                    await handle_dm(message)
                    return
        except Exception as e:
            logger.error(
                f"Error routing message to project plan handler: {e}",
                exc_info=True
            )
            # Fall back to regular DM handler
            await handle_dm(message)
    
    # Process commands
    await bot.process_commands(message)


async def handle_dm(message):
    """Handle direct messages from users.
    
    Routes incoming Discord messages to the backend API for processing.
    The backend will determine the appropriate response based on user state,
    active check-ins, and conversation context.
    
    Args:
        message: Discord message object
    """
    user_id = str(message.author.id)
    content = message.content
    
    logger.info(f"Received DM from {message.author.name} (ID: {user_id}): {content[:50]}...")
    
    try:
        # Send message to backend API for processing
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/discord/message",
                json={
                    "discord_user_id": user_id,
                    "message": content,
                    "author_name": message.author.name
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                reply = data.get("reply", "I received your message!")
                
                # Send reply back to user
                await message.channel.send(reply)
                logger.info(f"Sent reply to {message.author.name}")
            elif response.status_code == 404:
                # User not found - this shouldn't happen often
                logger.warning(f"User not found for Discord ID {user_id}")
                await message.channel.send(
                    "I don't have you in my system yet. Use the !start command to get started!"
                )
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                await message.channel.send(
                    "Sorry, I'm having trouble processing your message right now. Please try again in a moment."
                )
    
    except httpx.TimeoutException:
        logger.error(f"Timeout while processing message from {user_id}")
        await message.channel.send(
            "Sorry, that took too long to process. Please try again."
        )
    except httpx.RequestError as e:
        logger.error(f"Network error handling DM: {str(e)}")
        await message.channel.send(
            "Sorry, I'm having connection issues. Please try again later."
        )
    except Exception as e:
        logger.error(f"Unexpected error handling DM: {str(e)}", exc_info=True)
        await message.channel.send(
            "Sorry, something unexpected went wrong. Please try again later."
        )


@bot.command(name="start")
async def start_onboarding(ctx):
    """Start the onboarding process.
    
    Initiates the onboarding flow for new users or welcomes back existing users.
    """
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("Please DM me to get started!")
        return
    
    user_id = str(ctx.author.id)
    
    logger.info(f"User {ctx.author.name} (ID: {user_id}) initiated onboarding")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/discord/start",
                json={
                    "discord_user_id": user_id,
                    "author_name": ctx.author.name
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                await ctx.send(data.get("message", "Welcome! Let's get started."))
                logger.info(f"Onboarding started for {ctx.author.name}")
            else:
                logger.error(f"Failed to start onboarding: {response.status_code}")
                await ctx.send("Sorry, I couldn't start the onboarding process. Please try again.")
    
    except httpx.TimeoutException:
        logger.error(f"Timeout starting onboarding for {user_id}")
        await ctx.send("Sorry, that took too long. Please try again.")
    except Exception as e:
        logger.error(f"Error starting onboarding: {str(e)}", exc_info=True)
        await ctx.send("Sorry, something went wrong. Please try again later.")


@bot.command(name="status")
async def check_status(ctx):
    """Check your current projects and tasks.
    
    Retrieves and displays the user's active projects and task status.
    """
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("Please DM me to check your status!")
        return
    
    user_id = str(ctx.author.id)
    
    logger.info(f"User {ctx.author.name} (ID: {user_id}) requested status")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{API_BASE_URL}/api/discord/status/{user_id}"
            )
            
            if response.status_code == 200:
                data = response.json()
                await ctx.send(data.get("status", "No active projects."))
                logger.info(f"Status sent to {ctx.author.name}")
            elif response.status_code == 404:
                await ctx.send("I don't have you in my system yet. Use !start to get started!")
            else:
                logger.error(f"Failed to fetch status: {response.status_code}")
                await ctx.send("Couldn't fetch your status. Please try again.")
    
    except httpx.TimeoutException:
        logger.error(f"Timeout fetching status for {user_id}")
        await ctx.send("Sorry, that took too long. Please try again.")
    except Exception as e:
        logger.error(f"Error checking status: {str(e)}", exc_info=True)
        await ctx.send("Sorry, something went wrong. Please try again later.")


async def send_message_to_user(discord_user_id: str, message: str):
    """Send a proactive message to a user.
    
    Handles Discord-specific errors including:
    - User blocking the bot (Forbidden)
    - Missing permissions
    - Rate limiting
    - User not found
    
    Args:
        discord_user_id: Discord user ID as string
        message: Message content to send
        
    Returns:
        bool: True if message sent successfully, False otherwise
    """
    try:
        user = await bot.fetch_user(int(discord_user_id))
        if not user:
            logger.error(f"User {discord_user_id} not found")
            return False
        
        await user.send(message)
        logger.info(f"Successfully sent message to {user.name} (ID: {discord_user_id})")
        return True
    
    except discord.Forbidden as e:
        # User has blocked the bot or DMs are disabled
        logger.warning(
            f"Cannot send message to user {discord_user_id}: "
            f"User has blocked bot or disabled DMs (Forbidden: {e})"
        )
        return False
    
    except discord.HTTPException as e:
        if e.status == 429:
            # Rate limited
            retry_after = e.retry_after if hasattr(e, 'retry_after') else 60
            logger.error(
                f"Rate limited when sending to user {discord_user_id}. "
                f"Retry after {retry_after} seconds"
            )
            # Could implement retry logic here, but for now just fail
            return False
        elif e.status == 404:
            # User not found
            logger.error(f"User {discord_user_id} not found (404)")
            return False
        else:
            # Other HTTP errors
            logger.error(
                f"HTTP error sending message to user {discord_user_id}: "
                f"Status {e.status}, {str(e)}"
            )
            return False
    
    except discord.NotFound:
        # User doesn't exist
        logger.error(f"User {discord_user_id} does not exist (NotFound)")
        return False
    
    except ValueError as e:
        # Invalid user ID format
        logger.error(f"Invalid Discord user ID format: {discord_user_id} - {str(e)}")
        return False
    
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(
            f"Unexpected error sending message to user {discord_user_id}: {str(e)}",
            exc_info=True
        )
        return False


# Simple HTTP server for receiving message requests from backend
from aiohttp import web

async def send_dm_endpoint(request):
    """Endpoint for backend to send DMs through Discord bot.
    
    This endpoint is specifically for onboarding and other DM flows.
    Returns success=True/False to indicate whether DM was delivered.
    
    Handles message delivery with detailed error reporting for:
    - Missing parameters
    - User blocking bot
    - DMs disabled
    - Rate limiting
    - Permission issues
    
    Returns:
        JSON response with success status and reason for failure
    """
    try:
        data = await request.json()
        discord_user_id = data.get("discord_user_id")
        message = data.get("message")
        
        if not discord_user_id or not message:
            logger.warning("Missing discord_user_id or message in request")
            return web.json_response(
                {
                    "success": False,
                    "reason": "missing_parameters",
                    "error": "Both discord_user_id and message are required"
                },
                status=400
            )
        
        logger.info(f"Attempting to send DM to Discord user {discord_user_id}")
        
        try:
            user = await bot.fetch_user(int(discord_user_id))
            if not user:
                logger.error(f"User {discord_user_id} not found")
                return web.json_response({
                    "success": False,
                    "reason": "user_not_found",
                    "discord_user_id": discord_user_id
                })
            
            await user.send(message)
            logger.info(f"Successfully sent DM to {user.name} (ID: {discord_user_id})")
            
            return web.json_response({
                "success": True,
                "discord_user_id": discord_user_id
            })
        
        except discord.Forbidden as e:
            # User has blocked the bot or DMs are disabled
            logger.warning(
                f"Cannot send DM to user {discord_user_id}: "
                f"User has blocked bot or disabled DMs (Forbidden: {e})"
            )
            return web.json_response({
                "success": False,
                "reason": "dms_disabled_or_blocked",
                "discord_user_id": discord_user_id,
                "error": "User has DMs disabled or has blocked the bot"
            })
        
        except discord.HTTPException as e:
            if e.status == 429:
                # Rate limited
                retry_after = e.retry_after if hasattr(e, 'retry_after') else 60
                logger.error(
                    f"Rate limited when sending to user {discord_user_id}. "
                    f"Retry after {retry_after} seconds"
                )
                return web.json_response({
                    "success": False,
                    "reason": "rate_limited",
                    "discord_user_id": discord_user_id,
                    "retry_after": retry_after
                })
            elif e.status == 404:
                # User not found
                logger.error(f"User {discord_user_id} not found (404)")
                return web.json_response({
                    "success": False,
                    "reason": "user_not_found",
                    "discord_user_id": discord_user_id
                })
            else:
                # Other HTTP errors
                logger.error(
                    f"HTTP error sending DM to user {discord_user_id}: "
                    f"Status {e.status}, {str(e)}"
                )
                return web.json_response({
                    "success": False,
                    "reason": "discord_api_error",
                    "discord_user_id": discord_user_id,
                    "status_code": e.status
                })
        
        except discord.NotFound:
            # User doesn't exist
            logger.error(f"User {discord_user_id} does not exist (NotFound)")
            return web.json_response({
                "success": False,
                "reason": "user_not_found",
                "discord_user_id": discord_user_id
            })
        
        except ValueError as e:
            # Invalid user ID format
            logger.error(f"Invalid Discord user ID format: {discord_user_id} - {str(e)}")
            return web.json_response({
                "success": False,
                "reason": "invalid_user_id",
                "discord_user_id": discord_user_id,
                "error": str(e)
            })
    
    except ValueError as e:
        logger.error(f"Invalid request data: {str(e)}")
        return web.json_response(
            {
                "success": False,
                "reason": "invalid_request",
                "error": str(e)
            },
            status=400
        )
    
    except Exception as e:
        logger.error(f"Unexpected error in send_dm endpoint: {str(e)}", exc_info=True)
        return web.json_response(
            {
                "success": False,
                "reason": "internal_error",
                "error": str(e)
            },
            status=500
        )


async def send_message_endpoint(request):
    """Endpoint for backend to send messages through Discord bot.
    
    Handles message delivery with detailed error reporting for:
    - Missing parameters
    - User blocking bot
    - Rate limiting
    - Permission issues
    
    Returns appropriate HTTP status codes and error details.
    """
    try:
        data = await request.json()
        discord_user_id = data.get("discord_user_id")
        message = data.get("message")
        
        if not discord_user_id or not message:
            logger.warning("Missing discord_user_id or message in request")
            return web.json_response(
                {
                    "error": "Missing required fields",
                    "details": "Both discord_user_id and message are required"
                },
                status=400
            )
        
        logger.info(f"Attempting to send message to Discord user {discord_user_id}")
        success = await send_message_to_user(discord_user_id, message)
        
        if success:
            return web.json_response({
                "status": "sent",
                "discord_user_id": discord_user_id
            })
        else:
            # Message sending failed - could be blocked, rate limited, etc.
            # The specific error is already logged in send_message_to_user
            return web.json_response(
                {
                    "error": "Failed to send message",
                    "details": "User may have blocked bot, disabled DMs, or bot lacks permissions",
                    "discord_user_id": discord_user_id
                },
                status=500
            )
    
    except ValueError as e:
        logger.error(f"Invalid request data: {str(e)}")
        return web.json_response(
            {
                "error": "Invalid request data",
                "details": str(e)
            },
            status=400
        )
    
    except Exception as e:
        logger.error(f"Unexpected error in send_message endpoint: {str(e)}", exc_info=True)
        return web.json_response(
            {
                "error": "Internal server error",
                "details": str(e)
            },
            status=500
        )


async def start_http_server():
    """Start HTTP server for backend communication."""
    app = web.Application()
    app.router.add_post("/send_message", send_message_endpoint)
    app.router.add_post("/send-dm", send_dm_endpoint)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8001)
    await site.start()
    logger.info("HTTP server started on port 8001")


async def main():
    """Main entry point."""
    # Start HTTP server in background
    asyncio.create_task(start_http_server())
    
    # Start Discord bot
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
