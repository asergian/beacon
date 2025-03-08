"""
Utilities for extracting and processing email message bodies.
"""

import logging
import email
from typing import Dict, Any, Tuple
from .html_utils import text_to_html

logger = logging.getLogger(__name__)

def has_attachments(msg: email.message.Message) -> bool:
    """Check if the email has any attachments."""
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
    
    Args:
        raw_email: Dictionary containing email data
        
    Returns:
        The best available body content
    """
    body = raw_email.get('body_html', '')
    if not body:
        body = raw_email.get('body_text', '')
    return body

def extract_body_content(msg: email.message.Message) -> str:
    """
    Extract the body from an email message, handling different content types.
    
    Args:
        msg: Email message object
        
    Returns:
        Extracted body text, preferring HTML content
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
    
    Args:
        msg: Email message object
        
    Returns:
        Tuple of (html_content, plain_text)
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
    
    Args:
        part: Email message part
        
    Returns:
        True if the part is an attachment, False otherwise
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
    
    Args:
        payload: Message payload bytes
        content_type: Content type string
        charset: Character encoding
        
    Returns:
        Tuple of (html_content, plain_text)
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