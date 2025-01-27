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
from email.utils import parseaddr
from typing import Dict, Union, Optional
from datetime import datetime
from dataclasses import dataclass, field
from dateutil.parser import parse
import re
from ..utils.clean_message_id import clean_message_id

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

    def extract_metadata(self, raw_email: Union[bytes, Dict]) -> Optional[EmailMetadata]:
        """
        Extract comprehensive email metadata.

        Args:
            raw_email: Raw email data as bytes or dictionary

        Returns:
            Structured EmailMetadata object if successful, None if parsing fails

        Note:
            Invalid emails will be logged and skipped instead of raising exceptions
        """
        try:
            # Handle different input types
            if not raw_email:
                self.logger.warning("Empty email input - skipping")
                return None
            
            if isinstance(raw_email, bytes):
                if len(raw_email.strip()) == 0:
                    self.logger.warning("Empty email bytes - skipping")
                    return None
                
                try:
                    self._validate_email(raw_email)
                    msg = self.parser.parsebytes(raw_email)
                except EmailParsingError as e:
                    self.logger.warning(f"Email validation failed - skipping: {e}")
                    return None
            
            elif isinstance(raw_email, dict):
                raw_msg = raw_email.get('raw_message')
                if not raw_msg:
                    self.logger.warning("Empty raw_message - skipping")
                    return None
                
                # Handle both bytes and string input for raw_message
                if isinstance(raw_msg, str):
                    raw_msg = raw_msg.encode('utf-8')
                
                try:
                    self._validate_email(raw_msg)
                    msg = self.parser.parsebytes(raw_msg)
                except EmailParsingError as e:
                    self.logger.warning(f"Email validation failed - skipping: {e}")
                    return None
            
            else:
                self.logger.warning(f"Unsupported email format: {type(raw_email)} - skipping")
                return None

            # Extract metadata with robust error handling
            id = self._extract_message_id(msg)
            subject = self._safe_extract_header(msg, 'Subject')
            sender = self._safe_extract_header(msg, 'From')
            body = self._extract_body(msg)
            parsed_date = self._parse_date(msg)

            metadata = EmailMetadata(
                id=id,
                subject=subject,
                sender=sender,
                body=body,
                date=parsed_date
            )

            self.logger.info(f"Successfully parsed email from {sender}")
            return metadata

        except Exception as e:
            self.logger.warning(f"Failed to parse email: {e} - skipping")
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

    def _extract_body(self, msg: email.message.Message) -> str:
        """
        Extract email body, handling various message formats.

        Supports:
        - Plain text and HTML messages
        - Multipart messages (nested)
        - Different character encodings
        - Mixed content types
        
        Args:
            msg: Email message object

        Returns:
            Extracted body text, preferring plain text over HTML
        """
        try:
            text_content = []
            html_content = []
            
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get_content_maintype() == 'text':
                        content = self._decode_payload(part.get_payload(decode=True))
                        charset = part.get_content_charset() or 'utf-8'
                        
                        try:
                            if isinstance(content, bytes):
                                content = content.decode(charset, errors='replace')
                        except (UnicodeDecodeError, LookupError):
                            content = content.decode('utf-8', errors='replace')
                        
                        if part.get_content_subtype() == 'plain':
                            text_content.append(content)
                        elif part.get_content_subtype() == 'html':
                            html_content.append(content)
            else:
                # Handle non-multipart messages
                content = self._decode_payload(msg.get_payload(decode=True))
                charset = msg.get_content_charset() or 'utf-8'
                
                try:
                    if isinstance(content, bytes):
                        content = content.decode(charset, errors='replace')
                except (UnicodeDecodeError, LookupError):
                    content = content.decode('utf-8', errors='replace')
                    
                if msg.get_content_type() == 'text/plain':
                    text_content.append(content)
                elif msg.get_content_type() == 'text/html':
                    html_content.append(content)
            
            # Prefer plain text over HTML content
            if text_content:
                return self._sanitize_text('\n'.join(text_content))
            elif html_content:
                # Basic HTML stripping - you might want to use a proper HTML parser
                html_text = '\n'.join(html_content)
                html_text = re.sub('<[^<]+?>', ' ', html_text)
                return self._sanitize_text(html_text)
            
            return ''
            
        except Exception as e:
            self.logger.error(f"Body extraction error: {e}")
            return ''

    def _decode_payload(self, payload: Optional[bytes]) -> str:
        """Decode email payload with multiple encoding attempts."""
        if not payload:
            return ''
            
        for encoding in SUPPORTED_ENCODINGS:
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
        
        return payload.decode('utf-8', errors='ignore')

    def _parse_date(self, msg: email.message.Message) -> datetime:
        """
        Parse email date with robust error handling.

        Args:
            msg: Email message object

        Returns:
            Parsed datetime or current time
        """
        try:
            date = msg.get('date')
            return parse(date) if date else datetime.now()
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Date parsing error: {e}. Using current time.")
            return datetime.now()