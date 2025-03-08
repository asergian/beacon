"""
Utilities for handling date parsing and normalization in email messages.
"""

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

def normalize_date(date_value: Any) -> datetime:
    """
    Normalize date values to datetime objects with proper error handling.
    
    Args:
        date_value: Date value which could be string, datetime, or None
        
    Returns:
        Normalized datetime object or current time if conversion fails
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
    """Parse email date string into datetime object."""
    if not date_str:
        return None
        
    try:
        return parsedate_to_datetime(date_str)
    except Exception as e:
        logger.warning(f"Date parse error: {e}")
        return None 