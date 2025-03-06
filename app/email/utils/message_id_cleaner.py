"""Email Message-ID cleaning utility.

This module provides functionality for standardizing email Message-ID formats
by removing angle brackets and whitespace, ensuring consistent ID formatting
for database storage and comparison operations.
"""

def clean_message_id(message_id: str | None) -> str:
    """Standardize email Message-ID format by removing angle brackets and whitespace.
    
    Email Message-IDs can be formatted inconsistently with extra whitespace and 
    surrounding angle brackets. This function normalizes them to a consistent format
    for reliable database storage and comparison.
    
    Args:
        message_id: Raw Message-ID string or None
        
    Returns:
        Cleaned Message-ID string or empty string if None
    """
    if not message_id:
        return ''
    return message_id.strip().strip('<>') 