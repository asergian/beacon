"""
Utilities for extracting and processing email message bodies.

This module provides functions for extracting body content from email messages,
handling multipart messages, determining content types, and processing
different encodings to produce usable text.

Example:
    ```python
    from app.email.parsing.utils.body_extractor import extract_body_content
    
    body = extract_body_content(email_message)
    # Returns the email body, prioritizing HTML content over plain text
    ```
"""

import logging
import email
from typing import Dict, Any, Tuple
from .html_utils import text_to_html

logger = logging.getLogger(__name__)

def has_attachments(msg: email.message.Message) -> bool:
    """
    Check if an email message has any attachments.
    
    Examines an email message for attachment parts based on content
    disposition headers.
    
    Args:
        msg: Email message object to check
        
    Returns:
        bool: True if the message has attachments, False otherwise
        
    Examples:
        >>> has_attachments(email_message_with_pdf)
        True
        >>> has_attachments(email_message_text_only)
        False
    """
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get_content_disposition() and \
               part.get_content_disposition().startswith('attachment'):
                return True
    return False

def get_best_body_content(raw_email: Dict[str, Any]) -> str:
    """
    Get the best available body content from a preprocessed email dict.
    
    Prioritizes HTML content over plain text when selecting the email body.
    
    Args:
        raw_email: Dictionary containing email data with body_html and/or body_text keys
        
    Returns:
        str: The best available body content, preferring HTML over plain text
        
    Examples:
        >>> get_best_body_content({'body_html': '<p>Hello</p>', 'body_text': 'Hello'})
        '<p>Hello</p>'
        >>> get_best_body_content({'body_text': 'Hello'})
        'Hello'
    """
    body = raw_email.get('body_html', '')
    if not body:
        body = raw_email.get('body_text', '')
    return body

def extract_body_content(msg: email.message.Message) -> str:
    """
    Extract the body from an email message, handling different content types.
    
    Processes an email message to extract body content, handling multipart
    messages and different content types. Prioritizes HTML content when available.
    
    Args:
        msg: Email message object to extract content from
        
    Returns:
        str: Extracted body text, preferring HTML content when available
        
    Examples:
        >>> extract_body_content(html_email_message)
        '<html><body>Hello World</body></html>'
        >>> extract_body_content(text_email_message)
        '<div style="font-family: Arial...">Hello World</div>'  # Converted to HTML
    """
    body = ""
    html_content = ""
    plain_text = ""

    # Skip messages that don't have a payload
    if not msg or not hasattr(msg, 'get_payload'):
        return ""

    # Process multipart and single-part messages
    html_content, plain_text = _extract_content_parts(msg)
    
    # Prioritize HTML content over plain text
    if html_content:
        body = html_content
    elif plain_text:
        # Convert plain text to HTML for better display
        body = text_to_html(plain_text)
    
    return body

def _extract_content_parts(msg: email.message.Message) -> Tuple[str, str]:
    """
    Extract HTML and plain text content from email parts.
    
    Processes multipart and single-part email messages to extract
    both HTML and plain text content.
    
    Args:
        msg: Email message object to process
        
    Returns:
        Tuple[str, str]: A tuple containing (html_content, plain_text)
    """
    html_content = ""
    plain_text = ""
    
    # If the message is multipart
    if msg.is_multipart():
        # Loop through all the message parts
        for part in msg.get_payload():
            # Skip attachments and empty parts
            if _is_attachment(part) or not hasattr(part, 'get_payload'):
                continue
                
            # Get content info
            content_type = part.get_content_type()
            charset = part.get_content_charset()
            payload = part.get_payload(decode=True)
            
            if not payload:
                continue
            
            # Process payload based on content type
            html_part, text_part = _process_payload(payload, content_type, charset or 'utf-8')
            
            if html_part and not html_content:
                html_content = html_part
            if text_part and not plain_text:
                plain_text = text_part
    else:
        # Handle single part messages
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        
        if payload:
            charset = msg.get_content_charset() or 'utf-8'
            html_content, plain_text = _process_payload(payload, content_type, charset)
    
    return html_content, plain_text

def _is_attachment(part) -> bool:
    """
    Check if a message part is an attachment.
    
    Determines if an email part should be considered an attachment
    based on content disposition and filename.
    
    Args:
        part: Email message part to check
        
    Returns:
        bool: True if the part is an attachment, False otherwise
    """
    if part.get_filename():
        return True
        
    content_disp = part.get('Content-Disposition', '')
    if content_disp and ('attachment' in content_disp or 'inline' in content_disp):
        return True
        
    return False

def _process_payload(payload: bytes, content_type: str, charset: str) -> Tuple[str, str]:
    """
    Process a message payload based on content type.
    
    Decodes payload bytes into text based on content type and charset.
    
    Args:
        payload: Message payload bytes to process
        content_type: Content type string (e.g., 'text/html', 'text/plain')
        charset: Character encoding to use for decoding
        
    Returns:
        Tuple[str, str]: A tuple containing (html_content, plain_text)
    """
    html_content = ""
    plain_text = ""
    
    try:
        decoded_payload = payload.decode(charset, errors='replace')
        
        # If this is HTML content
        if content_type == 'text/html':
            html_content = decoded_payload
        
        # If this is plain text
        elif content_type == 'text/plain':
            plain_text = decoded_payload
    except Exception as e:
        logger.warning(f"Error decoding part: {e}")
    
    return html_content, plain_text 