"""User context setup and validation.

This module provides functions for setting up and validating user context
in the email pipeline, including user authentication, timezone handling,
and user preference retrieval.
"""

import logging
from typing import Tuple, Optional
from datetime import timezone, tzinfo
from zoneinfo import ZoneInfo
from flask import session

from app.models.user import User
from app.email.pipeline.orchestrator import AnalysisCommand


def setup_user_context(
    command: AnalysisCommand,
    logger: Optional[logging.Logger] = None
) -> Tuple[int, str, tzinfo, bool, int]:
    """Set up the user context for email analysis.
    
    Retrieves and validates user information from the session, fetches
    user preferences, and sets up timezone information.
    
    Args:
        command: The analysis command containing parameters
        logger: Optional logger instance for logging events
        
    Returns:
        Tuple containing:
            - user_id (int): The user's ID
            - user_email (str): The user's email address
            - timezone_obj (tzinfo): The user's timezone object
            - ai_enabled (bool): Whether AI features are enabled
            - cache_duration (int): Cache duration in days
            
    Raises:
        ValueError: If user context is invalid or missing
    """
    logger = logger or logging.getLogger(__name__)
    
    # First ensure we have user context
    if 'user' not in session:
        raise ValueError("No user found in session")
            
    user_id = int(session['user'].get('id'))
    user_email = session['user'].get('email')
    if not user_email:
        raise ValueError("No user email found in session")
            
    logger.info(f"Setting up user context: {user_email} (ID: {user_id}), Days Back: {command.days_back}, Cache Duration: {command.cache_duration_days} days")
    logger.debug(f"User Context Setup\n"
        f"    User: {user_email} (ID: {user_id})\n"
        f"    Days Back: {command.days_back}\n"
        f"    Cache Duration: {command.cache_duration_days} days"
    )
    
    # Get user settings
    user = User.query.get(user_id)
    if not user:
        raise ValueError("User not found in database")
            
    # Verify user email matches database
    if user.email != user_email:
        raise ValueError("User email mismatch between session and database")
    
    # Get user timezone setting, fall back to PST if not set
    user_timezone = user.get_setting('timezone', 'US/Pacific')
    timezone_obj = timezone.utc
    try:
        # Try to parse the timezone from string (e.g., 'America/New_York')
        timezone_obj = ZoneInfo(user_timezone)
        logger.debug(f"Using user timezone: {user_timezone}")
    except (ImportError, Exception) as e:
        logger.warning(f"Could not use user timezone ({user_timezone}), falling back to US/Pacific: {e}")
        try:
            timezone_obj = ZoneInfo('US/Pacific')
        except Exception:
            timezone_obj = timezone.utc
    
    # Check AI features once at the pipeline level
    ai_enabled = user.get_setting('ai_features.enabled', True)
    if not ai_enabled:
        logger.info("AI features disabled for this pipeline run")
    
    # Get cache duration from settings
    cache_duration = user.get_setting('email_preferences.cache_duration_days', 7)
    
    # Ensure cache_duration is an integer
    try:
        cache_duration = int(cache_duration)
    except (ValueError, TypeError):
        logger.warning(f"Invalid cache_duration value: {cache_duration}, using default of 7 days")
        cache_duration = 7
    
    return user_id, user_email, timezone_obj, ai_enabled, cache_duration
