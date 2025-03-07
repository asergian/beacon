"""
Email validation and preprocessing utilities.

This module provides functions for validating and preparing
email data for semantic analysis.
"""
import logging
from typing import Dict, Any

from ....core.email_parsing import EmailMetadata
from ..utilities.text_processor import strip_html

logger = logging.getLogger(__name__)


def validate_email_data(email_data: Any) -> EmailMetadata:
    """
    Validate and normalize email data.
    
    Args:
        email_data: The email data to validate (EmailMetadata or dict)
        
    Returns:
        Validated EmailMetadata object
        
    Raises:
        ValueError: If email_data is invalid or missing required fields
    """
    # Ensure email_data is properly structured
    if not isinstance(email_data, EmailMetadata):
        logger.warning(f"email_data is not an EmailMetadata object (got {type(email_data)})")
        if isinstance(email_data, dict):
            email_data = EmailMetadata(**email_data)
        else:
            raise ValueError("Invalid email_data format: must be EmailMetadata or dict")

    # Validate required fields
    required_fields = ['subject', 'sender', 'body']
    for field in required_fields:
        if not hasattr(email_data, field) or getattr(email_data, field) is None:
            logger.error(f"Missing required field '{field}' in email_data")
            raise ValueError(f"Missing required field: {field}")
            
    return email_data


def preprocess_email(email_data: EmailMetadata, token_handler, max_tokens: int) -> EmailMetadata:
    """
    Preprocess an email by cleaning and truncating its content.
    
    Args:
        email_data: The email data to preprocess
        token_handler: The token handler for truncation
        max_tokens: Maximum number of tokens for the body
        
    Returns:
        EmailMetadata with processed content
    """
    # Clean HTML and truncate content
    clean_body = strip_html(email_data.body)
    truncated_body = token_handler.truncate_to_tokens(clean_body, max_tokens)
    
    # Create clean version of email metadata
    return EmailMetadata(
        id=email_data.id,
        subject=email_data.subject,
        sender=email_data.sender,
        body=truncated_body,
        date=email_data.date
    ) 