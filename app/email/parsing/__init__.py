"""
Email parsing package for extracting and processing email content.

This package provides comprehensive utilities for parsing, validating,
and extracting structured metadata from various email formats. It handles
complex email structures, encodings, and formats to produce clean,
normalized data for application use.

The package contains both high-level parsers and specialized utility modules
for specific email processing tasks.

Modules:
    parser: Main parsing functionality and metadata extraction
    utils: Utility functions organized by purpose (date, header, HTML, etc.)

Example:
    ```python
    from app.email.parsing import EmailParser, EmailMetadata
    
    # Create a parser instance
    parser = EmailParser()
    
    # Extract metadata from an email
    metadata = parser.extract_metadata(raw_email_data)
    
    # Access structured email metadata
    subject = metadata.subject
    sender = metadata.sender
    body = metadata.body
    ```

Classes:
    EmailParser: Main parser class for extracting email metadata
    EmailMetadata: Structured container for email metadata
    EmailParsingError: Exception raised for parsing errors
"""

from .parser import EmailParser, EmailMetadata, EmailParsingError
from .utils import (
    decode_header,
    normalize_date,
    parse_email_date,
    safe_extract_header,
    sanitize_text,
    strip_html,
    extract_body_content,
    has_attachments
)

__all__ = [
    'EmailParser',
    'EmailMetadata',
    'EmailParsingError',
    'decode_header',
    'normalize_date',
    'parse_email_date',
    'safe_extract_header',
    'sanitize_text',
    'strip_html',
    'extract_body_content',
    'has_attachments'
]
