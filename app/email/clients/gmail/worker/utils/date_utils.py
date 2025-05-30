"""Date and time utility functions for the Gmail worker module.

This module provides utility functions for handling date and time operations,
including timezone conversions and calculating cutoff dates for email filtering.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional
from zoneinfo import ZoneInfo

# Set up logger for this module
logger = logging.getLogger('gmail_worker')

def calculate_cutoff_time(days_back: int, user_timezone: str = 'US/Pacific') -> Tuple[datetime, datetime]:
    """Calculate the cutoff time for email filtering.
    
    Calculates a cutoff datetime for filtering emails based on the number of
    days to look back from the current time. Handles timezone conversion and
    ensures consistent date boundaries.
    
    Args:
        days_back: int: Number of days back to calculate cutoff. A value of 1
            means today only, 7 means the last week, etc.
        user_timezone: str: User's timezone string (e.g., 'US/Pacific').
            Defaults to 'US/Pacific' if not specified or if specified timezone
            is not available.
        
    Returns:
        Tuple[datetime, datetime]: A tuple containing:
            - user_now: Current datetime in the user's timezone
            - cutoff_time: Start of day N days ago in the user's timezone,
              where N is days_back-1 (minimum 0)
    
    Raises:
        None: Falls back to US/Pacific or UTC if timezone is invalid
    """
    # Adjust days_back to match cache logic (days_back=1 means today only)
    adjusted_days = max(0, days_back - 1)
    
    # Use the user's timezone for date calculations
    try:
        # Create timezone object from string
        user_tz = ZoneInfo(user_timezone)
        logger.info(f"Using user timezone: {user_timezone}")
    except (ImportError, Exception) as e:
        logger.warning(f"Could not use user timezone ({user_timezone}), falling back to US/Pacific: {e}")
        try:
            user_tz = ZoneInfo('US/Pacific')
        except Exception:
            user_tz = timezone.utc
    
    # Calculate the time range using user's timezone
    user_now = datetime.now(user_tz)
    cutoff_time = (user_now - timedelta(days=adjusted_days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    
    logger.info(f"Filtering emails with user timezone ({user_timezone}):\n"
               f"    User now: {user_now}\n"
               f"    User timezone cutoff: {cutoff_time}\n"
               f"    UTC cutoff: {cutoff_time.astimezone(timezone.utc)}")
    
    return user_now, cutoff_time 