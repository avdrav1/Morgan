"""
Token encryption utilities for secure storage.
"""
from cryptography.fernet import Fernet
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def get_cipher() -> Fernet:
    """Get Fernet cipher instance."""
    if not hasattr(settings, 'ENCRYPTION_KEY') or not settings.ENCRYPTION_KEY:
        logger.warning("ENCRYPTION_KEY not set, generating temporary key (NOT FOR PRODUCTION)")
        # Generate a temporary key for development
        # In production, this should be set in environment variables
        return Fernet(Fernet.generate_key())
    
    return Fernet(settings.ENCRYPTION_KEY.encode())


cipher = get_cipher()


def encrypt_token(token: str) -> str:
    """
    Encrypt a token for secure storage.
    
    Args:
        token: Plain text token to encrypt
        
    Returns:
        Encrypted token as string
    """
    if not token:
        return ""
    
    try:
        return cipher.encrypt(token.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to encrypt token: {e}")
        raise


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt a stored token.
    
    Args:
        encrypted_token: Encrypted token string
        
    Returns:
        Decrypted plain text token
    """
    if not encrypted_token:
        return ""
    
    try:
        return cipher.decrypt(encrypted_token.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to decrypt token: {e}")
        raise
