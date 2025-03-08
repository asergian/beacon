"""Processing utilities for the Gmail worker module.

This module provides utility functions for processing emails and messages.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.memory_management import track_email_processing
from utils.logging_utils import get_logger

def filter_emails_by_date(emails: List[Dict[str, Any]], cutoff_time: datetime) -> List[Dict[str, Any]]:
    """Filter emails by date.
    
    Args:
        emails: List of emails to filter
        cutoff_time: Cutoff time for filtering
        
    Returns:
        Filtered list of emails
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
    
    Args:
        message: The message to track
        logger: Optional logger for output
    """
    if logger is None:
        logger = get_logger()
        
    if logger:
        # Estimate message size (rough approximation)
        message_size = len(str(message))
        track_email_processing(message_size) 