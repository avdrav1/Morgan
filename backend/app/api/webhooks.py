"""
Webhook endpoints for external integrations.

This module provides webhook endpoints for triggering internal processes
from external events, such as starting onboarding after OAuth completion.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from datetime import datetime
import httpx

from app.core.database import get_db
from app.core.config import settings
from app.core.logging_config import get_logger, set_correlation_id
from app.core.metrics import metrics
from app.schemas.webhook import OnboardingWebhookPayload
from app.services.onboarding_service import OnboardingService
from app.models.user import User

logger = get_logger(__name__)

router = APIRouter()


def verify_webhook_token(x_webhook_token: Optional[str] = Header(None)) -> bool:
    """
    Verify the webhook authentication token.
    
    For security, webhooks should include a secret token in the X-Webhook-Token header.
    In production, this should be a strong secret stored in environment variables.
    
    Args:
        x_webhook_token: The webhook token from the request header
        
    Returns:
        bool: True if token is valid
        
    Raises:
        HTTPException: If token is missing or invalid
    """
    # Get webhook secret from settings (defaults to JWT secret if not set)
    webhook_secret = settings.WEBHOOK_SECRET if settings.WEBHOOK_SECRET else settings.JWT_SECRET_KEY
    
    if not x_webhook_token:
        logger.warning("Webhook request missing authentication token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if x_webhook_token != webhook_secret:
        logger.warning(
            f"Webhook request with invalid authentication token. "
            f"Expected length: {len(webhook_secret)}, Got length: {len(x_webhook_token)}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return True


@router.post(
    "/onboarding/start",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start onboarding for a new user",
    description="Webhook endpoint to trigger Discord DM onboarding flow for a new user"
)
async def start_onboarding_webhook(
    payload: OnboardingWebhookPayload,
    db: Session = Depends(get_db),
    authenticated: bool = Depends(verify_webhook_token)
):
    """
    Start onboarding webhook endpoint.
    
    This endpoint is called when a new user completes Discord OAuth to trigger
    the Discord DM onboarding flow. It creates an onboarding session and
    initiates the conversation.
    
    Attempts to send a welcome DM to the user. If DM delivery fails (user has
    DMs disabled or blocked the bot), returns a response indicating web onboarding
    should be used instead.
    
    Authentication:
        Requires X-Webhook-Token header with valid webhook secret
    
    Args:
        payload: Webhook payload containing user_id, discord_id, and email
        db: Database session
        authenticated: Authentication verification result
        
    Returns:
        dict: Success message with session_id and dm_sent status
        
    Raises:
        HTTPException: If user not found or onboarding fails
        
    Validates: Requirements 1.1, 1.3, 7.1, 7.2
    """
    # Set correlation ID for this webhook request
    correlation_id = set_correlation_id()
    
    logger.info(
        "Received onboarding webhook request",
        extra={'extra_fields': {
            'event': 'webhook_onboarding_start_received',
            'user_id': str(payload.user_id),
            'discord_id': payload.discord_id,
            'correlation_id': correlation_id
        }}
    )
    
    metrics.increment('webhook_requests', {'endpoint': 'onboarding_start'})
    
    # Verify user exists
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        logger.error(
            f"User not found for onboarding webhook: {payload.user_id}",
            extra={'extra_fields': {'user_id': str(payload.user_id)}}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {payload.user_id}"
        )
    
    # Verify user has Discord linked
    if not user.discord_user_id:
        logger.warning(
            f"User {payload.user_id} does not have Discord linked",
            extra={'extra_fields': {'user_id': str(payload.user_id)}}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have Discord account linked"
        )
    
    # Verify Discord IDs match
    if user.discord_user_id != payload.discord_id:
        logger.error(
            f"Discord ID mismatch for user {payload.user_id}",
            extra={'extra_fields': {
                'user_id': str(payload.user_id),
                'expected_discord_id': user.discord_user_id,
                'provided_discord_id': payload.discord_id
            }}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discord ID mismatch"
        )
    
    try:
        # Try to send welcome DM via Discord bot
        dm_sent = await _send_welcome_dm(payload.discord_id)
        
        if not dm_sent:
            # DM delivery failed - log and return failure status
            logger.warning(
                f"DM delivery failed for user {payload.user_id}, discord_id {payload.discord_id}",
                extra={'extra_fields': {
                    'user_id': str(payload.user_id),
                    'discord_id': payload.discord_id,
                    'dm_sent': False
                }}
            )
            
            # Don't create onboarding session if DM failed
            return {
                "message": "DM delivery failed, user should use web onboarding",
                "dm_sent": False,
                "user_id": str(payload.user_id),
                "discord_id": payload.discord_id,
                "use_web_onboarding": True
            }
        
        # DM sent successfully - create onboarding session
        onboarding_service = OnboardingService(db)
        session = await onboarding_service.start_onboarding(
            user_id=payload.user_id,
            discord_id=payload.discord_id,
            dm_enabled=True
        )
        
        if not session:
            # This shouldn't happen if dm_enabled=True, but handle it
            logger.error(
                f"Failed to create onboarding session despite DM success for user {payload.user_id}",
                extra={'extra_fields': {
                    'user_id': str(payload.user_id),
                    'discord_id': payload.discord_id
                }}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create onboarding session"
            )
        
        logger.info(
            "Onboarding session created successfully",
            extra={'extra_fields': {
                'user_id': str(payload.user_id),
                'session_id': str(session.id),
                'discord_id': payload.discord_id,
                'dm_sent': True
            }}
        )
        
        return {
            "message": "Onboarding session created successfully",
            "session_id": str(session.id),
            "user_id": str(payload.user_id),
            "discord_id": payload.discord_id,
            "current_state": session.current_state.value,
            "dm_sent": True,
            "use_web_onboarding": False
        }
        
    except Exception as e:
        logger.error(
            f"Failed to start onboarding for user {payload.user_id}: {e}",
            extra={'extra_fields': {
                'user_id': str(payload.user_id),
                'error': str(e)
            }},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start onboarding: {str(e)}"
        )


async def _send_welcome_dm(discord_user_id: str) -> bool:
    """
    Attempt to send a welcome DM to a Discord user.
    
    This function calls the Discord bot API to send the welcome message.
    If the DM fails (user has DMs disabled or blocked the bot), returns False.
    
    Args:
        discord_user_id: Discord user ID
        
    Returns:
        bool: True if DM was sent successfully, False if delivery failed
        
    Validates: Requirements 1.3, 7.1, 7.2
    """
    # Get Discord bot API URL from settings
    discord_bot_url = settings.DISCORD_BOT_API_URL if hasattr(settings, 'DISCORD_BOT_API_URL') else "http://discord-bot:8001"
    
    welcome_message = (
        "👋 **Welcome to your Accountability Assistant!**\n\n"
        "I'm here to help you stay on track with your goals. "
        "Let's get started by setting up your first project.\n\n"
        "**What project would you like to work on?**\n"
        "Just tell me the name of your project, and we'll take it from there!"
    )
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{discord_bot_url}/send-dm",
                json={
                    "discord_user_id": discord_user_id,
                    "message": welcome_message
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                dm_sent = data.get("success", False)
                
                if dm_sent:
                    logger.info(
                        f"Welcome DM sent successfully to Discord user {discord_user_id}",
                        extra={'extra_fields': {
                            'discord_user_id': discord_user_id,
                            'dm_sent': True
                        }}
                    )
                else:
                    # Bot returned success=False (DMs disabled or blocked)
                    logger.warning(
                        f"DM delivery failed for Discord user {discord_user_id}: {data.get('reason', 'unknown')}",
                        extra={'extra_fields': {
                            'discord_user_id': discord_user_id,
                            'dm_sent': False,
                            'reason': data.get('reason', 'unknown')
                        }}
                    )
                
                return dm_sent
            else:
                # Bot API returned error
                logger.error(
                    f"Discord bot API error: {response.status_code} - {response.text}",
                    extra={'extra_fields': {
                        'discord_user_id': discord_user_id,
                        'status_code': response.status_code
                    }}
                )
                return False
                
    except httpx.TimeoutException:
        logger.error(
            f"Timeout sending welcome DM to Discord user {discord_user_id}",
            extra={'extra_fields': {
                'discord_user_id': discord_user_id,
                'error': 'timeout'
            }}
        )
        return False
        
    except httpx.RequestError as e:
        logger.error(
            f"Network error sending welcome DM: {str(e)}",
            extra={'extra_fields': {
                'discord_user_id': discord_user_id,
                'error': str(e)
            }}
        )
        return False
        
    except Exception as e:
        logger.error(
            f"Unexpected error sending welcome DM: {str(e)}",
            extra={'extra_fields': {
                'discord_user_id': discord_user_id,
                'error': str(e)
            }},
            exc_info=True
        )
        return False


@router.post(
    "/onboarding/message",
    status_code=status.HTTP_200_OK,
    summary="Process onboarding message",
    description="Handle incoming Discord messages during onboarding flow"
)
async def process_onboarding_message(
    payload: dict,
    db: Session = Depends(get_db)
):
    """
    Process an incoming message during onboarding.
    
    Routes the message to the onboarding service for processing and
    returns the appropriate response to send back to the user.
    
    Detects returning users with incomplete onboarding and resumes
    from their last completed state.
    
    Enhanced with state-based logic to:
    - Parse user input based on current onboarding state
    - Extract relevant data (project name, goal, deadline, tone, frequency)
    - Validate extracted data using input validators
    - Update session with extracted data
    - Determine next state based on current state and input
    - Transition to next state
    - Generate LLM response for next question
    - Handle validation errors with clarifying questions
    
    Args:
        payload: Message payload with discord_user_id, message, author_name
        db: Database session
        
    Returns:
        dict: Response with reply message
        
    Raises:
        HTTPException: If session not found or processing fails
        
    Validates: Requirements 2.1, 3.1, 3.2, 6.3, 6.4, 8.1, 8.2
    """
    discord_user_id = payload.get("discord_user_id")
    message = payload.get("message")
    author_name = payload.get("author_name")
    
    if not discord_user_id or not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields: discord_user_id and message"
        )
    
    logger.info(
        f"Processing onboarding message from Discord user {discord_user_id}",
        extra={'extra_fields': {
            'discord_user_id': discord_user_id,
            'message_preview': message[:50]
        }}
    )
    
    # Find user by Discord ID
    user = db.query(User).filter(User.discord_user_id == discord_user_id).first()
    if not user:
        logger.warning(f"User not found for Discord ID {discord_user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    try:
        onboarding_service = OnboardingService(db)
        
        # Get active session (this automatically handles resumption)
        session = await onboarding_service.get_session(user.id)
        if not session:
            logger.info(f"No active onboarding session for user {user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active onboarding session"
            )
        
        # Check if this is a command
        if onboarding_service.is_command(message):
            logger.info(
                f"Processing command from user {user.id}: {message}",
                extra={'extra_fields': {
                    'user_id': str(user.id),
                    'command': message.strip().lower()
                }}
            )
            
            # Handle the command
            response = await onboarding_service.handle_command(user.id, message)
            
            # Get updated session state
            updated_session = await onboarding_service.get_session(user.id)
            current_state = updated_session.current_state.value if updated_session else session.current_state.value
            
            return {
                "reply": response,
                "current_state": current_state,
                "is_command": True
            }
        
        # Check if this is a returning user (session was inactive)
        from datetime import timedelta
        time_since_activity = (datetime.utcnow() - session.last_activity_at).total_seconds() / 3600
        is_returning = time_since_activity > 1  # More than 1 hour since last activity
        
        if is_returning:
            logger.info(
                f"Resuming onboarding for returning user {user.id}",
                extra={'extra_fields': {
                    'user_id': str(user.id),
                    'session_id': str(session.id),
                    'current_state': session.current_state.value,
                    'hours_inactive': round(time_since_activity, 2)
                }}
            )
        
        # Process the message with state-based logic
        result = await onboarding_service.process_message_with_state_logic(
            user_id=user.id,
            message=message
        )
        
        logger.info(
            f"Generated onboarding response for user {user.id}",
            extra={'extra_fields': {
                'user_id': str(user.id),
                'session_state': result.get('current_state'),
                'is_resumption': is_returning,
                'validation_passed': result.get('validation_passed', True)
            }}
        )
        
        return {
            "reply": result['reply'],
            "current_state": result['current_state'],
            "is_resumption": is_returning,
            "is_command": False,
            "validation_passed": result.get('validation_passed', True)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error processing onboarding message: {e}",
            extra={'extra_fields': {
                'discord_user_id': discord_user_id,
                'error': str(e)
            }},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process message: {str(e)}"
        )


@router.get(
    "/onboarding/status/{discord_user_id}",
    status_code=status.HTTP_200_OK,
    summary="Check onboarding status",
    description="Check if a user has an active onboarding session"
)
async def check_onboarding_status(
    discord_user_id: str,
    db: Session = Depends(get_db)
):
    """
    Check if a user has an active onboarding session.
    
    Used by the Discord bot to determine whether to route messages
    to the onboarding handler or regular message handler.
    
    Args:
        discord_user_id: Discord user ID
        db: Database session
        
    Returns:
        dict: Status information
        
    Raises:
        HTTPException: If user not found
    """
    # Find user by Discord ID
    user = db.query(User).filter(User.discord_user_id == discord_user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    onboarding_service = OnboardingService(db)
    session = await onboarding_service.get_session(user.id)
    
    if session:
        return {
            "has_active_session": True,
            "current_state": session.current_state.value,
            "session_id": str(session.id)
        }
    else:
        return {
            "has_active_session": False
        }


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Webhook health check",
    description="Health check endpoint for webhook service"
)
async def webhook_health_check():
    """
    Health check endpoint for webhooks.
    
    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "service": "webhooks"
    }
