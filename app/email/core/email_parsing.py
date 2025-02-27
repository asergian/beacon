"""
Module for parsing and extracting metadata from email messages.

Provides robust email parsing capabilities with comprehensive 
metadata extraction and error handling.

Typical usage:
    parser = EmailParser()
    metadata = parser.extract_metadata(raw_email)
"""

import logging
import email
from email.parser import BytesParser
from email.policy import default
from email.utils import parseaddr, parsedate_to_datetime
from typing import Dict, Union, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
from dateutil.parser import parse
import re
from ..utils.clean_message_id import clean_message_id
import base64
from html import escape
import email.parser
import email.header

# Constants
MIN_EMAIL_LENGTH = 20
SUPPORTED_ENCODINGS = ['utf-8', 'iso-8859-1', 'latin-1']
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$'
REQUIRED_HEADERS = ['From:', 'Subject:']

# Regular expression to match content between HTML tags
HTML_TAG_PATTERN = re.compile(r'<[^>]*>')
# Match common HTML entities
HTML_ENTITY_PATTERN = re.compile(r'&[a-zA-Z]+;|&#\d+;')

class EmailParsingError(Exception):
    """Exception raised for email parsing-related errors."""
    pass

@dataclass
class EmailMetadata:
    """
    Structured representation of email metadata.

    Attributes:
        id (str): Unique email Message-ID (cleaned)
        subject (str): Email subject
        sender (str): Email sender
        body (str): Email body text
        date (datetime): Email received/sent date
    """
    id: str = ''
    subject: str = ''
    sender: str = ''
    body: str = ''
    date: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self) -> None:
        """Validate metadata after initialization."""
        if not isinstance(self.date, datetime):
            raise ValueError("date must be a datetime object")
        # Clean the Message-ID by removing angle brackets and whitespace
        self.id = self.id.strip().strip('<>') if self.id else ''

class EmailParser:
    """
    A comprehensive email parsing utility.

    Handles various email formats and extracts structured metadata.
    """

    def __init__(self, parser=None):
        """
        Initialize the email parser.

        Args:
            parser: Optional custom email parser (defaults to BytesParser)
        """
        self.parser = parser or BytesParser(policy=default)
        self.logger = logging.getLogger(__name__)

    def _validate_email(self, raw_email: bytes) -> None:
        """
        Validates required headers and email address format
        
        Args:
            raw_email (bytes): Raw email content
        
        Raises:
            EmailParsingError: If email fails validation
        """
        try:
            # Try multiple encodings for decoding
            for encoding in SUPPORTED_ENCODINGS:
                try:
                    msg = email.message_from_bytes(raw_email, policy=default)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # If no encoding works, try with error='ignore'
                try:
                    msg = email.message_from_bytes(raw_email, policy=default)
                except Exception:
                    raise EmailParsingError("Invalid email encoding")
            
            # Check all required headers
            for header in REQUIRED_HEADERS:
                header_name = header.rstrip(':').lower()
                if not msg.get(header_name):
                    raise EmailParsingError(f"Missing {header_name} header")
            
            # Extract and validate email address
            from_header = msg.get('from', '')
            sender_name, sender_email = parseaddr(from_header)
            # print(f"DEBUG - From header: {from_header}")
            # print(f"DEBUG - Parsed sender: {sender_email}")
            
            if not sender_email:
                raise EmailParsingError("Could not extract email address from From header")
                
            if not self._validate_email_address(sender_email):
                raise EmailParsingError(f"Invalid email address format: {sender_email}")
                
        except EmailParsingError:
            raise
        except Exception as e:
            raise EmailParsingError(f"Email parsing failed: {str(e)}")

    def _validate_email_address(self, email_addr: str) -> bool:
        """Validate email address format."""
        if not email_addr:
            return False
        match_result = bool(re.match(EMAIL_REGEX, email_addr))
        # print(f"DEBUG - Validating email: {email_addr}, Result: {match_result}")  # Direct print for debugging
        # print(f"DEBUG - Using regex pattern: {EMAIL_REGEX}")  # Print the pattern being used
        return match_result

    def _extract_message_id(self, msg: email.message.Message) -> str:
        """
        Extract and clean the Message-ID.
        
        Args:
            msg: Email message object
            
        Returns:
            Cleaned Message-ID or generated fallback ID
        """
        message_id = self._safe_extract_header(msg, 'Message-ID')
        if message_id:
            return clean_message_id(message_id)
        
        # Fallback: Generate a unique ID using timestamp and content hash
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        content_hash = str(hash(str(msg)))[:8]
        return f"generated-{timestamp}-{content_hash}"

    def extract_metadata(self, raw_email: Dict[str, Any]) -> Optional[EmailMetadata]:
        """
        Extract metadata from an email dictionary, handling both pre-parsed emails and raw emails.
        
        This method processes email data in two ways:
        1. For pre-parsed emails from the subprocess (preferred): Uses the already extracted
           fields like body_text, body_html, subject, etc.
        2. For raw emails (fallback): Parses the raw_message data to extract metadata
        
        The method prioritizes using pre-parsed data to reduce memory usage and improve
        performance, falling back to raw message parsing only when necessary.
        
        Args:
            raw_email: Dictionary containing email data, either pre-parsed or with raw_message
            
        Returns:
            EmailMetadata object containing structured email information, or None if parsing failed
            
        Note:
            This implementation has been optimized to work without raw_message data,
            relying instead on pre-processed body_text and body_html from the subprocess.
        """
        try:
            # First check if this is a pre-parsed email with all fields already extracted
            # This is the optimized path that avoids raw message processing
            if raw_email and 'id' in raw_email and ('body_text' in raw_email or 'body_html' in raw_email):
                self.logger.debug(f"Processing pre-parsed email: {raw_email.get('id')}")
                
                # Parse date if it's provided as a string
                email_date = raw_email.get('parsed_date')
                if isinstance(email_date, str):
                    try:
                        email_date = datetime.fromisoformat(email_date)
                    except (ValueError, TypeError):
                        email_date = datetime.now()
                elif not isinstance(email_date, datetime):
                    email_date = datetime.now()
                
                # UPDATED: Prefer body_html over body_text to preserve rich formatting
                body = raw_email.get('body_html', '')
                if not body:
                    body = raw_email.get('body_text', '')
                
                # Create metadata with original body
                return EmailMetadata(
                    id=raw_email.get('id', ''),
                    subject=raw_email.get('subject', ''),
                    sender=raw_email.get('from', ''),
                    body=body,
                    date=email_date
                )
            
            # Check if we have a valid raw_message to parse
            if raw_email is None or 'raw_message' not in raw_email or raw_email['raw_message'] is None:
                # Updated error message with more helpful guidance
                self.logger.warning("Email missing raw_message but should have body_text and body_html from subprocess")
                # We should still have the essential fields if preprocessing was done in subprocess
                if raw_email and 'id' in raw_email and ('body_text' in raw_email or 'body_html' in raw_email):
                    # Create minimal metadata from available fields
                    email_id = raw_email.get('id', '')
                    email_date = raw_email.get('parsed_date')
                    if isinstance(email_date, str):
                        try:
                            email_date = datetime.fromisoformat(email_date)
                        except (ValueError, TypeError):
                            email_date = datetime.now()
                    elif not isinstance(email_date, datetime):
                        email_date = datetime.now()
                    
                    # Prefer body_html, fall back to body_text
                    body = raw_email.get('body_html', '') or raw_email.get('body_text', '')
                    
                    return EmailMetadata(
                        id=email_id,
                        subject=raw_email.get('subject', ''),
                        sender=raw_email.get('from', ''),
                        body=body,
                        date=email_date
                    )
                else:
                    self.logger.error("Invalid email data: missing both raw_message and processed content")
                    return None
                    
            # Fallback path for raw message processing - this is the legacy path
            # that should rarely be used now that the subprocess does the parsing
            # Handle Gmail API format - raw_message should be bytes
            raw_message = raw_email.get('raw_message')
            
            if not isinstance(raw_message, bytes):
                self.logger.error(f"Unsupported email format: raw_message must be bytes, got {type(raw_message)}")
                return None
                
            # Parse the raw bytes directly
            email_msg = email.message_from_bytes(raw_message)
            
            # Extract basic headers
            message_id = self._extract_message_id(email_msg)
            
            # Use Gmail API ID from raw_email['id'] as the primary identifier 
            # This is consistent with how GmailClient processes emails
            email_id = raw_email.get('id', '')
            
            # If no Gmail API ID is available, fall back to Message-ID header
            if not email_id:
                email_id = message_id
            
            headers = {
                'subject': self._decode_header(email_msg.get('subject', '')),
                'from': self._decode_header(email_msg.get('from', '')),
                'to': self._decode_header(email_msg.get('to', '')),
                'date': self._parse_date(email_msg.get('date')),
                'content_type': email_msg.get_content_type()
            }

            # Extract body (this preserves HTML structure)
            body = self._extract_body(email_msg)
            if not body:
                self.logger.warning(f"No readable body found for email {email_id}")
                body = ""
            
            # Clear the raw_message reference to free memory immediately
            raw_email['raw_message'] = None
            email_msg = None

            # Create and return EmailMetadata object
            return EmailMetadata(
                id=email_id,
                subject=headers['subject'],
                sender=headers['from'],
                body=body,
                date=headers['date']
            )

        except Exception as e:
            self.logger.error(f"Failed to parse email: {e}")
            # Make sure we clear references even on errors
            if 'raw_message' in raw_email:
                raw_email['raw_message'] = None
            return None

    def _safe_extract_header(self, msg: email.message.Message, header: str) -> str:
        """
        Safely extract email headers with fallback.

        Args:
            msg: Email message object
            header: Header to extract

        Returns:
            Extracted header value or empty string
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
            return self._sanitize_text(value or '')
        except Exception as e:
            self.logger.warning(f"Failed to extract {header} header: {e}")
            return ''

    def _sanitize_text(self, text: str) -> str:
        """Clean and sanitize extracted text."""
        if not text:
            return ''
        return ' '.join(text.split()).strip()

    def _decode_header(self, header_text):
        """
        Decodes email headers that may contain encoded text.
        Returns the decoded text.
        
        Args:
            header_text (str): The header text to decode
            
        Returns:
            str: The decoded header text
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
                self.logger.debug(f"Primary header decoding failed: {str(e)}")
            
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
                            self.logger.debug(f"Part decoding failed: {str(e)}")
                            # Last resort fallback
                            result_parts.append(part.decode('utf-8', errors='ignore'))
                    else:
                        # String parts can be used directly
                        result_parts.append(str(part))
                
                decoded = ' '.join(result_parts).strip()
                if not '=?' in decoded and not '?=' in decoded:
                    return decoded
            except Exception as e:
                self.logger.debug(f"Secondary header decoding failed: {str(e)}")
            
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
                    self.logger.debug(f"Message-based decoding failed: {str(e)}")
            
            # Quaternary approach: Direct Base64/QuotedPrintable decoding
            # This is a last-ditch effort for headers that are still encoded
            try:
                # Look for Base64 encoded sections
                import re
                import base64
                import quopri
                
                # Pattern to match MIME encoded words
                pattern = r'=\?([^?]*)\?([BQ])\?([^?]*)\?='
                
                def decode_match(match):
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
                self.logger.debug(f"Direct encoding decoding failed: {str(e)}")
            
            # If we've tried everything and failed, log it and return original
            if '=?' in header_text and '?=' in header_text:
                self.logger.warning(f"All decoding methods failed for header: {header_text}")
                
            # Return the raw header as a last resort
            return header_text
            
        except Exception as e:
            self.logger.warning(f"Header decoding failed completely: {str(e)} for header: {header_text}")
            return str(header_text)

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse email date string into datetime object."""
        if not date_str:
            return None
            
        try:
            return parsedate_to_datetime(date_str)
        except Exception as e:
            self.logger.warning(f"Date parse error: {e}")
            return None

    def _extract_body(self, msg: email.message.Message) -> str:
        """Extract the body from an email message, handling different content types."""
        body = ""
        html_content = ""
        plain_text = ""

        # Skip messages that don't have a payload
        if not msg or not hasattr(msg, 'get_payload'):
            return ""

        # If the message is multipart
        if msg.is_multipart():
            # Loop through all the message parts
            for part in msg.get_payload():
                # Check for content type
                content_type = part.get_content_type()
                charset = part.get_content_charset()
                
                # Check if this is an attachment
                is_attachment = False
                if part.get_filename():
                    is_attachment = True
                    
                content_disp = part.get('Content-Disposition', '')
                if content_disp and ('attachment' in content_disp or 'inline' in content_disp):
                    is_attachment = True
                    
                # Skip attachments
                if is_attachment:
                    continue
                    
                # Skip empty parts
                if not hasattr(part, 'get_payload'):
                    continue
                    
                # Get the payload
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                
                # Get charset
                if not charset:
                    charset = 'utf-8'  # Assume UTF-8 if not specified
                
                try:
                    decoded_payload = payload.decode(charset, errors='replace')
                    
                    # If this is HTML content
                    if content_type == 'text/html':
                        html_content = decoded_payload
                    
                    # If this is plain text
                    elif content_type == 'text/plain':
                        plain_text = decoded_payload
                except Exception as e:
                    self.logger.warning(f"Error decoding part: {e}")
                    
        else:
            # Handle single part messages
            content_type = msg.get_content_type()
            payload = msg.get_payload(decode=True)
            
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                try:
                    decoded_payload = payload.decode(charset, errors='replace')
                    
                    if content_type == 'text/html':
                        html_content = decoded_payload
                    elif content_type == 'text/plain':
                        plain_text = decoded_payload
                except Exception as e:
                    self.logger.warning(f"Error decoding single part message: {e}")
        
        # Prioritize HTML content over plain text
        if html_content:
            body = html_content
        elif plain_text:
            # Convert plain text to HTML for better display
            # 1. Escape HTML special characters
            import html
            escaped_text = html.escape(plain_text)
            
            # 2. Convert URLs to clickable links
            import re
            url_pattern = r'(https?://[^\s<>"]+|www\.[^\s<>"]+)'
            
            def replace_with_link(match):
                url = match.group(0)
                display_url = url
                
                # Add https:// to www. URLs
                if url.startswith('www.'):
                    url = 'https://' + url
                    
                return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{display_url}</a>'
            
            text_with_links = re.sub(url_pattern, replace_with_link, escaped_text)
            
            # 3. Convert newlines to <br> tags for proper display
            text_with_breaks = text_with_links.replace('\n', '<br>\n')
            
            # 4. Wrap in a div with appropriate styling
            body = f'<div style="font-family: Arial, sans-serif; white-space: pre-wrap;">{text_with_breaks}</div>'
        
        return body

    def _has_attachments(self, msg: email.message.Message) -> bool:
        """Check if the email has any attachments."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                if part.get_content_disposition() and \
                   part.get_content_disposition().startswith('attachment'):
                    return True
        return False
        
    def _strip_html(self, html_content: str) -> str:
        """
        Remove HTML tags and convert common HTML entities to text.
        
        Args:
            html_content: HTML content string
            
        Returns:
            Plain text with HTML tags removed
        """
        if not html_content:
            return ""
            
        # Replace common HTML entities with characters
        text = html_content
        
        # Replace <br>, <p>, <div> tags with newlines for better readability
        text = re.sub(r'<br[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<\/p>\s*<p[^>]*>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<\/div>\s*<div[^>]*>', '\n', text, flags=re.IGNORECASE)
        
        # Remove all remaining HTML tags
        text = HTML_TAG_PATTERN.sub('', text)
        
        # Replace common HTML entities
        entities = {
            '&nbsp;': ' ',
            '&lt;': '<',
            '&gt;': '>',
            '&amp;': '&',
            '&quot;': '"',
            '&apos;': "'",
            '&#39;': "'",
            '&mdash;': '—',
            '&ndash;': '–',
            '&hellip;': '…'
        }
        
        for entity, char in entities.items():
            text = text.replace(entity, char)
        
        # Replace numeric entities (like &#8212;)
        text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()