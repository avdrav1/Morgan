"""
Discord OAuth 2.0 service for authentication and token management.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import httpx
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.config import settings
from app.core.encryption import encrypt_token, decrypt_token
from app.core.logging_config import get_logger
from app.models.user import User

logger = get_logger(__name__)


class DiscordOAuthService:
    """Service for handling Discord OAuth operations."""
    
    def __init__(self):
        self.client_id = settings.DISCORD_CLIENT_ID
        self.client_secret = settings.DISCORD_CLIENT_SECRET
        self.redirect_uri = settings.DISCORD_REDIRECT_URI
        self.token_url = "https://discord.com/api/oauth2/token"
        self.revoke_url = "https://discord.com/api/oauth2/token/revoke"
        self.api_base = "https://discord.com/api/v10"
    
    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            code: Authorization code from Discord
            
        Returns:
            Dict with access_token, refresh_token, expires_in, token_type
        """
        logger.info(
            "Exchanging authorization code for tokens",
            extra={'extra_fields': {'operation': 'exchange_code'}}
        )
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                response.raise_for_status()
                result = response.json()
                
                logger.info(
                    "Successfully exchanged code for tokens",
                    extra={'extra_fields': {'operation': 'exchange_code', 'success': True}}
                )
                
                return result
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to exchange code: {e.response.text}",
                extra={'extra_fields': {'operation': 'exchange_code', 'error': str(e)}},
                exc_info=True
            )
            raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
        except Exception as e:
            logger.error(
                f"Unexpected error exchanging code: {e}",
                extra={'extra_fields': {'operation': 'exchange_code', 'error': str(e)}},
                exc_info=True
            )
            raise HTTPException(status_code=500, detail="OAuth exchange failed")
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an expired access token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            Dict with new access_token, refresh_token, expires_in
        """
        logger.info(
            "Refreshing access token",
            extra={'extra_fields': {'operation': 'refresh_access_token'}}
        )
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                response.raise_for_status()
                result = response.json()
                
                logger.info(
                    "Successfully refreshed access token",
                    extra={'extra_fields': {'operation': 'refresh_access_token', 'success': True}}
                )
                
                return result
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to refresh token: {e.response.text}",
                extra={'extra_fields': {'operation': 'refresh_access_token', 'error': str(e)}},
                exc_info=True
            )
            raise HTTPException(status_code=401, detail="Failed to refresh token")
        except Exception as e:
            logger.error(
                f"Unexpected error refreshing token: {e}",
                extra={'extra_fields': {'operation': 'refresh_access_token', 'error': str(e)}},
                exc_info=True
            )
            raise HTTPException(status_code=500, detail="Token refresh failed")
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Fetch user information from Discord API.
        
        Args:
            access_token: Valid Discord access token
            
        Returns:
            Dict with id, username, discriminator, email, avatar, etc.
        """
        logger.info(
            "Fetching user info from Discord",
            extra={'extra_fields': {'operation': 'get_user_info'}}
        )
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/users/@me",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                response.raise_for_status()
                result = response.json()
                
                logger.info(
                    "Successfully fetched user info",
                    extra={'extra_fields': {
                        'operation': 'get_user_info',
                        'discord_id': result.get('id'),
                        'username': result.get('username')
                    }}
                )
                
                return result
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to fetch user info: {e.response.text}",
                extra={'extra_fields': {'operation': 'get_user_info', 'error': str(e)}},
                exc_info=True
            )
            raise HTTPException(status_code=401, detail="Failed to fetch user information")
        except Exception as e:
            logger.error(
                f"Unexpected error fetching user info: {e}",
                extra={'extra_fields': {'operation': 'get_user_info', 'error': str(e)}},
                exc_info=True
            )
            raise HTTPException(status_code=500, detail="Failed to fetch user information")
    
    async def revoke_token(self, token: str) -> None:
        """
        Revoke a Discord access or refresh token.
        
        Args:
            token: Token to revoke
        """
        logger.info(
            "Revoking Discord token",
            extra={'extra_fields': {'operation': 'revoke_token'}}
        )
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "token": token,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.revoke_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                response.raise_for_status()
                
                logger.info(
                    "Successfully revoked token",
                    extra={'extra_fields': {'operation': 'revoke_token', 'success': True}}
                )
        except Exception as e:
            logger.warning(
                f"Failed to revoke token (may already be invalid): {e}",
                extra={'extra_fields': {'operation': 'revoke_token', 'error': str(e)}}
            )
            # Don't raise - token may already be invalid
    
    async def create_or_update_user(
        self,
        db: Session,
        discord_user: Dict[str, Any],
        access_token: str,
        refresh_token: str,
        expires_at: datetime
    ) -> User:
        """
        Create a new user or update existing user with Discord info.
        
        Args:
            db: Database session
            discord_user: User data from Discord API
            access_token: Discord access token
            refresh_token: Discord refresh token
            expires_at: Token expiration time
            
        Returns:
            User object
        """
        discord_id = discord_user["id"]
        
        logger.info(
            "Creating or updating user from Discord OAuth",
            extra={'extra_fields': {
                'operation': 'create_or_update_user',
                'discord_id': discord_id,
                'username': discord_user.get('username')
            }}
        )
        
        # Check if user exists with this Discord ID
        user = db.query(User).filter(User.discord_user_id == discord_id).first()
        
        if user:
            # Update existing user
            logger.info(f"Updating existing user with Discord ID {discord_id}")
            user.discord_username = discord_user["username"]
            user.discord_discriminator = discord_user.get("discriminator", "0")
            user.discord_avatar = discord_user.get("avatar")
            user.discord_access_token = encrypt_token(access_token)
            user.discord_refresh_token = encrypt_token(refresh_token)
            user.discord_token_expires_at = expires_at
            # Preserve is_new flag so onboarding logic can decide when to flip it
            # (it is set to False when onboarding is completed).
            user.oauth_provider = "discord"
        else:
            # Create new user
            email = discord_user.get("email")
            if not email:
                raise HTTPException(
                    status_code=400,
                    detail="Email scope is required for registration"
                )
            
            # Check if email already exists
            existing_user = db.query(User).filter(User.email == email).first()
            if existing_user:
                # Link Discord to existing account
                logger.info(f"Linking Discord to existing account with email {email}")
                existing_user.discord_user_id = discord_id
                existing_user.discord_username = discord_user["username"]
                existing_user.discord_discriminator = discord_user.get("discriminator", "0")
                existing_user.discord_avatar = discord_user.get("avatar")
                existing_user.discord_access_token = encrypt_token(access_token)
                existing_user.discord_refresh_token = encrypt_token(refresh_token)
                existing_user.discord_token_expires_at = expires_at
                existing_user.oauth_provider = "discord"
                user = existing_user
            else:
                # Create completely new user
                logger.info(f"Creating new user from Discord OAuth with email {email}")
                user = User(
                    email=email,
                    full_name=discord_user.get("global_name") or discord_user["username"],
                    discord_user_id=discord_id,
                    discord_username=discord_user["username"],
                    discord_discriminator=discord_user.get("discriminator", "0"),
                    discord_avatar=discord_user.get("avatar"),
                    discord_access_token=encrypt_token(access_token),
                    discord_refresh_token=encrypt_token(refresh_token),
                    discord_token_expires_at=expires_at,
                    preferred_tone="coach",  # Default
                    timezone="UTC",  # Will be set in onboarding
                    is_new=True,
                    oauth_provider="discord"
                )
                db.add(user)
        
        db.commit()
        db.refresh(user)
        
        logger.info(
            "Successfully created/updated user",
            extra={'extra_fields': {
                'operation': 'create_or_update_user',
                'user_id': str(user.id),
                'is_new': user.is_new
            }}
        )
        
        return user


# Singleton instance
discord_oauth_service = DiscordOAuthService()
