"""Gmail API service operations.

This module provides functionality for interacting with the Gmail API service,
including building services, executing API calls, and handling responses.
"""

import logging
import base64
import asyncio
from typing import Dict, List, Optional, Any
from email import message_from_bytes
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import ensure_valid_credentials
from .quota import QuotaManager
from .exceptions import GmailAPIError, RateLimitError
from .email_utils import parse_date, create_email_data
from app.utils.memory_profiling import log_memory_usage

logger = logging.getLogger(__name__)


class MemoryCache:
    """In-memory cache for Gmail API discovery document."""
    # Module level cache that persists across instances
    _GLOBAL_CACHE = {}

    def get(self, url):
        """Retrieve cached content for a URL.
        
        This method implements the interface expected by googleapiclient.discovery
        to retrieve cached content for discovery URLs.
        
        Args:
            url: The URL to retrieve cached content for.
            
        Returns:
            The cached content if available, None otherwise.
        """
        return self._GLOBAL_CACHE.get(url)

    def set(self, url, content):
        """Store content in the cache for a URL.
        
        This method implements the interface expected by googleapiclient.discovery
        to store discovery document content in the cache.
        
        Args:
            url: The URL to use as the cache key.
            content: The content to store in the cache.
        """
        self._GLOBAL_CACHE[url] = content


# Initialize cache with common discovery URLs
_DISCOVERY_URL = "https://gmail.googleapis.com/$discovery/rest?version=v1"
MemoryCache._GLOBAL_CACHE[_DISCOVERY_URL] = None  # Will be populated on first use


class GmailAPIService:
    """Service for interacting with the Gmail API."""
    
    def __init__(self):
        """Initialize the Gmail API service."""
        self.logger = logging.getLogger(__name__)
        self._service = None
        self._credentials = None
        self._user_email = None
        self._quota_manager = QuotaManager()
    
    async def connect(self, user_email: str):
        """Connect to the Gmail API service.
        
        Args:
            user_email: Email of the user to connect as
            
        Raises:
            GmailAPIError: If connection fails
        """
        try:
            # First ensure we have valid credentials for this user
            credentials = await ensure_valid_credentials(user_email)
            
            # Only create service if we don't have one or if user changed
            if not self._service or self._user_email != user_email or self._credentials != credentials:
                self.logger.info(f"Connecting to Gmail API for user {user_email}")
                self._service = build('gmail', 'v1', 
                                     credentials=credentials,
                                     cache=MemoryCache())
                self._credentials = credentials
                self._user_email = user_email
                self.logger.info("Gmail API connection established")
            
        except Exception as e:
            self._service = None
            self._credentials = None
            self._user_email = None
            raise GmailAPIError(f"Connection error: {e}")
    
    async def fetch_emails(self, days_back: int = 1, user_email: str = None) -> List[Dict]:
        """Fetch emails using the Gmail API with rate limiting and retries.
        
        Args:
            days_back: Number of days to fetch emails for
            user_email: Email of the user to fetch emails for
            
        Returns:
            List of dictionaries containing email data
            
        Raises:
            ValueError: If user_email is not provided
            GmailAPIError: If email fetching fails
        """
        if not user_email:
            raise ValueError("user_email is required to fetch emails")
            
        try:
            # Only connect if no service exists or if user changed
            if not self._service or self._user_email != user_email:
                await self.connect(user_email)
            elif self._credentials and self._credentials.expired:
                self._credentials = await ensure_valid_credentials(user_email)
            
            # Calculate the time range using local timezone
            local_tz = datetime.now().astimezone().tzinfo
            local_midnight = (datetime.now(local_tz) - timedelta(days=days_back - 1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            utc_date = (local_midnight - timedelta(days=1)).astimezone(timezone.utc)
            query = f'after:{utc_date.strftime("%Y/%m/%d")}'
            
            # Exclude emails from the SENT folder
            query = f'{query} -in:sent'
            
            self.logger.info(
                "Fetching emails\n"
                f"    Days Back: {days_back}\n"
                f"    Start Date: {local_midnight.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                f"    Query: {query}"
            )
            
            log_memory_usage(self.logger, "Before Gmail API Fetch")
            
            # Get list of message IDs with retry
            results = await self._quota_manager.execute_with_retry(
                self._service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=100
                ).execute
            )

            messages = results.get('messages', [])
            if not messages:
                return []

            # Process batches with controlled concurrency
            batch_results = []
            all_batches = []

            batch_size = self._quota_manager.batch_size
            for i in range(0, len(messages), batch_size):
                batch = messages[i:i + batch_size]
                batch_request = self._service.new_batch_http_request()
                
                def callback(request_id, response, exception):
                    """Handles the response for each request in a batch API call.

                    This callback function processes the response or exception for each
                    individual request within a batch request made to the Gmail API. It
                    records the success or failure of the request and processes the
                    response data if successful.

                    Args:
                        request_id (str): The ID of the completed request.
                        response (dict): The response data if the request was successful.
                        exception (Exception): The exception raised if the request failed.
                    """
                    nonlocal batch_results

                    if exception:
                        self._quota_manager.record_failure()
                        if isinstance(exception, HttpError):
                            if exception.resp.status in (429, 403):
                                # Rate limit or quota exceeded
                                self._quota_manager.record_rate_limit_error()
                                self.logger.warning(f"Rate limit or quota exceeded: {exception}")
                            else:
                                self.logger.error(f"API error: {exception}")
                        else:
                            self.logger.error(f"Non-HTTP error: {exception}")
                        return

                    # Process successful response
                    self._quota_manager.record_success()

                    # Extract raw message data
                    processed_data = create_email_data(response)
                    batch_results.append(processed_data)

                    if len(batch_results) % 10 == 0:
                        self.logger.info(f"Processed {len(batch_results)} emails so far")
                
                # Add messages to batch
                for msg in batch:
                    batch_request.add(
                        self._service.users().messages().get(
                            userId='me',
                            id=msg['id'],
                            format='raw'
                        ),
                        callback=callback
                    )
                
                all_batches.append((batch_request, len(batch)))
                
            log_memory_usage(self.logger, "After Gmail API Fetch (get list of message IDs)")
            
            # Process batches with controlled concurrency
            concurrent_limit = self._quota_manager.concurrent_batch_limit
            for i in range(0, len(all_batches), concurrent_limit):
                current_batches = all_batches[i:i + concurrent_limit]
                batch_tasks = [self._quota_manager.execute_batch_with_quota(req, size) 
                              for req, size in current_batches]
                
                try:
                    await asyncio.gather(*batch_tasks)
                except RateLimitError:
                    # If we hit rate limit, process remaining batches sequentially
                    self.logger.warning("Rate limit hit, switching to sequential processing")
                    for req, size in current_batches:
                        try:
                            await self._quota_manager.execute_batch_with_quota(req, size)
                        except Exception as e:
                            self.logger.error(f"Failed to process batch: {e}")
                            continue
                            
            log_memory_usage(self.logger, "After Batch Processing")
            
            # Process results - with memory optimization
            emails = []
            for msg in batch_results:
                try:
                    # Decode the raw message
                    raw_msg = base64.urlsafe_b64decode(msg['raw'])
                    email_msg = message_from_bytes(raw_msg)
                    
                    # Parse the email date with caching
                    date_str = email_msg.get('date')
                    email_date = parse_date(date_str)
                    
                    if email_date:
                        local_email_date = email_date.astimezone(local_tz)
                        if local_email_date >= local_midnight:
                            # Process this email and extract what we need now
                            email_data = create_email_data(
                                msg['id'], 
                                email_msg, 
                                raw_msg,
                                msg.get('snippet', '')
                            )
                            emails.append(email_data)
                            
                    # Clear references to large objects immediately
                    raw_msg = None
                    email_msg = None
                    msg['raw'] = None  # Clear the raw data in the batch result too
                    
                except Exception as e:
                    self.logger.error(f"Error processing message {msg['id']}: {e}")
                    continue

            # Clear batch results to free memory
            batch_results = None
            msg = None  # Clear the reference to the last message in the loop
            
            log_memory_usage(self.logger, "After Email Processing")
            self.logger.info(f"Retrieved {len(emails)} emails from Gmail API")
            
            return emails
                
        except Exception as e:
            if "401" in str(e):
                self.logger.info("Token expired during fetch, attempting refresh...")
                self._credentials = await ensure_valid_credentials(user_email)
                # Retry the fetch once
                return await self.fetch_emails(days_back, user_email)
            raise GmailAPIError(f"Failed to fetch emails: {e}")
    
    async def close(self):
        """Close the Gmail API connection."""
        try:
            if self._service:
                self._service.close()
                self._service = None
                self.logger.debug("Gmail API connection closed")
        except Exception as e:
            self.logger.debug(f"Error closing Gmail API connection: {e}")
    
    def __del__(self):
        """Ensure resources are cleaned up."""
        if self._service:
            try:
                self._service.close()
            except:
                pass 