"""Email parsing utilities for Gmail worker.

This module provides functions for parsing and decoding email content
from the Gmail API responses.
"""

import base64
import email.header
import email.utils
import quopri
import re
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from functools import lru_cache

from utils.logging_utils import get_logger

# Get a logger for this module
logger = get_logger('gmail_parser')

#
# Header Decoding Functions
#

def decode_bytes_with_encoding(part: bytes, encoding: Optional[str] = None) -> str:
    """Decode bytes using the specified encoding or fallback to utf-8.
    
    Args:
        part: Bytes to decode
        encoding: Character encoding to use
        
    Returns:
        Decoded string
    """
    if not isinstance(part, bytes):
        return part
        
    try:
        if encoding:
            return part.decode(encoding, errors='replace')
        else:
            # Default to utf-8 if no encoding is specified
            return part.decode('utf-8', errors='replace')
    except LookupError:
        # If encoding is not recognized, try utf-8
        return part.decode('utf-8', errors='replace')
    except Exception:
        # Last resort fallback
        return str(part)


def decode_encoded_word(charset: str, encoding: str, encoded_text: str) -> str:
    """Decode a single encoded word in an email header.
    
    Args:
        charset: Character set of the encoded text
        encoding: Encoding method (B for base64, Q for quoted-printable)
        encoded_text: The encoded text
        
    Returns:
        Decoded text
    """
    try:
        if encoding.upper() == 'B':
            # Base64 encoding
            decoded_bytes = base64.b64decode(encoded_text)
            return decoded_bytes.decode(charset, errors='replace')
        elif encoding.upper() == 'Q':
            # Quoted-printable encoding
            decoded_bytes = quopri.decodestring(encoded_text.replace('_', ' '))
            return decoded_bytes.decode(charset, errors='replace')
        return encoded_text
    except Exception:
        return encoded_text


def decode_encoded_words_regex(text: str) -> str:
    """Decode any encoded words in text using regex.
    
    Args:
        text: Text that may contain encoded words
        
    Returns:
        Decoded text
    """
    if '=?' not in text or '?=' not in text:
        return text
        
    pattern = r'=\?([^?]+)\?([BbQq])\?([^?]*)\?='
    
    def decode_match(match):
        charset, encoding, encoded_text = match.groups()
        return decode_encoded_word(charset, encoding, encoded_text)
        
    return re.sub(pattern, decode_match, text)


def decode_header(header_text: str) -> str:
    """Decode email header text that may contain encoded words.
    
    Args:
        header_text: The header text to decode
        
    Returns:
        Decoded header text
    """
    if not header_text:
        return ""
        
    try:
        # Decode any encoded words in the header using email.header module
        decoded_parts = []
        for part, encoding in email.header.decode_header(header_text):
            decoded_parts.append(decode_bytes_with_encoding(part, encoding))
                
        # Join the decoded parts
        decoded_text = ''.join(decoded_parts)
        
        # Handle any remaining encoded words using regex
        return decode_encoded_words_regex(decoded_text)
    except Exception:
        # If decoding fails, return the original text
        return header_text


#
# Date Parsing Functions
#

@lru_cache(maxsize=128)
def parse_date(date_str: str) -> Optional[datetime]:
    """Parse email date string with caching.
    
    Args:
        date_str: The date string to parse
        
    Returns:
        Parsed datetime object or None if parsing fails
    """
    if not date_str:
        return None
        
    try:
        # Remove the "(UTC)" part if it exists
        date_str = date_str.split(' (')[0].strip()
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


#
# Content Extraction Functions
#

def decode_base64_content(body_data: str, default_encoding: str = 'utf-8') -> str:
    """Decode base64 encoded content.
    
    Args:
        body_data: Base64 encoded string
        default_encoding: Encoding to use for decoding (default: utf-8)
        
    Returns:
        Decoded content as string
    """
    if not body_data:
        return ""
        
    try:
        return base64.urlsafe_b64decode(body_data).decode(default_encoding, errors='replace')
    except Exception:
        # In case of decoding errors, return empty string
        return ""


def get_content_by_mime_type(part: Dict[str, Any], mime_type: str) -> str:
    """Extract content from a part if it matches the specified MIME type.
    
    Args:
        part: Email part data
        mime_type: MIME type to look for
        
    Returns:
        Decoded content if MIME type matches, empty string otherwise
    """
    part_mime_type = part.get('mimeType', '')
    body_data = part.get('body', {}).get('data', '')
    
    if part_mime_type == mime_type and body_data:
        return decode_base64_content(body_data)
    return ""


def extract_content_from_parts(parts: List[Dict[str, Any]], 
                               text_content: str = "", 
                               html_content: str = "") -> Tuple[str, str]:
    """Extract text and HTML content from message parts recursively.
    
    Args:
        parts: List of email parts
        text_content: Existing text content to append to
        html_content: Existing HTML content to append to
        
    Returns:
        Tuple of (text_content, html_content)
    """
    if not parts:
        return text_content, html_content
        
    for part in parts:
        # Get content from this part
        if not text_content:
            new_text = get_content_by_mime_type(part, 'text/plain')
            if new_text:
                text_content = new_text
                
        if not html_content:
            new_html = get_content_by_mime_type(part, 'text/html')
            if new_html:
                html_content = new_html
        
        # Process nested parts recursively
        nested_parts = part.get('parts', [])
        if nested_parts:
            text_content, html_content = extract_content_from_parts(
                nested_parts, text_content, html_content)
    
    return text_content, html_content


def extract_email_parts(message_data: Dict[str, Any]) -> Tuple[str, str, Dict[str, str]]:
    """Extract text, HTML content, and headers from a Gmail message.
    
    Args:
        message_data: The Gmail API message data
        
    Returns:
        Tuple of (text_content, html_content, headers)
    """
    # Extract headers
    headers = {}
    for header in message_data.get('payload', {}).get('headers', []):
        name = header.get('name', '').lower()
        value = header.get('value', '')
        if name in ['from', 'to', 'cc', 'bcc', 'subject', 'date', 'message-id']:
            headers[name] = decode_header(value)
    
    # Extract parts and body
    parts = message_data.get('payload', {}).get('parts', [])
    if not parts:  # Simple message without parts
        parts = [message_data.get('payload', {})]
    
    # Extract content from parts recursively
    text_content, html_content = extract_content_from_parts(parts)
    
    # If we still don't have content, try the payload body directly
    if not text_content and not html_content:
        body_data = message_data.get('payload', {}).get('body', {}).get('data', '')
        if body_data:
            mime_type = message_data.get('payload', {}).get('mimeType', '')
            content = decode_base64_content(body_data)
            if 'html' in mime_type:
                html_content = content
            else:
                text_content = content
                
    return text_content, html_content, headers


#
# Main Message Processing Function
#

def process_message(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process a Gmail message into a structured format.
    
    Args:
        message_data: The Gmail API message data
        
    Returns:
        Structured message data
    """
    # Extract content and headers
    text_content, html_content, headers = extract_email_parts(message_data)
    
    # Parse the date
    date_str = headers.get('date', '')
    date = parse_date(date_str) if date_str else None
    
    # Create structured message
    return {
        'id': message_data.get('id', ''),
        'thread_id': message_data.get('threadId', ''),
        'from': headers.get('from', ''),
        'to': headers.get('to', ''),
        'cc': headers.get('cc', ''),
        'bcc': headers.get('bcc', ''),
        'subject': headers.get('subject', ''),
        'date': date.isoformat() if date else None,
        'message_id': headers.get('message-id', ''),
        'body_text': text_content,
        'body_html': html_content,
        'labels': message_data.get('labelIds', []),
        'snippet': message_data.get('snippet', ''),
        'headers': headers
    } 