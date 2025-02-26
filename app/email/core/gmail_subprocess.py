"""Gmail API subprocess handler for memory isolation.

This module provides a self-contained script that can be run in a separate
process to handle Gmail API operations, particularly fetching and decoding
emails, which can be memory-intensive operations.
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


async def fetch_and_process_emails(service, user_email, query, include_spam_trash=False):
    """Fetch and process emails from Gmail API.
    
    This function fetches emails from Gmail API, processes them to extract 
    raw message data, and returns a list of processed emails.
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
        
        # Process each batch
        for batch_idx, batch in enumerate(batches):
            # Create a batch request properly with a callback dictionary
            batch_results = []
            batch_message_ids = {}
            
            # Force garbage collection before processing batch content
            gc.collect()
            
            def create_callback(msg_id):
                """Create a callback function that captures the message ID through closure."""
                def callback(request_id, response, exception):
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
                    
                    # Compress the raw message data for transfer
                    compressed_data = gzip.compress(raw_msg, compresslevel=6)
                    # Encode as base64 for JSON serialization and add prefix
                    compressed_b64 = base64.b64encode(compressed_data).decode('utf-8')
                    compressed_with_prefix = f"COMPRESSED:{compressed_b64}"
                    
                    # Log compression stats for the first few emails
                    if EMAILS_PROCESSED <= 3:
                        original_size = len(raw_msg)
                        compressed_size = len(compressed_data)
                        compression_ratio = (original_size - compressed_size) / original_size * 100 if original_size > 0 else 0
                        logger.debug(
                            f"Email {msg_id}: Original: {original_size/1024:.1f}KB, "
                            f"Compressed: {compressed_size/1024:.1f}KB, Ratio: {compression_ratio:.1f}%"
                        )
                    
                    # Extract minimal headers - we'll do full parsing in the main process
                    # to avoid duplicating the memory overhead
                    headers = {
                        'subject': email_msg.get('subject', ''),
                        'from': email_msg.get('from', ''),
                        'to': email_msg.get('to', ''),
                        'date': email_msg.get('date', '')
                    }
                    
                    # Process and add to results - only keep essential fields
                    result = {
                        'id': msg_id,
                        'threadId': response.get('threadId', ''),
                        'labelIds': response.get('labelIds', []),
                        'raw_message': compressed_with_prefix,  # Use compressed data
                        # Include a minimal snippet to help with display
                        'snippet': response.get('snippet', '')
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
            f"Successfully retrieved {EMAILS_PROCESSED} emails\n"
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


async def main(credentials_json, user_email, query, include_spam_trash):
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
        
        # Fetch and process emails
        log_memory_usage(logger, "Before Email Processing")
        emails = await fetch_and_process_emails(service, user_email, query, include_spam_trash)
        
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
            include_spam_trash=args.include_spam_trash
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