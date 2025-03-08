"""Date utility functions for the Gmail client.

This module provides date and time utility functions for the Gmail client,
particularly for creating date cutoffs for Gmail queries.
"""

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def calculate_date_cutoff(days_back: int, user_timezone: str = 'US/Pacific') -> str:
    """Calculate date cutoff for Gmail query based on days_back.
    
    Args:
        days_back: Number of days back to fetch emails
        user_timezone: User's timezone string
        
    Returns:
        Gmail date query string (e.g., "after:2023/01/01")
    """
    # Adjust days_back to match cache logic (days_back=1 means today only)
    adjusted_days = max(0, days_back - 1)  # Ensure we don't use negative days
    
    # Calculate the time range using user's timezone
    try:
        # Create timezone object from string
        user_tz = ZoneInfo(user_timezone)
        logger.debug(f"Using user timezone: {user_timezone}")
    except (ImportError, Exception) as e:
        logger.warning(f"Could not use user timezone ({user_timezone}), falling back to US/Pacific: {e}")
        try:
            user_tz = ZoneInfo('US/Pacific')
        except Exception:
            user_tz = timezone.utc
    
    # Calculate the time range using user's timezone
    user_now = datetime.now(user_tz)
    user_midnight = (user_now - timedelta(days=adjusted_days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    
    # Convert to UTC for the Gmail query
    utc_date = user_midnight.astimezone(timezone.utc)
    date_cutoff = utc_date.strftime('%Y/%m/%d')
    
    # Debug logging
    logger.debug(f"Date cutoff calculation: days_back={days_back}, adjusted_days={adjusted_days}")
    logger.debug(f"    User timezone: {user_timezone}")
    logger.debug(f"    User now: {user_now}")
    logger.debug(f"    User midnight cutoff: {user_midnight}")
    logger.debug(f"    UTC cutoff: {utc_date}")
    
    return f"after:{date_cutoff}" 