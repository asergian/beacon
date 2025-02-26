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
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional

from google.auth.transport.requests import Request as AuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.discovery_cache.base import Cache
import httplib2
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger('gmail_subprocess')

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


async def fetch_and_process_emails(service, user_email, query, include_spam_trash) -> list:
    """Fetch and process emails using the Gmail API service with batch requests.
    
    This function retrieves emails matching the query from Gmail API and processes them
    in batches to limit memory usage. Each batch request processes multiple messages
    in a single HTTP request to improve performance.
    
    Note:
    - Callbacks are registered per request when adding to the batch,
      rather than globally when executing the batch.
    - Raw message data is encoded as base64 text for JSON serialization,
      and must be decoded back to bytes by the client.
    """
    try:
        logger.info(f"Fetching emails for user {user_email} with query: {query}")
        
        # Log memory usage before fetching
        process = os.getpid()
        logger.info(f"Memory usage before fetching: {os.popen(f'ps -p {process} -o rss=').read().strip()} KB")
        
        # Get list of message IDs matching the query
        messages = []
        request = service.users().messages().list(userId=user_email, q=query, includeSpamTrash=include_spam_trash)
        
        while request is not None:
            response = request.execute()
            msg_items = response.get('messages', [])
            
            if not msg_items:
                logger.info("No messages found matching the query.")
                return []
                
            messages.extend(msg_items)
            request = service.users().messages().list_next(request, response)
            
        logger.info(f"Found {len(messages)} emails matching the query")
        
        # Batch size for processing
        batch_size = 25
        results = []
        
        # Process messages in batches to limit memory usage
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1}/{(len(messages) + batch_size - 1) // batch_size} ({len(batch)} messages)")
            
            # Create a batch request
            batch_request = service.new_batch_http_request()
            message_map = {}  # Map request IDs to message IDs
            
            # Add requests to the batch
            for j, msg_item in enumerate(batch):
                msg_id = msg_item['id']
                request_id = f'msg{j}'
                message_map[request_id] = msg_id
                
                # Define callback inline for each request
                def create_callback(req_id):
                    def _callback(request_id, response, exception):
                        if exception:
                            logger.error(f"Error fetching message {message_map.get(req_id)}: {exception}")
                            return
                        responses[req_id] = response
                    return _callback
                
                batch_request.add(
                    service.users().messages().get(userId=user_email, id=msg_id, format='raw'),
                    callback=create_callback(request_id),
                    request_id=request_id
                )
            
            # Execute the batch request
            responses = {}
            
            # Execute without callback parameter
            batch_request.execute()
            
            # Process the batch results
            batch_results = []
            for request_id, msg_id in message_map.items():
                if request_id not in responses:
                    continue
                    
                response = responses[request_id]
                
                try:
                    # Extract raw message
                    raw_msg = base64.urlsafe_b64decode(response['raw'])
                    
                    # Extract headers from the message
                    email_msg = message_from_bytes(raw_msg)
                    
                    # Process and add to results
                    result = {
                        'id': msg_id,
                        'threadId': response.get('threadId', ''),
                        'labelIds': response.get('labelIds', []),
                        'raw_message': base64.b64encode(raw_msg).decode('ascii'),  # Encode as base64 text for JSON serialization
                        'snippet': response.get('snippet', '')
                    }
                    
                    batch_results.append(result)
                    
                    # Clear references to large objects
                    raw_msg = None
                    email_msg = None
                    response = None
                except Exception as e:
                    logger.error(f"Error processing message {msg_id}: {e}")
            
            # Add batch results to final results
            results.extend(batch_results)
            
            # Clear batch data for garbage collection
            batch_results = None
            responses = None
            message_map = None
            batch_request = None
            batch = None
            
            # Force garbage collection
            gc.collect()
            
        # Log memory after fetching
        logger.info(f"Memory usage after fetching: {os.popen(f'ps -p {process} -o rss=').read().strip()} KB")
        logger.info(f"Successfully retrieved {len(results)} emails")
        
        return results
        
    except HttpError as error:
        logger.error(f"Gmail API HTTP error: {error}")
        raise
    except Exception as e:
        logger.error(f"Error fetching emails: {e}")
        raise


def get_memory_usage():
    """Get memory usage for the current process."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024
        }
    except ImportError:
        # Fallback if psutil is not available
        return {'rss_mb': 0, 'vms_mb': 0}


async def main(credentials_json, user_email, query, include_spam_trash):
    """Main function to handle the subprocess flow."""
    try:
        # Create credentials from the JSON
        creds_data = json.loads(credentials_json)
        credentials = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data['refresh_token'],
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )
        
        # Build the Gmail API service
        service = build('gmail', 'v1', credentials=credentials, cache=MemoryCache())
        
        # Fetch and process emails
        emails = await fetch_and_process_emails(service, user_email, query, include_spam_trash)
        
        # Output results as JSON
        result = {
            "success": True,
            "emails": emails
        }
        print(json.dumps(result))
        
    except Exception as e:
        # If something goes wrong, output the error as JSON
        error_result = {
            "success": False,
            "error": str(e),
            "emails": []
        }
        print(json.dumps(error_result))
        sys.stderr.write(f"ERROR: {str(e)}\n")
        sys.exit(1)


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