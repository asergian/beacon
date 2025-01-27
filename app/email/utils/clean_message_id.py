def clean_message_id(message_id: str | None) -> str:
    """
    Standardize email Message-ID format by removing angle brackets and whitespace.
    
    Args:
        message_id: Raw Message-ID string or None
        
    Returns:
        Cleaned Message-ID string or empty string if None
    """
    if not message_id:
        return ''
    return message_id.strip().strip('<>') 