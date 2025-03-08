"""Email fetching and cache handling utilities.

This module provides functions for fetching emails from Gmail and
the email cache, as well as filtering and processing the fetched emails.
"""

import logging
from typing import List, Dict, Set, Tuple, Optional, AsyncGenerator, Union, Any
from datetime import tzinfo
import asyncio

from app.email.models.processed_email import ProcessedEmail  
from app.email.storage.base_cache import EmailCache
from app.email.clients.gmail.client import GmailClient
from app.email.pipeline.orchestrator import AnalysisCommand
from app.utils.memory_profiling import log_memory_usage


async def send_cache_status() -> AsyncGenerator[Dict, None]:
    """Send a status update that the system is checking the cache.
    
    Yields:
        Status message about checking cache
    """
    yield {
        'type': 'status',
        'data': {'message': 'Checking cache...'}
    }


async def fetch_cached_emails(
    command: AnalysisCommand,
    user_email: str,
    user_timezone: Union[str, tzinfo],
    stats: Dict,
    cache: Optional[EmailCache] = None,
    logger: Optional[logging.Logger] = None
) -> Tuple[List[ProcessedEmail], Set[str]]:
    """Fetch cached emails for the user.
    
    Args:
        command: The analysis command with parameters
        user_email: The user's email address
        user_timezone: The user's timezone (string or tzinfo object)
        stats: Dictionary to track stats
        cache: Email cache implementation
        logger: Optional logger for logging events
        
    Returns:
        Tuple containing:
            - List of cached ProcessedEmail objects
            - Set of cached email IDs
    """
    logger = logger or logging.getLogger(__name__)
    cached_emails = []
    cached_ids = set()
    
    if cache:
        try:
            # Convert timezone object to string if needed
            timezone_str = str(user_timezone) if hasattr(user_timezone, 'key') else str(user_timezone)
            cached_emails = await cache.get_recent(
                command.cache_duration_days,
                command.days_back,
                user_email,
                timezone_str
            )
            cached_ids = {email.id for email in cached_emails}
            stats["cached"] = len(cached_ids)
            logger.info(f"Retrieved {len(cached_emails)} cached emails")
        except Exception as e:
            logger.error(f"Error retrieving from cache: {e}")
    
    return cached_emails, cached_ids


async def fetch_emails_from_gmail(
    command: AnalysisCommand,
    user_email: str,
    user_timezone: Union[str, tzinfo],
    cached_ids: Set[str],
    cached_emails: List[ProcessedEmail],
    stats: Dict,
    connection: Optional[GmailClient] = None,
    logger: Optional[logging.Logger] = None
) -> Tuple[List[Dict], Set[str], List[Dict]]:
    """Fetch emails from Gmail for analysis.
    
    Args:
        command: The analysis command with parameters
        user_email: The user's email address
        user_timezone: The user's timezone (string or tzinfo object)
        cached_ids: Set of cached email IDs
        cached_emails: List of cached emails
        stats: Dictionary to track stats
        connection: Gmail client connection
        logger: Optional logger for logging events
        
    Returns:
        Tuple containing:
            - List of raw email dictionaries
            - Set of Gmail email IDs
            - List of new raw emails not in cache
            
    Raises:
        RuntimeError: If connection is None
    """
    logger = logger or logging.getLogger(__name__)
    
    if connection is None:
        raise RuntimeError("Gmail connection is required")
    
    # Connect to Gmail
    await connection.connect(user_email)
    
    # Convert timezone object to string if needed
    timezone_str = user_timezone.key if hasattr(user_timezone, 'key') else str(user_timezone)
    
    # Fetch emails
    raw_emails = await connection.fetch_emails(
        days_back=command.days_back,
        user_email=user_email,
        user_timezone=timezone_str
    )
    stats["emails_fetched"] = len(raw_emails)
    
    # Log memory after Gmail fetch
    log_memory_usage(logger, "After Gmail Fetch")
    
    # Get the IDs of emails currently in Gmail
    gmail_email_ids = {email.get('id') for email in raw_emails}
    
    # Filter out already cached emails
    new_raw_emails = [email for email in raw_emails if email.get('id') not in cached_ids]
    stats["new_emails"] = len(new_raw_emails)
    
    logger.info(f"Email Retrieval Complete: {len(raw_emails)} total, {len(cached_emails)} cached)")
    logger.debug(f"Email Retrieval Complete\n"
        f"    From Gmail: {len(raw_emails)} emails\n"
        f"    Already Cached: {len(cached_ids)} emails\n"
        f"    New Emails: {len(new_raw_emails)} emails"
    )
    
    return raw_emails, gmail_email_ids, new_raw_emails


def filter_cached_emails(
    cached_emails: List[ProcessedEmail],
    gmail_email_ids: Set[str],
    stats: Dict,
    cache: Optional[EmailCache] = None,
    user_email: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> Tuple[List[ProcessedEmail], Set[str]]:
    """Filter cached emails to keep only those still in Gmail.
    
    Args:
        cached_emails: List of cached emails
        gmail_email_ids: Set of email IDs currently in Gmail
        stats: Dictionary to track stats
        cache: Optional cache implementation for removing deleted emails
        user_email: User's email address, needed for cache operations
        logger: Optional logger for logging events
        
    Returns:
        Tuple containing:
            - Filtered list of cached emails
            - Set of filtered cached email IDs
    """
    logger = logger or logging.getLogger(__name__)
    
    if not cached_emails:
        return [], set()
        
    original_cached_count = len(cached_emails)
    filtered_cached_emails = [email for email in cached_emails if email.id in gmail_email_ids]
    filtered_out_count = original_cached_count - len(filtered_cached_emails)
    filtered_cached_ids = {email.id for email in filtered_cached_emails}
    
    # Find emails that were filtered out (deleted from Gmail)
    filtered_out_emails = [email for email in cached_emails if email.id not in gmail_email_ids]
    filtered_out_ids = {email.id for email in filtered_out_emails}
    
    if filtered_out_count > 0:
        logger.info(f"Filtered out {filtered_out_count} cached emails that were deleted from Gmail")
        stats["deleted_emails_filtered"] = filtered_out_count
        
        # Delete filtered out emails from cache if cache is available
        if cache and user_email and filtered_out_emails:
            try:
                # Check if the cache has the delete_emails method (RedisEmailCache does)
                if hasattr(cache, 'delete_emails') and callable(getattr(cache, 'delete_emails')):
                    # Use the cache's delete_emails method
                    logger.info(f"Removing {filtered_out_count} deleted emails from cache for user {user_email}")
                    asyncio.create_task(cache.delete_emails(user_email, list(filtered_out_ids)))
                else:
                    # Fallback for cache implementations without delete_emails method
                    logger.info(f"Using fallback method to remove {filtered_out_count} deleted emails from cache")
                    if filtered_cached_emails:
                        # Re-store the filtered list (this will reset TTLs but is better than keeping deleted emails)
                        asyncio.create_task(cache.store_many(filtered_cached_emails, user_email))
            except Exception as e:
                logger.error(f"Failed to update cache after filtering: {e}")
    
    return filtered_cached_emails, filtered_cached_ids
