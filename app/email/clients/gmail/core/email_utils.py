"""Email processing utilities for Gmail API.

This module provides utility functions for processing emails retrieved from
the Gmail API, including parsing dates, formatting emails, and other common
operations.
"""

import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=128)
def parse_date(date_str: str) -> Optional[datetime]:
    """Parse email date string with caching.
    
    Args:
        date_str: The date string to parse
        
    Returns:
        Parsed datetime object or None if parsing fails
    """
    if not date_str:
        return None
    try:
        # Remove the "(UTC)" part if it exists
        date_str = date_str.split(' (')[0].strip()
        return parsedate_to_datetime(date_str)
    except Exception as e:
        logger.debug(f"Failed to parse date '{date_str}': {e}")
        return None


def create_email_data(msg_id: str, email_msg, raw_msg, snippet: str = '') -> dict:
    """Create a dictionary of email data from a parsed email message.
    
    Args:
        msg_id: The Gmail message ID
        email_msg: The parsed email message object
        raw_msg: The raw message bytes
        snippet: A snippet of the email content
        
    Returns:
        Dictionary containing normalized email data
    """
    return {
        'id': msg_id,
        'Message-ID': email_msg.get('Message-ID'),
        'subject': email_msg.get('subject'),
        'from': email_msg.get('from'),
        'to': email_msg.get('to'),
        'date': email_msg.get('date'),
        'snippet': snippet,
        'raw_message': raw_msg  # Will be processed and cleared by parser
    } 