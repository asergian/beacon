"""
Email parsing utilities package.

This package provides utility modules for parsing and processing email messages.
It organizes email parsing functionality into cohesive modules based on purpose.

Modules:
    date_utils: Date and time handling utilities
    header_utils: Email header processing utilities
    html_utils: HTML content processing utilities
    body_extractor: Email body content extraction utilities

Example:
    ```python
    from app.email.parsing.utils import decode_header, normalize_date
    
    decoded_subject = decode_header(raw_subject)
    normalized_date = normalize_date(date_string)
    ```
"""

from .date_utils import normalize_date, parse_email_date
from .header_utils import decode_header, safe_extract_header, sanitize_text
from .html_utils import strip_html, convert_urls_to_links, text_to_html
from .body_extractor import extract_body_content, get_best_body_content, has_attachments

__all__ = [
    'normalize_date',
    'parse_email_date',
    'decode_header',
    'safe_extract_header',
    'sanitize_text',
    'strip_html',
    'convert_urls_to_links',
    'text_to_html',
    'extract_body_content',
    'get_best_body_content',
    'has_attachments'
] 