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
    
    Attempts to decode bytes using the specified encoding, falling back to
    UTF-8 if the specified encoding fails or is not provided. This function
    handles various error cases gracefully to ensure it always returns a string.
    
    Args:
        part: bytes: The bytes data to decode
        encoding: Optional[str]: Character encoding to use for decoding.
            If None, UTF-8 will be used as the default.
        
    Returns:
        str: Decoded string. If decoding fails, the function will attempt to
            use UTF-8 with error replacement or as a last resort, convert
            the bytes to a string representation.
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
    
    Handles the RFC 2047 encoded-word format used in email headers, supporting
    both base64 (B) and quoted-printable (Q) encoding methods.
    
    Args:
        charset: str: Character set of the encoded text (e.g., 'utf-8', 'iso-8859-1')
        encoding: str: Encoding method - 'B' for base64, 'Q' for quoted-printable
        encoded_text: str: The encoded text to decode
        
    Returns:
        str: Decoded text. Returns the original text if decoding fails.
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
    
    Searches for RFC 2047 encoded words in the text and decodes them.
    This is used as a fallback mechanism when the standard email.header
    module fails to decode properly.
    
    Args:
        text: str: Text that may contain encoded words in the format =?charset?encoding?text?=
            
    Returns:
        str: Text with all encoded words decoded. If no encoded words are found
            or if decoding fails, returns the original text.
    """
    if '=?' not in text or '?=' not in text:
        return text
        
    pattern = r'=\?([^?]+)\?([BbQq])\?([^?]*)\?='
    
    def decode_match(match):
        """Decode a single regex match of an encoded word.
        
        Args:
            match: re.Match object containing the encoded word components
            
        Returns:
            str: Decoded text for this match
        """
        charset, encoding, encoded_text = match.groups()
        return decode_encoded_word(charset, encoding, encoded_text)
        
    return re.sub(pattern, decode_match, text)


def decode_header(header_text: str) -> str:
    """Decode email header text that may contain encoded words.
    
    Uses a two-step process to decode email headers:
    1. Try the standard email.header module
    2. Fall back to regex-based decoding for any remaining encoded words
    
    This handles complex headers with mixed encodings and character sets.
    
    Args:
        header_text: str: The header text to decode, which may contain
            encoded words in =?charset?encoding?text?= format
            
    Returns:
        str: Fully decoded header text as a single string. If decoding
            fails, returns the original text.
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
    
    Converts an email date string into a datetime object, with caching for
    better performance. The function uses LRU caching to avoid repeatedly
    parsing the same date strings.
    
    Args:
        date_str: str: The date string to parse, typically from an email's
            Date header in RFC 2822 format
            
    Returns:
        Optional[datetime]: Parsed datetime object, or None if parsing fails
            or if date_str is empty
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
    
    Decodes base64 encoded content from email bodies, handling URL-safe
    base64 encoding and character encoding issues.
    
    Args:
        body_data: str: Base64 encoded string from email body
        default_encoding: str: Character encoding to use for decoding the bytes
            after base64 decoding. Defaults to 'utf-8'.
            
    Returns:
        str: Decoded content as string. Returns an empty string if body_data is
            empty or if decoding fails.
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
    
    Examines an email part and extracts its content if the MIME type matches
    the requested type. This is used to extract specific content types like
    text/plain or text/html from email messages.
    
    Args:
        part: Dict[str, Any]: Email part data from Gmail API response
        mime_type: str: MIME type to look for (e.g., 'text/plain', 'text/html')
        
    Returns:
        str: Decoded content if MIME type matches, empty string otherwise or
            if the part has no body data
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
    
    Processes a list of email parts recursively to extract both text/plain
    and text/html content. This handles complex multipart email structures
    with nested parts.
    
    Args:
        parts: List[Dict[str, Any]]: List of email parts from Gmail API response
        text_content: str: Existing text content to append to. Defaults to empty string.
        html_content: str: Existing HTML content to append to. Defaults to empty string.
        
    Returns:
        Tuple[str, str]: A tuple containing:
            - text_content: Plain text content extracted from the parts
            - html_content: HTML content extracted from the parts
            
    Note:
        The function prioritizes finding content when text_content or html_content
        are empty. If they already have values, it won't overwrite them.
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
    
    Parses the Gmail API message data to extract the message body in both
    plain text and HTML formats, along with decoded email headers.
    
    Args:
        message_data: Dict[str, Any]: The Gmail API message data object
            containing payload, headers, parts, and body information
        
    Returns:
        Tuple[str, str, Dict[str, str]]: A tuple containing:
            - text_content: Plain text body of the email
            - html_content: HTML body of the email
            - headers: Dictionary of decoded header values with lowercase keys
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
    
    Converts a raw Gmail API message response into a cleaner, structured format
    by extracting headers, parsing dates, and decoding message content (both text
    and HTML parts).
    
    Args:
        message_data: Dict[str, Any]: The Gmail API message data as returned by
            the API's users.messages.get method with format='full'
        
    Returns:
        Dict[str, Any]: Structured message data with the following keys:
            - id: Message ID
            - thread_id: Thread ID
            - from: Sender address
            - to: Recipient address(es)
            - cc: CC address(es)
            - bcc: BCC address(es)
            - subject: Email subject
            - date: ISO format date string
            - message_id: Message-ID header
            - body_text: Plain text content
            - body_html: HTML content
            - labels: List of Gmail labels
            - snippet: Short preview of message content
            - headers: Dictionary of all headers
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