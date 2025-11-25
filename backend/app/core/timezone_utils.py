"""Timezone validation and error handling utilities.

Requirements: 8.5
"""

import pytz
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def validate_timezone(timezone_str: str) -> Tuple[bool, Optional[str]]:
    """Validate a timezone string against the IANA database.
    
    Args:
        timezone_str: The timezone string to validate (e.g., "America/New_York")
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if timezone is valid, False otherwise
        - error_message: None if valid, error description if invalid
        
    Requirements: 8.5
    """
    if not timezone_str:
        return False, "Timezone cannot be empty"
    
    try:
        # Try to get the timezone from pytz
        pytz.timezone(timezone_str)
        return True, None
    except pytz.exceptions.UnknownTimeZoneError:
        logger.warning(f"Invalid timezone provided: {timezone_str}")
        return False, f"Unknown timezone: {timezone_str}. Please use a valid IANA timezone (e.g., 'America/New_York', 'Europe/London', 'UTC')"
    except Exception as e:
        logger.error(f"Error validating timezone {timezone_str}: {e}")
        return False, f"Invalid timezone format: {timezone_str}"


def get_safe_timezone(timezone_str: Optional[str]) -> str:
    """Get a safe timezone, defaulting to UTC if invalid.
    
    Args:
        timezone_str: The timezone string to validate
        
    Returns:
        The validated timezone string, or "UTC" if invalid
        
    Requirements: 8.5
    """
    if not timezone_str:
        logger.info("No timezone provided, defaulting to UTC")
        return "UTC"
    
    is_valid, error_msg = validate_timezone(timezone_str)
    
    if is_valid:
        return timezone_str
    else:
        logger.warning(f"Invalid timezone '{timezone_str}', defaulting to UTC. Error: {error_msg}")
        return "UTC"


def get_common_timezones() -> list[str]:
    """Get a list of common timezones for user selection.
    
    Returns:
        List of common timezone strings
    """
    return [
        "UTC",
        "America/New_York",
        "America/Chicago",
        "America/Denver",
        "America/Los_Angeles",
        "America/Toronto",
        "America/Mexico_City",
        "America/Sao_Paulo",
        "Europe/London",
        "Europe/Paris",
        "Europe/Berlin",
        "Europe/Moscow",
        "Asia/Dubai",
        "Asia/Kolkata",
        "Asia/Shanghai",
        "Asia/Tokyo",
        "Asia/Singapore",
        "Australia/Sydney",
        "Pacific/Auckland",
    ]


def get_all_timezones() -> list[str]:
    """Get all available IANA timezones.
    
    Returns:
        List of all timezone strings
    """
    return sorted(pytz.all_timezones)
