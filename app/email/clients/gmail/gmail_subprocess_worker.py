"""Gmail worker process for memory-isolated email processing.

This module provides a self-contained process for fetching and processing emails from 
the Gmail API. It's designed to run as a separate process to isolate memory-intensive
operations from the main application process. The subprocess handles all raw email
data processing and returns only the parsed metadata and content to the main process,
significantly reducing memory usage in the parent process.

Key features:
- Complete Gmail API interaction
- Raw email parsing and content extraction
- Memory isolation from main process
- Efficient data filtering and processing

Typical usage:
  python gmail_subprocess_worker.py --credentials @/path/to/creds --user_email user@gmail.com 
                            --query "after:2023/01/01" --days_back 7
"""

# Import standard library modules
import argparse
import asyncio
import base64
import gc
import json
import logging
import os
import signal
import sys
import time
import gzip
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Any
from functools import lru_cache
import email.header
import quopri
import re
import email.utils
import platform
import socket
from zoneinfo import ZoneInfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Set more aggressive garbage collection thresholds
# This helps reclaim memory more frequently
gc.set_threshold(700, 10, 5)  # Default is (700, 10, 10)

# Import memory utilities for consistent memory tracking
# First make sure we can import from the main app
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    # Print debugging info to help diagnose import issues
    print(f"Python path: {sys.path}", file=sys.stderr)
    from app.utils.memory_profiling import get_process_memory, log_memory_usage, log_memory_cleanup
    print("Successfully imported memory_profiling", file=sys.stderr)
except ImportError as e:
    # Print detailed import error information and use fallback functions
    print(f"Import error: {e}", file=sys.stderr)
    print(f"Failed to import from app.utils.memory_profiling", file=sys.stderr)
    print(f"Current directory: {os.getcwd()}", file=sys.stderr)
    print(f"__file__: {__file__}", file=sys.stderr)
    
    # Define fallback functions if imports fail
    def get_process_memory():
        return 0
    
    def log_memory_usage(logger=None, message=None):
        if logger and message:
            logger.info(f"{message} (memory tracking unavailable)")
        return 0
    
    def log_memory_cleanup(logger=None, message=None):
        if logger and message:
            logger.info(f"{message} (memory cleanup unavailable)")
        gc.collect()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger('gmail_subprocess')

# Track memory usage globally
TOTAL_PROCESSED_BYTES = 0
EMAILS_PROCESSED = 0
MAX_EMAIL_SIZE = 0

# Log initial memory usage
log_memory_usage(logger, "Subprocess Start")

# Import Google API libraries - These are heavy imports
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.discovery_cache.base import Cache
import httplib2
from google.auth.transport.requests import Request as AuthRequest

# Set lower connection timeout for faster failure/retry
socket.setdefaulttimeout(10)  # 10 seconds instead of default 60

class MemoryCache(Cache):
    """In-memory cache for Gmail API discovery document."""
    _CACHE = {}  # Process-local cache

    def get(self, url):
        return self._CACHE.get(url)

    def set(self, url, content):
        self._CACHE[url] = content


class GmailAPIError(Exception):
    """Exception raised for Gmail API-related errors."""
    pass


class RateLimitError(GmailAPIError):
    """Exception raised when hitting Gmail API rate limits."""
    pass


async def create_gmail_service(creds_data: Dict) -> any:
    """Create a Gmail API service using the provided credentials."""
    try:
        # Create credentials object
        credentials = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data['refresh_token'],
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )
        
        # Refresh if needed
        if credentials.expired:
            logger.info("Refreshing expired credentials")
            credentials.refresh(AuthRequest())
        
        # Build the service
        service = build('gmail', 'v1', 
                        credentials=credentials,
                        static_discovery=True,
                        cache=MemoryCache())
        return service
    
    except Exception as e:
        logger.error(f"Failed to create Gmail service: {e}")
        raise GmailAPIError(f"Failed to create Gmail service: {e}")


def decode_header(header_text):
    """
    Decodes email headers that may contain encoded words (RFC 2047).
    
    This function implements a multi-stage approach to header decoding:
    1. Tries email.header.make_header for standard decoding
    2. Falls back to part-by-part decoding with multiple charsets
    3. Attempts direct Base64/QuotedPrintable decoding as last resort
    
    Args:
        header_text (str): The header text to decode
        
    Returns:
        str: The decoded header text with all encoding artifacts removed
    """
    if not header_text:
        return ""
        
    try:
        # Primary approach: Use email.header.make_header
        decoded_pairs = email.header.decode_header(header_text)
        decoded = str(email.header.make_header(decoded_pairs))
        
        # Check if we still have MIME encoding patterns
        if not '=?' in decoded and not '?=' in decoded:
            return decoded
        
        # Secondary approach: Part-by-part decoding
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
                                decoded_part = part.decode(enc)
                                result_parts.append(decoded_part)
                                break
                            except UnicodeDecodeError:
                                continue
                        else:
                            # If all charset attempts fail, use replace mode
                            result_parts.append(part.decode('utf-8', errors='replace'))
                except Exception:
                    # Last resort fallback
                    result_parts.append(part.decode('utf-8', errors='ignore'))
            else:
                # String parts can be used directly
                result_parts.append(str(part))
        
        decoded = ' '.join(result_parts).strip()
        if not '=?' in decoded and not '?=' in decoded:
            return decoded
            
        # Tertiary approach: Direct Base64/QuotedPrintable decoding
        if '=?' in header_text and '?=' in header_text:
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
        logger.debug(f"Header decoding failed completely: {e}")
    
    # Last resort, return the original
    return header_text


async def fetch_and_process_emails(service, user_email, query, include_spam_trash=False, cutoff_time=None, max_results=100):
    """Fetch and process emails from Gmail API.
    
    This function fetches emails from Gmail API, processes them to extract 
    necessary metadata and content, and returns only the parsed data (not raw messages).
    It handles date filtering, attachment detection, and content extraction.
    
    Args:
        service: Gmail API service object
        user_email: Email address of the user
        query: Gmail search query string
        include_spam_trash: Whether to include emails from spam and trash
        cutoff_time: Optional datetime to filter emails by date
        max_results: Maximum number of results to fetch
    
    Returns:
        list: List of processed email dictionaries containing metadata and content 
              but NOT the raw message data
              
    Note:
        This function explicitly avoids returning raw message data to reduce
        memory usage in the calling process. All necessary content extraction
        happens within this function.
    """
    global TOTAL_PROCESSED_BYTES, EMAILS_PROCESSED, MAX_EMAIL_SIZE
    
    try:
        # Fetch emails matching the query
        messages_resource = service.users().messages()
        
        # Initial request to get messages
        request = messages_resource.list(
            userId=user_email,
            q=query,
            includeSpamTrash=include_spam_trash,
            maxResults=max_results  # Use passed parameter instead of args
        )
        
        # Fetch all matching message IDs
        messages = []
        while request:
            log_memory_usage(logger, "Before Email Fetching")
            response = request.execute()
            msgs = response.get('messages', [])
            messages.extend(msgs)
            
            # Get next page if available
            request = messages_resource.list_next(request, response)
            
            # Log progress
            logger.info(f"Found {len(messages)} emails matching the query")
            
            # Break early if no results
            if not messages:
                break
        
        if not messages:
            logger.info("No emails found matching the criteria")
            return []
            
        # Process emails in smaller batches to limit memory usage
        # Increase batch size from 10 to 25 emails for better throughput
        batch_size = 25
        batches = [messages[i:i+batch_size] for i in range(0, len(messages), batch_size)]
        
        all_results = []
        filtered_out = 0
        
        # Process each batch
        for batch_idx, batch in enumerate(batches):
            # Create a batch request properly with a callback dictionary
            batch_results = []
            batch_message_ids = {}
            
            # Only do garbage collection after every 2 batches instead of every batch
            if batch_idx % 2 == 0:
                gc.collect()
            
            # Log memory status every 4th batch instead of every batch
            if batch_idx % 4 == 0:
                log_memory_usage(logger, f"Processing batch {batch_idx+1}/{len(batches)}")
            else:
                logger.debug(f"Processing batch {batch_idx+1}/{len(batches)}")
            
            def create_callback(msg_id):
                """Creates a callback function for processing each email.
                
                Args:
                    msg_id: The email ID to process
                    
                Returns:
                    function: A callback function to handle the API response
                """
                def callback(request_id, response, exception):
                    """Process a single email response from the Gmail API.
                    
                    This callback extracts metadata and content from the email without
                    returning the raw message to the main process, which significantly
                    reduces memory usage.
                    
                    Args:
                        request_id: The ID of the batch request
                        response: The Gmail API response
                        exception: Exception if the request failed
                    """
                    if exception:
                        logger.warning(f"Error fetching message {msg_id}: {exception}")
                        return
                    
                    # Skip if message fetch failed
                    if not response:
                        logger.warning(f"Skipping message {msg_id} due to fetch error")
                        return
                    
                    # Get raw message data
                    raw_data = response.get('raw', '')
                    if not raw_data:
                        logger.warning(f"No raw data for message {msg_id}")
                        return
                    
                    # Decode base64 data to bytes
                    raw_msg = base64.urlsafe_b64decode(raw_data)
                    
                    # Update byte counters
                    msg_size = len(raw_msg)
                    global TOTAL_PROCESSED_BYTES, EMAILS_PROCESSED, MAX_EMAIL_SIZE
                    TOTAL_PROCESSED_BYTES += msg_size
                    EMAILS_PROCESSED += 1
                    MAX_EMAIL_SIZE = max(MAX_EMAIL_SIZE, msg_size)
                    
                    # Parse email message - this is the most memory-intensive part
                    email_msg = message_from_bytes(raw_msg)
                    
                    # Extract date for filtering
                    date_str = email_msg.get('date', '')
                    email_date = None
                    if date_str:
                        try:
                            email_date = parsedate_to_datetime(date_str)
                            # Ensure date is in UTC for consistent comparison
                            if email_date.tzinfo is None:
                                email_date = email_date.replace(tzinfo=timezone.utc)
                            else:
                                email_date = email_date.astimezone(timezone.utc)
                        except Exception as e:
                            logger.warning(f"Failed to parse date '{date_str}': {e}")
                    
                    # Apply time filtering if cutoff_time is provided
                    if cutoff_time and email_date and email_date < cutoff_time:
                        nonlocal filtered_out
                        filtered_out += 1
                        logger.debug(f"Filtering out email {msg_id} with date {email_date} (before {cutoff_time})")
                        return
                    
                    # Extract headers with special handling for From field
                    headers = {
                        'subject': decode_header(email_msg.get('subject', '')),
                        'to': decode_header(email_msg.get('to', '')),
                        'date': date_str,
                        'parsed_date': email_date.isoformat() if email_date else None
                    }
                    
                    # Special handling for From field which often has display name + email address
                    from_header = email_msg.get('from', '')
                    if from_header:
                        # First try standard decoding
                        decoded_from = decode_header(from_header)
                        
                        # If it still contains encoded parts, try special handling
                        if '=?' in decoded_from and '?=' in decoded_from:
                            try:
                                # Parse into name and address
                                name, addr = email.utils.parseaddr(from_header)
                                
                                # Decode just the name part
                                decoded_name = decode_header(name)
                                
                                # Reconstruct the From header
                                if addr:
                                    if decoded_name:
                                        headers['from'] = f"{decoded_name} <{addr}>"
                                    else:
                                        headers['from'] = addr
                                else:
                                    headers['from'] = decoded_from
                            except Exception:
                                # Fall back to the standard decoded version
                                headers['from'] = decoded_from
                        else:
                            headers['from'] = decoded_from
                    else:
                        headers['from'] = ''
                    
                    # Extract plain text content and HTML content if available
                    plain_text = ""
                    html_content = ""
                    has_attachments = False
                    
                    if email_msg.is_multipart():
                        for part in email_msg.walk():
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition"))
                            
                            # Check for attachments
                            if "attachment" in content_disposition:
                                has_attachments = True
                                continue
                                
                            # Get the payload
                            try:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    charset = part.get_content_charset() or 'utf-8'
                                    try:
                                        decoded_payload = payload.decode(charset, errors='replace')
                                        
                                        if content_type == 'text/plain':
                                            plain_text = decoded_payload
                                        elif content_type == 'text/html':
                                            html_content = decoded_payload
                                    except Exception as e:
                                        logger.warning(f"Failed to decode payload: {e}")
                            except Exception as e:
                                logger.warning(f"Error processing email part: {e}")
                    else:
                        # Not multipart - just get the content directly
                        try:
                            payload = email_msg.get_payload(decode=True)
                            if payload:
                                charset = email_msg.get_content_charset() or 'utf-8'
                                try:
                                    decoded_payload = payload.decode(charset, errors='replace')
                                    
                                    if email_msg.get_content_type() == 'text/plain':
                                        plain_text = decoded_payload
                                    elif email_msg.get_content_type() == 'text/html':
                                        html_content = decoded_payload
                                except Exception as e:
                                    logger.warning(f"Failed to decode payload: {e}")
                        except Exception as e:
                            logger.warning(f"Error processing email payload: {e}")
                    
                    # Process and add to results - create a complete processed result
                    # Note: raw_message is intentionally not included to reduce memory usage
                    result = {
                        'id': msg_id,
                        'threadId': response.get('threadId', ''),
                        'labelIds': response.get('labelIds', []),
                        # 'raw_message': raw_base64,  # Removed: no longer sending raw message
                        'snippet': response.get('snippet', ''),
                        'body_text': plain_text,
                        'body_html': html_content,
                        'parsed_date': email_date.isoformat() if email_date else None,
                        'has_attachments': has_attachments,
                    }
                    
                    # Add extracted headers
                    result.update(headers)
                    
                    batch_results.append(result)
                    
                    # Clear large objects explicitly
                    raw_msg = None
                    email_msg = None
                    compressed_data = None
                    compressed_b64 = None
                    headers = None
                    
                    # Free individual message memory more aggressively
                    if (len(batch_results) % 10 == 0):  # Changed from 5 to 10
                        gc.collect()
                
                return callback
            
            # Create batch request with per-request callbacks
            batch_request = service.new_batch_http_request()
            
            # Add each message to the batch request with its own callback
            for message in batch:
                msg_id = message['id']
                # Add request to batch with a callback specific to this message
                request = messages_resource.get(
                    userId=user_email, 
                    id=msg_id, 
                    format='raw'
                )
                # Add the request to the batch with a callback that knows which message ID this is
                batch_request.add(request, callback=create_callback(msg_id))
            
            # Execute batch and get responses through callbacks
            try:
                # Execute the batch request - responses will go to callbacks
                batch_request.execute()
                
            except Exception as e:
                logger.error(f"Error executing batch request: {e}")
            
            # Add this batch's results to the overall results
            all_results.extend(batch_results)
            
            # Clear batch data
            batch_results = None
            
            # Force garbage collection between batches - only once is sufficient
            gc.collect()
            
            # Log memory status after each batch - reduce frequency for speed
            if batch_idx == 0 or (batch_idx+1) % 4 == 0:  # Log less frequently (every 4th batch)
                log_memory_usage(logger, f"After Batch {batch_idx+1}/{len(batches)}")
        
        # Clear batches data
        batches = None
        messages = None
        
        # Log memory usage after fetching
        log_memory_usage(logger, "After Fetching All Emails")
        
        # Log stats about the data we processed
        avg_size = TOTAL_PROCESSED_BYTES / EMAILS_PROCESSED if EMAILS_PROCESSED > 0 else 0
        logger.info(
            f"Successfully retrieved {EMAILS_PROCESSED} emails, filtered out {filtered_out}\n"
            f"    Total data processed: {TOTAL_PROCESSED_BYTES/1024/1024:.2f} MB\n"
            f"    Average email size: {avg_size/1024:.1f} KB\n"
            f"    Largest email: {MAX_EMAIL_SIZE/1024:.1f} KB"
        )
        
        # Final cleanup before returning
        log_memory_cleanup(logger, "Before Returning Results")
        
        return all_results
        
    except Exception as e:
        logger.error(f"Error fetching emails: {e}")
        return []


async def send_email_with_retry(service, to: str, subject: str, content: str, cc: List[str] = None, 
                                 bcc: List[str] = None, html_content: str = None, max_retries: int = 3) -> Dict:
    """
    Send an email with retry logic in case of temporary failures.
    
    Args:
        service: The Gmail API service object
        to: Recipient email address(es)
        subject: Email subject
        content: Plain text content
        cc: Optional CC recipients
        bcc: Optional BCC recipients
        html_content: Optional HTML content
        max_retries: Maximum number of retry attempts
        
    Returns:
        Dict: Response containing message ID and other details
    """
    retries = 0
    last_error = None
    
    while retries < max_retries:
        try:
            # Try sending the email
            result = await send_email_with_gmail_api(service, to, subject, content, cc, bcc, html_content)
            # If successful, return the result
            return result
        except Exception as e:
            last_error = e
            retries += 1
            
            # Check for rate limit errors specifically
            error_str = str(e).lower()
            if "quota" in error_str or "rate limit" in error_str or "too many requests" in error_str:
                wait_time = 2 ** retries  # Exponential backoff
                logger.warning(f"Hit rate limit, retry {retries}/{max_retries} after {wait_time}s delay")
                await asyncio.sleep(wait_time)
            elif "invalid credentials" in error_str:
                # No point retrying credential issues
                logger.error("Invalid credentials error, not retrying")
                break
            else:
                # For other errors, retry with a small delay
                logger.warning(f"Email send failed, retry {retries}/{max_retries}: {e}")
                await asyncio.sleep(1)
    
    # If we get here, all retries failed
    error_msg = f"Failed to send email after {max_retries} attempts: {last_error}"
    logger.error(error_msg)
    raise GmailAPIError(error_msg)


async def send_email_with_gmail_api(service, to: str, subject: str, content: str, cc: List[str] = None, 
                                    bcc: List[str] = None, html_content: str = None) -> Dict:
    """
    Send an email using the Gmail API.
    
    Args:
        service: The Gmail API service object
        to: Recipient email address(es) - comma-separated string or single address
        subject: Email subject
        content: Plain text email content
        cc: Optional list of CC recipients
        bcc: Optional list of BCC recipients
        html_content: Optional HTML content (if not provided, plain text content will be used)
        
    Returns:
        Dict: Response containing message ID and other details
        
    Raises:
        GmailAPIError: If the email sending fails
    """
    try:
        # Get user's email address
        user_profile = service.users().getProfile(userId='me').execute()
        sender_email = user_profile.get('emailAddress')
        logger.info(f"Sending email as user: {sender_email}")
        
        # Create message
        message = MIMEMultipart('alternative')
        message['to'] = to
        message['subject'] = subject
        message['from'] = sender_email  # Add explicit From header
        
        # Add CC if provided
        if cc:
            if isinstance(cc, list):
                message['cc'] = ','.join(cc)
            else:
                message['cc'] = cc
                
        # Add BCC if provided
        if bcc:
            if isinstance(bcc, list):
                message['bcc'] = ','.join(bcc)
            else:
                message['bcc'] = bcc
        
        # Attach plain text part
        plain_part = MIMEText(content, 'plain')
        message.attach(plain_part)
        
        # Attach HTML part if provided
        if html_content:
            html_part = MIMEText(html_content, 'html')
            message.attach(html_part)
        
        # Log full MIME message headers for debugging
        logger.debug(f"MIME message headers: {dict(message.items())}")
        
        # Encode the message for the Gmail API
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Create the message body for the API
        message_body = {
            'raw': encoded_message
        }
        
        # Send the message
        logger.info(f"Sending email from {sender_email} to {to} with subject: {subject}")
        response = service.users().messages().send(userId='me', body=message_body).execute()
        
        # Log the full API response for debugging
        logger.info(f"Gmail API response: {response}")
        logger.info(f"Email sent successfully. Message ID: {response.get('id')}")
        logger.info(f"Thread ID: {response.get('threadId')}")
        logger.info(f"Label IDs: {response.get('labelIds', [])}")
        
        # Check if SENT label is in the response
        label_ids = response.get('labelIds', [])
        if 'SENT' not in label_ids:
            logger.warning(f"SENT label not found in response labels: {label_ids}")
            
            # Try to manually add message to SENT label
            try:
                logger.info(f"Attempting to manually add message to SENT label")
                modify_response = service.users().messages().modify(
                    userId='me',
                    id=response.get('id'),
                    body={'addLabelIds': ['SENT']}
                ).execute()
                logger.info(f"Modified message labels: {modify_response}")
            except Exception as label_error:
                logger.error(f"Failed to add SENT label: {label_error}")
        
        return {
            'success': True,
            'message_id': response.get('id'),
            'thread_id': response.get('threadId'),
            'label_ids': response.get('labelIds', []),
            'sender': sender_email
        }
        
    except Exception as e:
        error_msg = f"Failed to send email via Gmail API: {str(e)}"
        logger.error(error_msg)
        raise GmailAPIError(error_msg)


async def main(credentials_json, user_email, query, include_spam_trash, days_back, max_results=100, user_timezone='US/Pacific'):
    """Main function to run Gmail API operations."""
    try:
        # Get credentials from JSON file or direct JSON string
        if credentials_json.startswith('@'):
            # It's a file path
            file_path = credentials_json[1:]
            with open(file_path, 'r') as f:
                credentials_data = json.load(f)
        else:
            # It's a JSON string
            credentials_data = json.loads(credentials_json)
            
        # Set thread count for better performance
        if hasattr(gc, 'set_threshold'):
            # Use more conservative GC settings for better performance
            original_threshold = gc.get_threshold()
            # Less aggressive GC for better performance during short-lived process
            gc.set_threshold(900, 15, 15)  # Changed from (700, 10, 10) to be less aggressive
            
        # Build Gmail service
        service = await create_gmail_service(credentials_data)
        
        # Calculate date cutoff for filtering
        if days_back > 0:
            # Adjust days_back to match cache logic (days_back=1 means today only)
            adjusted_days = max(0, days_back - 1)
            
            # Use the user's timezone for date calculations
            try:
                # Create timezone object from string
                user_tz = ZoneInfo(user_timezone)
                logger.info(f"Using user timezone: {user_timezone}")
            except (ImportError, Exception) as e:
                logger.warning(f"Could not use user timezone ({user_timezone}), falling back to US/Pacific: {e}")
                try:
                    user_tz = ZoneInfo('US/Pacific')
                except Exception:
                    user_tz = timezone.utc
            
            # Calculate the time range using user's timezone
            user_now = datetime.now(user_tz)
            cutoff_time = (user_now - timedelta(days=adjusted_days)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            
            logger.info(f"Filtering emails with user timezone ({user_timezone}):\n    User now: {user_now}\n    User timezone cutoff: {cutoff_time}\n    UTC cutoff: {cutoff_time.astimezone(timezone.utc)}")
        else:
            cutoff_time = None
        
        # Fetch and process emails with cutoff time for filtering
        log_memory_usage(logger, "Before Email Processing")
        emails = await fetch_and_process_emails(service, user_email, query, include_spam_trash, cutoff_time, max_results)
        
        # Clear service reference
        service = None
        
        # Force garbage collection and log results
        log_memory_cleanup(logger, "After Email Processing")
        
        # Use ujson for faster JSON serialization if available
        result = {
            "success": True,
            "emails": emails
        }
        
        # Final memory cleanup
        emails = None
        credentials_data = None
        log_memory_cleanup(logger, "Before Exit")
        
        # Return the result - use ujson if available for faster serialization
        try:
            import ujson
            print(ujson.dumps(result))
        except ImportError:
            print(json.dumps(result))
        
        logger.info(f"Using user timezone: {user_timezone} for email filtering")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error: {e}")
        # Return JSON with error flag
        print(json.dumps({
            "success": False,
            "error": str(e)
        }))
        return 1
    finally:
        # Final cleanup
        gc.collect()
        gc.collect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gmail API Client Subprocess")
    parser.add_argument("--credentials", required=True, help="OAuth2 credentials JSON string or @file containing credentials")
    parser.add_argument("--user_email", required=True, help="User email address")
    parser.add_argument("--query", default="", help="Gmail search query")
    parser.add_argument("--include_spam_trash", action="store_true", help="Include emails in spam and trash")
    parser.add_argument("--days_back", type=int, default=1, help="Number of days back to fetch emails")
    parser.add_argument('--max_results', type=int, default=100, help='Maximum number of results to fetch')
    parser.add_argument('--user_timezone', default='US/Pacific', help='User timezone (e.g., "America/New_York")')
    
    # Add new arguments for email sending functionality
    parser.add_argument('--action', choices=['fetch_emails', 'send_email'], default='fetch_emails',
                      help='Action to perform (fetch_emails or send_email)')
    parser.add_argument('--to', help='Recipient email address(es) for send_email action')
    parser.add_argument('--subject', help='Email subject for send_email action')
    parser.add_argument('--content', help='Email content (plain text) or @file path for send_email action')
    parser.add_argument('--html_content', help='Email HTML content or @file path for send_email action')
    parser.add_argument('--cc', help='CC recipients for send_email action')
    parser.add_argument('--bcc', help='BCC recipients for send_email action')
    
    args = parser.parse_args()
    
    # Handle credentials from file (if specified with @)
    credentials_data = args.credentials
    if credentials_data.startswith("@"):
        # Read credentials from file
        file_path = credentials_data[1:]
        with open(file_path, 'r') as f:
            credentials_json = f.read()
    else:
        credentials_json = credentials_data
    
    # Handle content and html_content from file (if specified with @)
    content = args.content
    if content and content.startswith("@"):
        # Read content from file
        file_path = content[1:]
        with open(file_path, 'r') as f:
            content = f.read()
            
    html_content = args.html_content
    if html_content and html_content.startswith("@"):
        # Read HTML content from file
        file_path = html_content[1:]
        with open(file_path, 'r') as f:
            html_content = f.read()
    
    try:
        # Log starting memory usage
        logger.info(f"Initial memory usage: {os.popen(f'ps -p {os.getpid()} -o rss=').read().strip()} KB")
        
        # Ensure httplib2 caching is disabled to prevent memory leaks
        httplib2.RETRIES = 1
        
        # Set up signal handler
        def handle_timeout(signum, frame):
            if args.action == 'send_email':
                print(json.dumps({
                    "success": False,
                    "error": "Timeout reached while processing request",
                }))
            else:
                print(json.dumps({
                    "error": "Timeout reached while fetching emails",
                    "emails": []
                }))
            sys.exit(1)
            
        # Set a timeout (e.g. 5 minutes) to prevent hanging
        signal.signal(signal.SIGALRM, handle_timeout)
        signal.alarm(300)  # 5 minutes timeout
        
        # Set process priority higher on Unix systems
        if platform.system() != 'Windows':
            try:
                os.nice(-15)  # Even higher priority (-20 is highest, 19 is lowest)
                logger.info(f"Set process nice value to -15 for better performance")
            except Exception as e:
                logger.warning(f"Could not set process priority: {e}")
        
        # Handle different actions
        if args.action == 'send_email':
            # Validate required parameters for sending email
            if not args.to or not content:
                print(json.dumps({
                    "success": False,
                    "error": "Missing required parameters for send_email action: to and content"
                }))
                sys.exit(1)
                
            # Execute send_email function
            try:
                # Use asyncio.run for send_email action
                async def send_email_task():
                    logger.info(f"Creating Gmail service for sending email")
                    service = await create_gmail_service(json.loads(credentials_json))
                    logger.info(f"Gmail service created, sending email with retry logic")
                    return await send_email_with_retry(
                        service,
                        to=args.to,
                        subject=args.subject or "",
                        content=content,
                        cc=args.cc,
                        bcc=args.bcc,
                        html_content=html_content
                    )
                
                result = asyncio.run(send_email_task())
                logger.info(f"Email sending completed with result: {result}")
                print(json.dumps(result))
                sys.exit(0)
            except Exception as e:
                logger.error(f"Exception during email sending: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                print(json.dumps({
                    "success": False,
                    "error": str(e)
                }))
                sys.exit(1)
        else:
            # Run the main function for fetch_emails action (original behavior)
            asyncio.run(main(
                credentials_json=credentials_json,
                user_email=args.user_email,
                query=args.query,
                include_spam_trash=args.include_spam_trash,
                days_back=args.days_back,
                max_results=args.max_results,
                user_timezone=args.user_timezone
            ))
            
    except Exception as e:
        # Print error as JSON response
        if args.action == 'send_email':
            print(json.dumps({
                "success": False,
                "error": str(e)
            }))
        else:
            error_response = {
                "error": str(e),
                "emails": []
            }
            print(json.dumps(error_response))
        sys.exit(1)
    finally:
        # Ensure all resources are cleaned up before exit
        try:
            # Force final garbage collection
            gc.collect()
            gc.collect()
            
            # Close any remaining httplib2 connections - safely check for attributes first
            try:
                # Check if httplib2.SCHEMES exists before accessing
                if hasattr(httplib2, 'SCHEMES') and httplib2.SCHEMES:
                    for scheme, conn in httplib2.SCHEMES.items():
                        if hasattr(conn, 'connections'):
                            conn.connections.clear()
                            logger.debug(f"Cleared {scheme} connections")
            except Exception as e:
                logger.warning(f"Could not clean httplib2 connections: {e}")
                
            # Note: httplib2 connections might already be cleaned up by the HTTP request objects
            # Try an alternative cleanup approach for httplib2
            try:
                # For open HTTP connections
                if hasattr(httplib2, 'Http'):
                    for attr in dir(httplib2.Http):
                        if attr.startswith('_conn_') and hasattr(httplib2.Http, attr):
                            setattr(httplib2.Http, attr, {})
                            logger.debug(f"Reset httplib2.Http.{attr}")
            except Exception as e:
                logger.warning(f"Alternative httplib2 cleanup failed: {e}")
                
            # Attempt to free the Google API client
            try:
                if 'service' in globals():
                    try:
                        service_obj = globals()['service']
                        if hasattr(service_obj, '_http') and service_obj._http:
                            # Close any http connections
                            if hasattr(service_obj._http, 'close'):
                                service_obj._http.close()
                    except Exception:
                        pass
                    # Set to None to free reference
                    globals()['service'] = None
            except Exception as e:
                logger.warning(f"Error cleaning up Google API service: {e}")
            
            # Log final memory usage
            logger.info(f"Final memory usage before exit: {os.popen(f'ps -p {os.getpid()} -o rss=').read().strip()} KB")
        except Exception as e:
            logger.error(f"Error during final cleanup: {e}") 