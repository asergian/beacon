"""
Module for parsing and extracting metadata from email messages.

This module provides a comprehensive email parsing implementation with 
robust error handling and metadata extraction. It processes raw email content
into structured metadata objects.

Example:
    ```python
    parser = EmailParser()
    metadata = parser.extract_metadata(raw_email)
    ```

Attributes:
    MIN_EMAIL_LENGTH (int): Minimum length for a valid email message
    SUPPORTED_ENCODINGS (list): List of supported character encodings
    EMAIL_REGEX (str): Regular expression pattern for validating email addresses
    REQUIRED_HEADERS (list): List of required email headers for validation
"""

import logging
import email
from email.parser import BytesParser
from email.policy import default
from email.utils import parseaddr
from typing import Dict, Union, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
import re
from ..utils.message_id_cleaner import clean_message_id

# Import utility modules
from .utils.date_utils import normalize_date, parse_email_date
from .utils.header_utils import decode_header, safe_extract_header, sanitize_text
from .utils.html_utils import strip_html
from .utils.body_extractor import extract_body_content, get_best_body_content, has_attachments

# Constants
MIN_EMAIL_LENGTH = 20
SUPPORTED_ENCODINGS = ['utf-8', 'iso-8859-1', 'latin-1']
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$'
REQUIRED_HEADERS = ['From:', 'Subject:']

class EmailParsingError(Exception):
    """Exception raised for email parsing-related errors.
    
    This exception is used to indicate failures in the email parsing process,
    such as missing required headers or invalid email format.
    
    Attributes:
        message (str): Explanation of the error
    """
    pass

@dataclass
class EmailMetadata:
    """
    Structured representation of email metadata.

    This dataclass encapsulates the essential metadata extracted from an email
    message in a clean, normalized format.

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
        """Validate metadata after initialization.
        
        Performs validation and cleanup of metadata fields after the object
        is initialized. Currently validates the date field and cleans the ID.
        
        Raises:
            ValueError: If date is not a datetime object
        """
        if not isinstance(self.date, datetime):
            raise ValueError("date must be a datetime object")
        # Clean the Message-ID by removing angle brackets and whitespace
        self.id = self.id.strip().strip('<>') if self.id else ''

class EmailParser:
    """
    A comprehensive email parsing utility.

    This class provides methods for validating, parsing, and extracting
    structured metadata from raw email content, handling various email
    formats and encodings.
    
    Attributes:
        parser: Email parser instance for processing raw email data
        logger: Logger instance for tracking parsing events
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
        Validates required headers and email address format.
        
        Performs basic validation checks on an email to ensure it contains
        required headers and a properly formatted email address.
        
        Args:
            raw_email: Raw email content as bytes
        
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
            
            if not sender_email:
                raise EmailParsingError("Could not extract email address from From header")
                
            if not self._validate_email_address(sender_email):
                raise EmailParsingError(f"Invalid email address format: {sender_email}")
                
        except EmailParsingError:
            raise
        except Exception as e:
            raise EmailParsingError(f"Email parsing failed: {str(e)}")

    def _validate_email_address(self, email_addr: str) -> bool:
        """
        Validate email address format using regex pattern.

        Args:
            email_addr: Email address string to validate
            
        Returns:
            bool: True if the email address is valid, False otherwise
        """
        if not email_addr:
            return False
        return bool(re.match(EMAIL_REGEX, email_addr))

    def _extract_message_id(self, msg: email.message.Message) -> str:
        """
        Extract and clean the Message-ID.
        
        Retrieves the Message-ID header from an email message, cleaning
        and normalizing it. Generates a fallback ID if none is found.
        
        Args:
            msg: Email message object
            
        Returns:
            str: Cleaned Message-ID or generated fallback ID
        """
        message_id = safe_extract_header(msg, 'Message-ID')
        if message_id:
            return clean_message_id(message_id)
        
        # Fallback: Generate a unique ID using timestamp and content hash
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        content_hash = str(hash(str(msg)))[:8]
        return f"generated-{timestamp}-{content_hash}"

    def _create_metadata_from_raw_dict(self, raw_email: Dict[str, Any]) -> EmailMetadata:
        """
        Create EmailMetadata object from raw email dictionary.
        
        Converts a dictionary of email data into a structured EmailMetadata
        object, handling date normalization and content selection.
        
        Args:
            raw_email: Dictionary containing email data
            
        Returns:
            EmailMetadata: Structured email metadata object
        """
        email_date = normalize_date(raw_email.get('parsed_date'))
        body = get_best_body_content(raw_email)
        
        return EmailMetadata(
            id=raw_email.get('id', ''),
            subject=raw_email.get('subject', ''),
            sender=raw_email.get('from', ''),
            body=body,
            date=email_date
        )

    def extract_metadata(self, raw_email: Dict[str, Any]) -> Optional[EmailMetadata]:
        """
        Extract metadata from an email dictionary.
        
        This method processes email data in two ways:
        1. For pre-parsed emails: Uses the already extracted fields
        2. For raw emails: Parses the raw_message data to extract metadata
        
        The method prioritizes using pre-parsed data when available.
        
        Args:
            raw_email: Dictionary containing email data, either pre-parsed 
                or with raw_message
            
        Returns:
            Optional[EmailMetadata]: Structured email metadata, or None if parsing failed
            
        Note:
            This implementation is optimized to work without raw_message data,
            relying instead on pre-processed content when available.
        """
        try:
            # First check if this is a pre-parsed email with all fields already extracted
            # This is the optimized path that avoids raw message processing
            if raw_email and 'id' in raw_email and ('body_text' in raw_email or 'body_html' in raw_email):
                self.logger.debug(f"Processing pre-parsed email: {raw_email.get('id')}")
                return self._create_metadata_from_raw_dict(raw_email)
            
            # Check if we have a valid raw_message to parse
            if raw_email is None or 'raw_message' not in raw_email or raw_email['raw_message'] is None:
                # Updated error message with more helpful guidance
                self.logger.warning("Email missing raw_message but should have body_text and body_html from subprocess")
                # We should still have the essential fields if preprocessing was done in subprocess
                if raw_email and 'id' in raw_email and ('body_text' in raw_email or 'body_html' in raw_email):
                    # Create minimal metadata from available fields
                    return self._create_metadata_from_raw_dict(raw_email)
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
                'subject': decode_header(email_msg.get('subject', '')),
                'from': decode_header(email_msg.get('from', '')),
                'to': decode_header(email_msg.get('to', '')),
                'date': parse_email_date(email_msg.get('date')),
                'content_type': email_msg.get_content_type()
            }

            # Extract body (this preserves HTML structure)
            body = extract_body_content(email_msg)
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