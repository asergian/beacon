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

# Constants
MIN_EMAIL_LENGTH = 20
SUPPORTED_ENCODINGS = ['utf-8', 'iso-8859-1', 'latin-1']
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$'
REQUIRED_HEADERS = ['From:', 'Subject:']

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
        Extract metadata from a raw email message.
        """
        try:
            # Handle Gmail API format
            if isinstance(raw_email.get('raw_message'), bytes):
                email_msg = email.message_from_bytes(raw_email['raw_message'])
            else:
                self.logger.error("Unsupported email format")
                return None

            # Extract basic headers
            message_id = self._extract_message_id(email_msg)
            
            # Use the raw_email['id'] if available (Gmail API ID), otherwise use the message_id
            email_id = raw_email.get('id', message_id)
            
            headers = {
                'subject': self._decode_header(email_msg.get('subject', '')),
                'from': self._decode_header(email_msg.get('from', '')),
                'to': self._decode_header(email_msg.get('to', '')),
                'date': self._parse_date(email_msg.get('date')),
                'content_type': email_msg.get_content_type()
            }

            # Extract body
            body = self._extract_body(email_msg)
            if not body:
                self.logger.warning(f"No readable body found for email {email_id}")
                body = ""

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

    def _decode_header(self, header: Optional[str]) -> str:
        """Decode email header, handling various encodings."""
        if not header:
            return ""
            
        try:
            decoded_header = email.header.decode_header(header)
            parts = []
            
            for part, charset in decoded_header:
                if isinstance(part, bytes):
                    try:
                        if charset:
                            parts.append(part.decode(charset))
                        else:
                            parts.append(part.decode())
                    except (UnicodeDecodeError, LookupError):
                        # Fallback to utf-8 if specified charset fails
                        try:
                            parts.append(part.decode('utf-8'))
                        except UnicodeDecodeError:
                            # Last resort: ignore errors
                            parts.append(part.decode('utf-8', 'ignore'))
                else:
                    parts.append(str(part))
                    
            return " ".join(parts)
        except Exception as e:
            self.logger.warning(f"Header decode error: {e}")
            return str(header)

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
        """
        Extract the email body, preferring HTML content when available.
        
        Handles multipart messages and different content types.
        """
        html_parts = []
        text_parts = []
        embedded_images = {}
        
        # Updated pattern to match both URLs and email addresses
        url_pattern = r'(https?://[^\s<>"\'\]]+|www\.[^\s<>"\'\]]+|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                
                # Handle embedded images
                if part.get_content_type().startswith('image/'):
                    try:
                        content_id = part.get('Content-ID')
                        if content_id:
                            # Remove angle brackets from Content-ID
                            content_id = content_id.strip('<>')
                            image_data = part.get_payload(decode=True)
                            image_type = part.get_content_type()
                            image_b64 = base64.b64encode(image_data).decode()
                            # Store both the data URI and the content type
                            embedded_images[content_id] = {
                                'data_uri': f"data:{image_type};base64,{image_b64}",
                                'content_type': image_type
                            }
                    except Exception as e:
                        self.logger.warning(f"Image processing error: {e}")
                    continue
                
                if part.get_content_type() == 'text/html':
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        try:
                            decoded = payload.decode(charset)
                        except (UnicodeDecodeError, LookupError):
                            decoded = payload.decode('utf-8', 'ignore')
                        html_parts.append(decoded)
                    except Exception as e:
                        self.logger.warning(f"HTML part decode error: {e}")
                        continue
                elif part.get_content_type() == 'text/plain':
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        try:
                            decoded = payload.decode(charset)
                        except (UnicodeDecodeError, LookupError):
                            decoded = payload.decode('utf-8', 'ignore')
                        text_parts.append(decoded)
                    except Exception as e:
                        self.logger.warning(f"Text part decode error: {e}")
                        continue
        else:
            # Handle non-multipart messages
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or 'utf-8'
                try:
                    decoded = payload.decode(charset)
                except (UnicodeDecodeError, LookupError):
                    decoded = payload.decode('utf-8', 'ignore')
                
                if msg.get_content_type() == 'text/html':
                    html_parts.append(decoded)
                else:
                    text_parts.append(decoded)
            except Exception as e:
                self.logger.warning(f"Body decode error: {e}")
        
        # Process the content
        if html_parts:
            html_content = "\n".join(html_parts)
            
            # Replace embedded image references while preserving links
            for cid, image_info in embedded_images.items():
                # Look for both simple img tags and linked img tags with various quote styles
                patterns = [
                    # <a> with <img> using cid: format
                    (r'<a([^>]*)><img([^>]*)src=["\']?cid:' + re.escape(cid) + r'["\']?([^>]*)></a>',
                     r'<a\1><img\2src="' + image_info['data_uri'] + r'"\3></a>'),
                    # <a> with <img> using just cid format
                    (r'<a([^>]*)><img([^>]*)src=["\']?' + re.escape(cid) + r'["\']?([^>]*)></a>',
                     r'<a\1><img\2src="' + image_info['data_uri'] + r'"\3></a>'),
                    # Standalone <img> using cid: format
                    (r'<img([^>]*)src=["\']?cid:' + re.escape(cid) + r'["\']?([^>]*)>',
                     r'<img\1src="' + image_info['data_uri'] + r'"\2>'),
                    # Standalone <img> using just cid format
                    (r'<img([^>]*)src=["\']?' + re.escape(cid) + r'["\']?([^>]*)>',
                     r'<img\1src="' + image_info['data_uri'] + r'"\2>')
                ]
                
                for pattern, replacement in patterns:
                    html_content = re.sub(pattern, replacement, html_content)
            
            # Handle external images
            html_content = re.sub(
                r'<img([^>]*?)src=["\']?(https?://[^"\'\s>]+)["\']?([^>]*?)>',
                r'<img\1src="\2"\3 loading="lazy" referrerpolicy="no-referrer">',
                html_content
            )
            
            return html_content
        elif text_parts:
            # Convert plain text to HTML with preserved formatting and clickable links
            text_content = "\n".join(text_parts)
            
            # Remove extra blank lines while preserving paragraph structure
            text_content = re.sub(r'\n{3,}', '\n\n', text_content)
            
            # Escape HTML special characters while preserving newlines
            text_content = escape(text_content)
            
            # Convert URLs and email addresses to clickable links with appropriate href
            text_content = re.sub(
                url_pattern,
                lambda m: (
                    f'<a href="mailto:{m.group(0)}" target="_blank" rel="noopener noreferrer">{m.group(0)}</a>'
                    if '@' in m.group(0)
                    else (
                        f'<a href="{"http://" if m.group(0).startswith("www.") else ""}{m.group(0)}" '
                        f'target="_blank" rel="noopener noreferrer">{m.group(0)}</a>'
                    )
                ),
                text_content
            )
            
            # Convert newlines to <br> tags, preserving paragraphs
            paragraphs = text_content.split('\n\n')
            formatted_paragraphs = []
            for para in paragraphs:
                if para.strip():
                    # Replace single newlines with <br> within paragraphs
                    formatted_para = para.replace('\n', '<br>')
                    formatted_paragraphs.append(f'<p>{formatted_para}</p>')
            
            text_content = '\n'.join(formatted_paragraphs)
            
            return f"""
                <div style='
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    line-height: 1.4;
                    color: #2c3338;
                    padding: 8px;
                '>
                    {text_content}
                </div>
            """
        else:
            return ""

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