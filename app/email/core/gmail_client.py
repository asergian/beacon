"""Gmail API client for fetching and managing emails.

This module provides a Gmail API client that implements the same interface as
the IMAP client but uses Google's Gmail API for better integration and performance.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
import base64
from email import message_from_bytes
from email.utils import parsedate_to_datetime
from googleapiclient.discovery import build
from googleapiclient.discovery_cache.base import Cache
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as AuthRequest
from flask import session
import time
import random
import asyncio
from functools import lru_cache
from google.oauth2 import id_token
from app.utils.memory_profiling import log_memory_usage

class GmailAPIError(Exception):
    """Exception raised for Gmail API-related errors."""
    pass

class RateLimitError(GmailAPIError):
    """Exception raised when hitting Gmail API rate limits."""
    pass

class MemoryCache(Cache):
    """In-memory cache for Gmail API discovery document."""
    # Module level cache that persists across instances
    _GLOBAL_CACHE = {}

    def get(self, url):
        return self._GLOBAL_CACHE.get(url)

    def set(self, url, content):
        self._GLOBAL_CACHE[url] = content

# Initialize cache with common discovery URLs
_DISCOVERY_URL = "https://gmail.googleapis.com/$discovery/rest?version=v1"
MemoryCache._GLOBAL_CACHE[_DISCOVERY_URL] = None  # Will be populated on first use

class GmailClient:
    """
    A client for interacting with Gmail using the Gmail API.
    
    This class provides the same interface as EmailConnection but uses
    the Gmail API instead of IMAP for better integration with Google's services.
    """
    
    def __init__(self):
        """Initialize the Gmail API client."""
        self.logger = logging.getLogger(__name__)
        self._service = None
        self._credentials = None
        self._user_email = None  # Track the authenticated user's email
        self._batch_size = 25  # Increased from 5 for better throughput
        self._request_count = 0
        self._last_request_time = 0
        self._min_request_interval = 0.1  # Reduced from 0.15 for faster processing
        self._max_retries = 3
        self._base_delay = 1
        self._quota_window = 1.0
        self._quota_limit = 250  # Gmail's default quota
        self._quota_cost_get = 5
        self._quota_usage = []
        self._last_quota_reset = time.time()
        self._concurrent_batch_limit = 5  # Increased from 3 for better parallelization
    
    def _create_credentials(self, creds_dict: Dict) -> Credentials:
        """Create a Credentials object from session dictionary."""
        if not creds_dict.get('token') or not creds_dict.get('refresh_token'):
            raise ValueError("Invalid credentials: missing token or refresh token")
            
        return Credentials(
            token=creds_dict['token'],
            refresh_token=creds_dict['refresh_token'],
            token_uri=creds_dict['token_uri'],
            client_id=creds_dict['client_id'],
            client_secret=creds_dict['client_secret'],
            scopes=creds_dict['scopes']
        )
    
    def _update_session_credentials(self, user_email: str):
        """Update session with current credential state."""
        if self._credentials and user_email:
            session['credentials'] = {
                'token': self._credentials.token,
                'refresh_token': self._credentials.refresh_token,
                'token_uri': self._credentials.token_uri,
                'client_id': self._credentials.client_id,
                'client_secret': self._credentials.client_secret,
                'scopes': self._credentials.scopes,
                'id_token': self._credentials.id_token  # Make sure to store the ID token
            }
    
    async def _ensure_valid_credentials(self, user_email: str):
        """Ensure credentials are valid, refreshing if necessary."""
        try:
            if not user_email:
                raise ValueError("user_email is required")
                
            # If we have credentials, verify they're for the right user
            if self._credentials and self._user_email != user_email:
                self._credentials = None
                self._service = None
                
            if not self._credentials:
                if 'credentials' not in session:
                    raise GmailAPIError("No credentials found. Please authenticate first.")
                
                creds_dict = session['credentials']
                
                # Only verify token if we don't have valid credentials
                try:
                    id_info = id_token.verify_oauth2_token(
                        creds_dict.get('id_token'),
                        AuthRequest(),
                        creds_dict.get('client_id')
                    )
                    token_email = id_info.get('email', '').lower()
                    
                    # Verify credentials belong to the right user
                    if token_email != user_email.lower():
                        self.logger.error(f"Email mismatch - Token: {token_email}, Requested: {user_email}")
                        raise GmailAPIError("Credentials don't match the requested user")
                except ValueError as e:
                    self.logger.debug(f"Token needs refresh: {e}")  # Changed to debug since this is normal
                    # If token verification fails, try to refresh credentials
                    if creds_dict.get('refresh_token'):
                        self.logger.info("Refreshing expired token...")
                        temp_creds = self._create_credentials(creds_dict)
                        temp_creds.refresh(AuthRequest())
                        creds_dict['token'] = temp_creds.token
                        creds_dict['id_token'] = temp_creds.id_token
                        session['credentials'] = creds_dict
                        # Try verification again
                        id_info = id_token.verify_oauth2_token(
                            temp_creds.id_token,
                            AuthRequest(),  # Use the correct Request class from google.auth.transport
                            creds_dict.get('client_id')
                        )
                        token_email = id_info.get('email', '').lower()
                        if token_email != user_email.lower():
                            raise GmailAPIError("Credentials don't match the requested user")
                        self.logger.info("Token refreshed successfully")  # Added success message
                    else:
                        raise GmailAPIError("Unable to verify user credentials - no refresh token available")
                
                required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'scopes']
                missing_fields = [field for field in required_fields if field not in creds_dict]
                
                if missing_fields:
                    session.pop('credentials', None)
                    raise GmailAPIError(f"Authentication incomplete - missing: {', '.join(missing_fields)}")
                
                self._credentials = self._create_credentials(creds_dict)
                self._user_email = user_email
            
            # Check if credentials need refresh
            if not self._credentials.valid:
                if self._credentials.expired and self._credentials.refresh_token:
                    self.logger.debug("Refreshing expired credentials")
                    self._credentials.refresh(AuthRequest())
                    self._update_session_credentials(user_email)
                    self.logger.debug("Credentials refreshed successfully")
                else:
                    raise GmailAPIError("Credentials invalid and cannot be refreshed")
                    
        except Exception as e:
            self.logger.error(f"Credential error: {e}")
            self._service = None
            self._credentials = None
            self._user_email = None
            session.pop('credentials', None)
            raise GmailAPIError(f"Failed to ensure valid credentials: {e}")

    @lru_cache(maxsize=128)
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse email date string with caching.
        
        Args:
            date_str: The date string to parse
            
        Returns:
            Parsed datetime object or None if parsing fails
        """
        if not date_str:
            return None
        try:
            # Remove the "(UTC)" part if it exists
            date_str = date_str.split(' (')[0].strip()
            return parsedate_to_datetime(date_str)
        except Exception:
            return None

    async def connect(self, user_email: str):
        """Establish a connection to Gmail API using OAuth credentials."""
        try:
            # First ensure we have valid credentials for this user
            await self._ensure_valid_credentials(user_email)
            
            # Only create service if we don't have one or if user changed
            if not self._service or self._user_email != user_email:
                self.logger.info(f"Connecting to Gmail API for user {user_email}")
                self._service = build('gmail', 'v1', 
                                    credentials=self._credentials,
                                    cache=MemoryCache())
                self._user_email = user_email
                self.logger.info("Gmail API connection established")
            
        except Exception as e:
            self._service = None
            self._credentials = None
            self._user_email = None
            session.pop('credentials', None)
            raise GmailAPIError(f"Connection error: {e}")
    
    async def _handle_rate_limit(self, attempt: int) -> None:
        """Handle rate limit with exponential backoff."""
        if attempt >= self._max_retries:
            raise RateLimitError("Max retries exceeded for rate limit")
            
        delay = (self._base_delay * (2 ** attempt)) + (random.random() * 0.5)  # True exponential backoff
        self.logger.warning(f"Rate limit hit. Backing off for {delay:.2f} seconds (attempt {attempt + 1}/{self._max_retries})")
        await asyncio.sleep(delay)
        
        # Adjust batch size and concurrency after rate limit
        if attempt > 0:
            self._batch_size = max(5, self._batch_size - 2)  # Reduce batch size but not below 5
            self._concurrent_batch_limit = max(2, self._concurrent_batch_limit - 1)  # Reduce concurrency but not below 2
            self.logger.info(f"Adjusted batch size to {self._batch_size} and concurrency to {self._concurrent_batch_limit}")

    async def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute an operation with retry logic for rate limits."""
        for attempt in range(self._max_retries):
            try:
                # Ensure minimum time between requests
                now = time.time()
                time_since_last = now - self._last_request_time
                if time_since_last < self._min_request_interval:
                    await asyncio.sleep(self._min_request_interval - time_since_last)
                
                self._last_request_time = time.time()
                self._request_count += 1
                
                return operation(*args, **kwargs)
                
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    await self._handle_rate_limit(attempt)
                    continue
                raise
                
        raise RateLimitError("Max retries exceeded")

    async def _track_quota(self, cost: int):
        """Track API quota usage with automatic reset."""
        current_time = time.time()
        
        # Reset quota if window has passed
        if current_time - self._last_quota_reset >= self._quota_window:
            self._quota_usage.clear()
            self._last_quota_reset = current_time
        
        # Remove old timestamps
        self._quota_usage = [t for t in self._quota_usage 
                           if current_time - t[0] < self._quota_window]
        
        # Calculate current usage
        current_usage = sum(cost for _, cost in self._quota_usage)
        
        # If we would exceed quota, wait for reset
        if current_usage + cost >= self._quota_limit:
            wait_time = self._quota_window - (current_time - self._last_quota_reset)
            if wait_time > 0:
                self.logger.info(f"Quota limit reached, waiting {wait_time:.2f}s for reset")
                await asyncio.sleep(wait_time)
                self._quota_usage.clear()
                self._last_quota_reset = time.time()
        
        # Add new usage
        self._quota_usage.append((current_time, cost))

    async def _execute_batch_with_quota(self, batch_request, batch_size: int):
        """Execute a batch request with quota tracking and rate limiting."""
        try:
            # Track quota before execution
            await self._track_quota(self._quota_cost_get * batch_size)
            
            # Add jitter to request timing to avoid thundering herd
            jitter = random.uniform(0, 0.1)
            current_time = time.time()
            time_since_last = current_time - self._last_request_time
            if time_since_last < self._min_request_interval:
                await asyncio.sleep(self._min_request_interval - time_since_last + jitter)
            
            # Execute with retry
            result = await self._execute_with_retry(batch_request.execute)
            self._last_request_time = time.time()
            return result
            
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                # If we hit rate limit, adjust parameters dynamically
                self._min_request_interval = min(self._min_request_interval * 1.2, 0.5)  # Increase interval up to max 0.5s
                raise RateLimitError(str(e))
            raise

    async def fetch_emails(self, days_back: int = 1, user_email: str = None) -> List[Dict]:
        """
        Fetch emails from Gmail using the API with rate limiting and retries.
        
        Args:
            days_back: Number of days to fetch emails for (1 = today, 2 = today and yesterday, etc.)
            user_email: Email of the user to fetch emails for
            
        Returns:
            List of dictionaries containing email data
        """
        if not user_email:
            raise ValueError("user_email is required to fetch emails")
            
        try:
            # Only connect if no service exists or if user changed
            if not self._service or self._user_email != user_email:
                await self.connect(user_email)
            elif self._credentials and self._credentials.expired:
                await self._ensure_valid_credentials(user_email)
            
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
            results = await self._execute_with_retry(
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

            for i in range(0, len(messages), self._batch_size):
                batch = messages[i:i + self._batch_size]
                batch_request = self._service.new_batch_http_request()
                
                def callback(request_id, response, exception):
                    if exception is None:
                        batch_results.append(response)
                    else:
                        self.logger.error(f"Error in batch request: {exception}")
                
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
            for i in range(0, len(all_batches), self._concurrent_batch_limit):
                current_batches = all_batches[i:i + self._concurrent_batch_limit]
                batch_tasks = [self._execute_batch_with_quota(req, size) 
                             for req, size in current_batches]
                
                try:
                    await asyncio.gather(*batch_tasks)
                except RateLimitError:
                    # If we hit rate limit, process remaining batches sequentially
                    self.logger.warning("Rate limit hit, switching to sequential processing")
                    for req, size in current_batches:
                        try:
                            await self._execute_batch_with_quota(req, size)
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
                    email_date = self._parse_date(date_str)
                    
                    if email_date:
                        local_email_date = email_date.astimezone(local_tz)
                        if local_email_date >= local_midnight:
                            # Process this email and extract what we need now
                            email_data = {
                                'id': msg['id'],
                                'Message-ID': email_msg.get('Message-ID'),
                                'subject': email_msg.get('subject'),
                                'from': email_msg.get('from'),
                                'to': email_msg.get('to'),
                                'date': date_str,
                                'snippet': msg.get('snippet', ''),
                                'raw_message': raw_msg  # Will be processed and cleared by parser
                            }
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
                await self._ensure_valid_credentials(user_email)
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
            self._service.close()

    async def disconnect(self):
        """Cleanup method to close any open connections."""
        # Currently a no-op since the Gmail API client doesn't require explicit cleanup
        # But we provide this method for consistency with other clients
        self.logger.info("Gmail client disconnected")
        return True 