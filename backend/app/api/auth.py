from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from urllib.parse import urlencode
import secrets
import json
import httpx

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user
)
from app.core.config import settings
from app.core.logging_config import get_logger
from app.models import User
from app.schemas.user import UserCreate, UserResponse, Token
from app.services.discord_oauth_service import discord_oauth_service

logger = get_logger(__name__)

router = APIRouter()

# In-memory state storage (in production, use Redis)
oauth_states = {}


async def trigger_onboarding_webhook(user_id: str, discord_id: str, email: str):
    """
    Trigger the onboarding webhook for a new user.
    
    Args:
        user_id: UUID of the user
        discord_id: Discord user ID
        email: User's email address
        
    Returns:
        dict or None: Webhook response data if successful, None if failed
    """
    webhook_url = f"http://localhost:8000/api/webhooks/onboarding/start"
    webhook_secret = settings.WEBHOOK_SECRET if settings.WEBHOOK_SECRET else settings.JWT_SECRET_KEY
    
    payload = {
        "user_id": user_id,
        "discord_id": discord_id,
        "email": email
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Token": webhook_secret
    }
    
    try:
        logger.info(
            "Triggering onboarding webhook",
            extra={'extra_fields': {
                'user_id': user_id,
                'discord_id': discord_id
            }}
        )
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            
            result = response.json()
            
            logger.info(
                "Onboarding webhook triggered successfully",
                extra={'extra_fields': {
                    'user_id': user_id,
                    'discord_id': discord_id,
                    'status_code': response.status_code,
                    'dm_sent': result.get('dm_sent', False)
                }}
            )
            return result
            
    except httpx.TimeoutException as e:
        logger.error(
            f"Onboarding webhook timeout: {e}",
            extra={'extra_fields': {
                'user_id': user_id,
                'discord_id': discord_id,
                'error': 'timeout'
            }}
        )
        return None
        
    except httpx.HTTPStatusError as e:
        logger.error(
            f"Onboarding webhook HTTP error: {e.response.status_code} - {e.response.text}",
            extra={'extra_fields': {
                'user_id': user_id,
                'discord_id': discord_id,
                'status_code': e.response.status_code,
                'error': str(e)
            }}
        )
        return None
        
    except Exception as e:
        logger.error(
            f"Onboarding webhook failed: {e}",
            extra={'extra_fields': {
                'user_id': user_id,
                'discord_id': discord_id,
                'error': str(e)
            }},
            exc_info=True
        )
        return None


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password)
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login and get access token."""
    
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return current_user


@router.get("/discord/login")
async def discord_login_initiate():
    """
    Initiate Discord OAuth flow.
    
    Generates a state token and redirects to Discord's authorization URL.
    """
    logger.info("Initiating Discord OAuth flow")
    
    if not settings.DISCORD_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="Discord OAuth not configured"
        )
    
    # Generate state token
    state = secrets.token_urlsafe(32)
    
    # Store state with expiration (10 minutes)
    oauth_states[state] = {
        "created_at": datetime.utcnow(),
        "action": "login"
    }
    
    # Clean up old states (older than 10 minutes)
    cutoff = datetime.utcnow() - timedelta(minutes=10)
    oauth_states_to_delete = [
        s for s, data in oauth_states.items()
        if data["created_at"] < cutoff
    ]
    for s in oauth_states_to_delete:
        del oauth_states[s]
    
    # Build Discord OAuth URL
    params = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "redirect_uri": settings.DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify email",
        "state": state,
    }
    
    discord_url = f"https://discord.com/api/oauth2/authorize?{urlencode(params)}"
    
    logger.info(
        "Redirecting to Discord OAuth",
        extra={'extra_fields': {'state': state}}
    )
    
    return RedirectResponse(discord_url)


@router.get("/discord/callback")
async def discord_oauth_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """
    Handle Discord OAuth callback.
    
    Validates state, exchanges code for tokens, fetches user info,
    creates/updates user account, and returns JWT token.
    """
    logger.info(
        "Received Discord OAuth callback",
        extra={'extra_fields': {'state': state}}
    )
    
    # Validate state
    stored_state = oauth_states.get(state)
    if not stored_state:
        logger.warning(f"Invalid or expired state parameter: {state}")
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired state parameter"
        )
    
    # Delete used state
    del oauth_states[state]
    
    try:
        # Exchange code for tokens
        token_data = await discord_oauth_service.exchange_code(code)
        
        # Fetch user info from Discord
        discord_user = await discord_oauth_service.get_user_info(
            token_data["access_token"]
        )
        
        # Create or update user account
        user = await discord_oauth_service.create_or_update_user(
            db=db,
            discord_user=discord_user,
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_at=datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        )
        
        # Trigger onboarding webhook for new users
        webhook_result = None
        dm_onboarding_available = False
        
        if user.is_new:
            logger.info(
                "New user detected, triggering onboarding webhook",
                extra={'extra_fields': {
                    'user_id': str(user.id),
                    'discord_id': user.discord_user_id
                }}
            )
            
            webhook_result = await trigger_onboarding_webhook(
                user_id=str(user.id),
                discord_id=user.discord_user_id,
                email=user.email
            )
            
            # Check if DM onboarding is available
            if webhook_result and isinstance(webhook_result, dict):
                dm_onboarding_available = webhook_result.get('dm_sent', False)
                
                if not dm_onboarding_available:
                    logger.warning(
                        "DM delivery failed, redirecting to web onboarding",
                        extra={'extra_fields': {
                            'user_id': str(user.id),
                            'discord_id': user.discord_user_id,
                            'reason': 'dm_delivery_failed'
                        }}
                    )
            elif not webhook_result:
                logger.warning(
                    "Failed to trigger onboarding webhook, user will use web onboarding",
                    extra={'extra_fields': {
                        'user_id': str(user.id),
                        'discord_id': user.discord_user_id
                    }}
                )
        
        # Generate JWT token
        jwt_token = create_access_token(data={"sub": user.email})
        
        # Redirect to frontend with token
        # If DM onboarding failed, redirect directly to web onboarding page
        if user.is_new and not dm_onboarding_available:
            frontend_url = f"{settings.FRONTEND_URL}/onboarding?token={jwt_token}&method=web&reason=dm_failed"
            logger.info(
                "Redirecting new user to web onboarding due to DM failure",
                extra={'extra_fields': {
                    'user_id': str(user.id),
                    'redirect_to': 'web_onboarding'
                }}
            )
        else:
            # Include dm_onboarding flag to help frontend decide onboarding flow
            frontend_url = f"{settings.FRONTEND_URL}/auth/callback?token={jwt_token}&new_user={str(user.is_new).lower()}&dm_onboarding={str(dm_onboarding_available).lower()}"
            logger.info(
                "Discord OAuth successful, redirecting to frontend",
                extra={'extra_fields': {
                    'user_id': str(user.id),
                    'is_new': user.is_new,
                    'dm_onboarding': dm_onboarding_available
                }}
            )
        
        return RedirectResponse(frontend_url)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Discord OAuth callback failed: {e}",
            extra={'extra_fields': {'error': str(e)}},
            exc_info=True
        )
        # Redirect to frontend with error
        error_url = f"{settings.FRONTEND_URL}/login?error=oauth_failed"
        return RedirectResponse(error_url)


@router.post("/discord/link")
async def link_discord_account(
    current_user: User = Depends(get_current_user)
):
    """
    Initiate Discord OAuth flow for linking to existing account.
    """
    logger.info(
        "Initiating Discord account linking",
        extra={'extra_fields': {'user_id': str(current_user.id)}}
    )
    
    if not settings.DISCORD_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="Discord OAuth not configured"
        )
    
    if current_user.discord_user_id:
        raise HTTPException(
            status_code=409,
            detail="Discord account already linked"
        )
    
    # Generate state token
    state = secrets.token_urlsafe(32)
    
    # Store state with user_id for linking
    oauth_states[state] = {
        "created_at": datetime.utcnow(),
        "action": "link",
        "user_id": str(current_user.id)
    }
    
    # Build Discord OAuth URL
    params = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "redirect_uri": settings.DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify email",
        "state": state,
    }
    
    discord_url = f"https://discord.com/api/oauth2/authorize?{urlencode(params)}"
    
    return {"authorization_url": discord_url}


@router.post("/discord/disconnect")
async def disconnect_discord_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disconnect Discord account from user.
    """
    logger.info(
        "Disconnecting Discord account",
        extra={'extra_fields': {'user_id': str(current_user.id)}}
    )
    
    if not current_user.discord_user_id:
        raise HTTPException(
            status_code=400,
            detail="No Discord account linked"
        )
    
    # Revoke tokens if they exist
    if current_user.discord_access_token:
        try:
            from app.core.encryption import decrypt_token
            access_token = decrypt_token(current_user.discord_access_token)
            await discord_oauth_service.revoke_token(access_token)
        except Exception as e:
            logger.warning(f"Failed to revoke access token: {e}")
    
    if current_user.discord_refresh_token:
        try:
            from app.core.encryption import decrypt_token
            refresh_token = decrypt_token(current_user.discord_refresh_token)
            await discord_oauth_service.revoke_token(refresh_token)
        except Exception as e:
            logger.warning(f"Failed to revoke refresh token: {e}")
    
    # Clear Discord fields
    current_user.discord_user_id = None
    current_user.discord_username = None
    current_user.discord_discriminator = None
    current_user.discord_avatar = None
    current_user.discord_access_token = None
    current_user.discord_refresh_token = None
    current_user.discord_token_expires_at = None
    
    db.commit()
    
    logger.info(
        "Discord account disconnected successfully",
        extra={'extra_fields': {'user_id': str(current_user.id)}}
    )
    
    return {"message": "Discord account disconnected successfully"}
