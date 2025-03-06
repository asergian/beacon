"""Utility functions for email caching.

This module provides common utility functions used across different email cache
implementations, including date handling, email validation, and timezone utilities.
"""

from typing import Optional
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

def validate_user_email(user_email: str) -> str:
    """Validate user email format and presence.
    
    Args:
        user_email: The user's email address.
        
    Returns:
        Normalized (lowercase) email address.
        
    Raises:
        ValueError: If user_email is invalid.
    """
    if not user_email:
        raise ValueError("user_email cannot be empty")
    if not isinstance(user_email, str):
        raise ValueError("user_email must be a string")
    if '@' not in user_email:
        raise ValueError("Invalid email format")
    # Normalize email to lowercase
    return user_email.lower()

def get_user_timezone(user_timezone: str) -> ZoneInfo:
    """Get the ZoneInfo object for the user's timezone.
    
    Args:
        user_timezone: String representation of the user's timezone.
        
    Returns:
        ZoneInfo object for the user's timezone, or a fallback timezone.
    """
    try:
        # Create timezone object from string
        user_tz = ZoneInfo(user_timezone)
        logger.debug(f"Using user timezone: {user_timezone}")
        return user_tz
    except (ImportError, Exception) as e:
        logger.warning(f"Could not use user timezone ({user_timezone}), falling back to US/Pacific: {e}")
        try:
            return ZoneInfo('US/Pacific')
        except Exception:
            return timezone.utc

def parse_date_string(date_str: str) -> Optional[datetime]:
    """Parse a date string into a datetime object with UTC timezone.
    
    Args:
        date_str: ISO-format date string.
        
    Returns:
        Datetime object in UTC timezone or None if parsing fails.
    """
    try:
        # Handle various date formats
        if 'Z' in date_str:
            parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        elif '+' in date_str or '-' in date_str[-6:]:
            parsed_date = datetime.fromisoformat(date_str)
        else:
            parsed_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        
        # Ensure date is in UTC
        if parsed_date.tzinfo is None:
            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
        else:
            parsed_date = parsed_date.astimezone(timezone.utc)
            
        return parsed_date
    except ValueError:
        return None

def format_date_for_storage(date_obj: datetime) -> str:
    """Format a datetime object for storage in Redis.
    
    Args:
        date_obj: Datetime object to format.
        
    Returns:
        ISO format string with timezone information.
    """
    if date_obj.tzinfo is None:
        date_obj = date_obj.replace(tzinfo=timezone.utc)
    else:
        date_obj = date_obj.astimezone(timezone.utc)
    return date_obj.isoformat() 