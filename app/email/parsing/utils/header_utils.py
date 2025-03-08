"""
Utilities for handling email headers, including decoding and sanitization.

This module provides comprehensive functions for processing email headers,
including decoding MIME-encoded headers, extracting header values from
email message objects, and sanitizing text.

Example:
    ```python
    from app.email.parsing.utils.header_utils import decode_header
    
    subject = decode_header("=?utf-8?B?SGVsbG8gV29ybGQ=?=")
    # Returns: "Hello World"
    ```
"""

import email.header
import re
import base64
import quopri
import logging

logger = logging.getLogger(__name__)

def sanitize_text(text: str) -> str:
    """
    Clean and sanitize extracted text.
    
    Removes redundant whitespace and trims the text.
    
    Args:
        text: Input text to be sanitized
        
    Returns:
        str: Cleaned and sanitized text
        
    Examples:
        >>> sanitize_text("  Hello   World  ")
        "Hello World"
        >>> sanitize_text("")
        ""
    """
    if not text:
        return ''
    return ' '.join(text.split()).strip()

def safe_extract_header(msg: email.message.Message, header: str) -> str:
    """
    Safely extract email headers with fallback.
    
    Extracts a header value from an email message, handling decoding and
    fallback to empty string if the header doesn't exist or extraction fails.
    
    Args:
        msg: Email message object
        header: Header name to extract
        
    Returns:
        str: Extracted and decoded header value or empty string
        
    Examples:
        >>> safe_extract_header(msg, 'Subject')
        "Re: Meeting tomorrow"
        >>> safe_extract_header(msg, 'X-NonExistent')
        ""
    """
    try:
        value = msg[header.lower()]
        if value:
            decoded_header = email.header.decode_header(value)
            header_parts = []
            for part, encoding in decoded_header:
                if isinstance(part, bytes):
                    try:
                        part = part.decode(encoding or 'utf-8')
                    except UnicodeDecodeError:
                        part = part.decode('iso-8859-1')
                else:
                    part = str(part)
                header_parts.append(part)
            value = ''.join(header_parts)
        return sanitize_text(value or '')
    except Exception as e:
        logger.warning(f"Failed to extract {header} header: {e}")
        return ''

def decode_header(header_text: str) -> str:
    """
    Decodes email headers that may contain encoded text.
    
    Handles RFC 2047 encoded words in email headers using multiple decoding
    approaches with comprehensive fallback mechanisms for robustness.
    
    Args:
        header_text: The header text to decode, which may contain
            encoded words in the format "=?charset?encoding?text?="
            
    Returns:
        str: The fully decoded header text
        
    Examples:
        >>> decode_header("=?utf-8?Q?Hello=20World?=")
        "Hello World"
        >>> decode_header("=?utf-8?B?SGVsbG8gV29ybGQ=?=")
        "Hello World"
        >>> decode_header("Regular text")
        "Regular text"
    """
    if not header_text:
        return ""
    
    try:
        # Primary approach: Use email.header make_header
        # This handles multi-part encodings and different character sets
        try:
            decoded_pairs = email.header.decode_header(header_text)
            
            # If we detect any encoded parts, use make_header
            has_encoded_parts = any(charset is not None for _, charset in decoded_pairs)
            
            if has_encoded_parts:
                decoded = str(email.header.make_header(decoded_pairs))
                
                # Check if the decoded result still contains MIME encoding patterns
                if not '=?' in decoded and not '?=' in decoded:
                    return decoded
        except Exception as e:
            logger.debug(f"Primary header decoding failed: {str(e)}")
        
        # Secondary approach: Manual part-by-part decoding
        try:
            decoded_pairs = email.header.decode_header(header_text)
            result_parts = []
            
            for part, charset in decoded_pairs:
                if isinstance(part, bytes):
                    try:
                        # Try with the specified charset first
                        if charset:
                            result_parts.append(part.decode(charset, errors='replace'))
                        else:
                            # Try common encodings in sequence
                            for enc in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
                                try:
                                    decoded_part = part.decode(enc, errors='strict')
                                    result_parts.append(decoded_part)
                                    break
                                except UnicodeDecodeError:
                                    continue
                            else:
                                # If all charset attempts fail, use replace mode
                                result_parts.append(part.decode('utf-8', errors='replace'))
                    except Exception as e:
                        logger.debug(f"Part decoding failed: {str(e)}")
                        # Last resort fallback
                        result_parts.append(part.decode('utf-8', errors='ignore'))
                else:
                    # String parts can be used directly
                    result_parts.append(str(part))
            
            decoded = ' '.join(result_parts).strip()
            if not '=?' in decoded and not '?=' in decoded:
                return decoded
        except Exception as e:
            logger.debug(f"Secondary header decoding failed: {str(e)}")
        
        # Tertiary approach: Try to create a message and get the header
        # This can sometimes handle encodings that the above methods miss
        if '=?' in header_text and '?=' in header_text:
            try:
                # For Subject-like headers
                msg = email.message.Message()
                msg['Subject'] = header_text
                decoded = msg.get('Subject')
                
                # For From-like headers
                if '<' in header_text and '>' in header_text:
                    # Split the display name and email address
                    parts = header_text.split('<', 1)
                    if len(parts) == 2:
                        display_name = parts[0].strip()
                        email_part = '<' + parts[1]
                        
                        # Try to decode just the display name
                        msg = email.message.Message()
                        msg['From'] = display_name
                        decoded_name = msg.get('From')
                        
                        if decoded_name and not decoded_name.startswith('=?'):
                            return decoded_name + ' ' + email_part
                
                # Return the decoded result if it looks good
                if decoded and not decoded.startswith('=?'):
                    return decoded
            except Exception as e:
                logger.debug(f"Message-based decoding failed: {str(e)}")
        
        # Quaternary approach: Direct Base64/QuotedPrintable decoding
        # This is a last-ditch effort for headers that are still encoded
        try:
            # Pattern to match MIME encoded words
            pattern = r'=\?([^?]*)\?([BQ])\?([^?]*)\?='
            
            def decode_match(match):
                """
                Decode a matched MIME encoded word.
                
                Args:
                    match: Regex match object containing the encoded word components
                    
                Returns:
                    str: Decoded text for this match
                """
                charset, encoding, encoded_text = match.groups()
                if encoding.upper() == 'B':
                    # Base64 encoding
                    try:
                        decoded_bytes = base64.b64decode(encoded_text)
                        return decoded_bytes.decode(charset, errors='replace')
                    except Exception:
                        return match.group(0)
                elif encoding.upper() == 'Q':
                    # Quoted-Printable encoding
                    try:
                        # Convert _ to space first (part of Q encoding)
                        text = encoded_text.replace('_', ' ')
                        decoded_bytes = quopri.decodestring(text.encode('ascii', errors='replace'))
                        return decoded_bytes.decode(charset, errors='replace')
                    except Exception:
                        return match.group(0)
                return match.group(0)
            
            # Apply regex substitution to decode all encoded parts
            decoded = re.sub(pattern, decode_match, header_text)
            
            # If we made any progress, return the result
            if decoded != header_text:
                return decoded
        except Exception as e:
            logger.debug(f"Direct encoding decoding failed: {str(e)}")
        
        # If we've tried everything and failed, log it and return original
        if '=?' in header_text and '?=' in header_text:
            logger.warning(f"All decoding methods failed for header: {header_text}")
            
        # Return the raw header as a last resort
        return header_text
        
    except Exception as e:
        logger.warning(f"Header decoding failed completely: {str(e)} for header: {header_text}")
        return str(header_text) 