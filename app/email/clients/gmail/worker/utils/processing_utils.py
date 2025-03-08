"""Processing utilities for the Gmail worker module.

This module provides utility functions for processing emails and messages.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .memory_management import track_email_processing
from .logging_utils import get_logger

def filter_emails_by_date(emails: List[Dict[str, Any]], cutoff_time: datetime) -> List[Dict[str, Any]]:
    """Filter emails by date.
    
    Filters a list of email dictionaries to include only those with dates
    on or after the specified cutoff time. Emails without dates or with 
    unparseable dates are included in the results.
    
    Args:
        emails: List of email dictionaries to filter. Each dictionary should
            have a 'date' key with an ISO format date string.
        cutoff_time: Cutoff datetime for filtering. Emails with dates before
            this time will be excluded.
        
    Returns:
        List[Dict[str, Any]]: Filtered list of email dictionaries that have dates
            on or after the cutoff time, or that don't have valid dates.
    """
    if not cutoff_time:
        return emails
        
    filtered_emails = []
    for email in emails:
        # Parse the date
        date_str = email.get('date')
        if date_str:
            try:
                email_date = datetime.fromisoformat(date_str)
                if email_date >= cutoff_time:
                    filtered_emails.append(email)
            except (ValueError, TypeError):
                # If date parsing fails, include the email
                filtered_emails.append(email)
        else:
            # If no date, include the email
            filtered_emails.append(email)
                
    return filtered_emails


def track_message_processing(message: Dict[str, Any], logger: Optional[logging.Logger] = None) -> None:
    """Track message processing for memory management.
    
    Records the approximate size of a message to track memory usage during
    email processing. Helps monitor resource consumption across the worker
    process.
    
    Args:
        message: Dict[str, Any]: The message dictionary to track. The entire
            message structure is used to estimate memory usage.
        logger: Optional[logging.Logger]: Logger instance for output. If None,
            a default logger will be obtained using get_logger().
    
    Returns:
        None
    """
    if logger is None:
        logger = get_logger()
        
    if logger:
        # Estimate message size (rough approximation)
        message_size = len(str(message))
        track_email_processing(message_size) 