"""Gmail subprocess for memory-isolated email processing.

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
  python gmail_subprocess.py --credentials @/path/to/creds --user_email user@gmail.com 
                            --query "after:2023/01/01" --days_back 7
"""

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

# Set more aggressive garbage collection thresholds
# This helps reclaim memory more frequently
gc.set_threshold(700, 10, 5)  # Default is (700, 10, 10)

# Import memory utilities for consistent memory tracking
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))
from app.utils.memory_utils import get_process_memory, log_memory_usage, log_memory_cleanup

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
from googleapiclient.http import HttpRequest
import googleapiclient.discovery_cache
from googleapiclient.http import HttpError
from googleapiclient.discovery_cache.base import Cache
import httplib2
from google.auth.transport.requests import Request as AuthRequest

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
        service = build('gmail', 'v1', credentials=credentials, cache=MemoryCache())
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


async def fetch_and_process_emails(service, user_email, query, include_spam_trash=False, cutoff_time=None):
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
            includeSpamTrash=include_spam_trash
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
        # Decrease batch size from 25 to 10 to reduce memory peaks
        batch_size = 10
        batches = [messages[i:i+batch_size] for i in range(0, len(messages), batch_size)]
        
        all_results = []
        filtered_out = 0
        
        # Process each batch
        for batch_idx, batch in enumerate(batches):
            # Create a batch request properly with a callback dictionary
            batch_results = []
            batch_message_ids = {}
            
            # Force garbage collection before processing batch content
            gc.collect()
            
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
                    if (len(batch_results) % 5 == 0):
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
            
            # Force garbage collection between batches
            gc.collect()
            gc.collect()
            
            # Log memory status after each batch
            if batch_idx == 0 or (batch_idx+1) % 2 == 0:  # Log more frequently
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


async def main(credentials_json, user_email, query, include_spam_trash, days_back):
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
            
        # Build Gmail service
        service = await create_gmail_service(credentials_data)
        
        # Calculate date cutoff for filtering
        local_tz = datetime.now().astimezone().tzinfo
        if days_back > 0:
            # Adjust days_back to match cache logic (days_back=1 means today only)
            adjusted_days = max(0, days_back - 1)
            
            # Calculate the time range using local timezone
            local_midnight = (datetime.now(local_tz) - timedelta(days=adjusted_days)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            
            # Convert to UTC for filtering
            cutoff_time = local_midnight.astimezone(timezone.utc)
            logger.info(f"Filtering emails with cutoff time: {cutoff_time.isoformat()}")
        else:
            cutoff_time = None
        
        # Fetch and process emails with cutoff time for filtering
        log_memory_usage(logger, "Before Email Processing")
        emails = await fetch_and_process_emails(service, user_email, query, include_spam_trash, cutoff_time)
        
        # Clear service reference
        service = None
        
        # Force garbage collection and log results
        log_memory_cleanup(logger, "After Email Processing")
        
        # Return JSON with success flag and emails
        result = {
            "success": True,
            "emails": emails
        }
        
        # Final memory cleanup
        emails = None
        credentials_data = None
        log_memory_cleanup(logger, "Before Exit")
        
        # Return the result
        print(json.dumps(result))
        
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
    
    try:
        # Log starting memory usage
        logger.info(f"Initial memory usage: {os.popen(f'ps -p {os.getpid()} -o rss=').read().strip()} KB")
        
        # Ensure httplib2 caching is disabled to prevent memory leaks
        httplib2.RETRIES = 1
        
        # Set up signal handler
        def handle_timeout(signum, frame):
            print(json.dumps({
                "error": "Timeout reached while fetching emails",
                "emails": []
            }))
            sys.exit(1)
            
        # Set a timeout (e.g. 5 minutes) to prevent hanging
        signal.signal(signal.SIGALRM, handle_timeout)
        signal.alarm(300)  # 5 minutes timeout
        
        # Run the main function
        asyncio.run(main(
            credentials_json=credentials_json,
            user_email=args.user_email,
            query=args.query,
            include_spam_trash=args.include_spam_trash,
            days_back=args.days_back
        ))
        
    except Exception as e:
        # Print error as JSON response
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