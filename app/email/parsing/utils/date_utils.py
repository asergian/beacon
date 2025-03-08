"""
Utilities for handling date parsing and normalization in email messages.

This module provides functions for processing, normalizing, and parsing dates
from various formats commonly found in email messages.

Example:
    ```python
    from app.email.parsing.utils.date_utils import normalize_date
    
    normalized_date = normalize_date("2023-01-15T14:30:00")
    ```
"""

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

def normalize_date(date_value: Any) -> datetime:
    """
    Normalize date values to datetime objects with proper error handling.
    
    Converts various date formats (string or datetime) to a normalized
    datetime object, providing fallback to current time when conversion fails.
    
    Args:
        date_value: Date value which could be string, datetime, or None
        
    Returns:
        datetime: Normalized datetime object or current time if conversion fails
        
    Examples:
        >>> normalize_date("2023-01-15T14:30:00")
        datetime.datetime(2023, 1, 15, 14, 30)
        >>> normalize_date(datetime(2023, 1, 15, 14, 30))
        datetime.datetime(2023, 1, 15, 14, 30)
        >>> normalize_date(None)  # Returns current time
    """
    if isinstance(date_value, str):
        try:
            return datetime.fromisoformat(date_value)
        except (ValueError, TypeError):
            return datetime.now()
    elif not isinstance(date_value, datetime):
        return datetime.now()
    return date_value

def parse_email_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse email date string into datetime object.
    
    Converts an email date string in RFC 2822 format into a datetime object.
    
    Args:
        date_str: Date string from email header in RFC 2822 format
        
    Returns:
        Optional[datetime]: Parsed datetime object or None if parsing fails
        
    Examples:
        >>> parse_email_date("Mon, 15 Jan 2023 14:30:00 +0000")
        datetime.datetime(2023, 1, 15, 14, 30, tzinfo=datetime.timezone.utc)
        >>> parse_email_date(None)
        None
    """
    if not date_str:
        return None
        
    try:
        return parsedate_to_datetime(date_str)
    except Exception as e:
        logger.warning(f"Date parse error: {e}")
        return None 