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
from google.auth.transport.requests import Request
from flask import session
import time
import random
import asyncio
from functools import lru_cache

class GmailAPIError(Exception):
    """Exception raised for Gmail API-related errors."""
    pass

class RateLimitError(GmailAPIError):
    """Exception raised when hitting Gmail API rate limits."""
    pass

class MemoryCache(Cache):
    """In-memory cache for Gmail API discovery document."""
    _CACHE = {}

    def get(self, url):
        return MemoryCache._CACHE.get(url)

    def set(self, url, content):
        MemoryCache._CACHE[url] = content

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
        self._batch_size = 20
        self._request_count = 0
        self._last_request_time = 0
        self._min_request_interval = 0.25  # Reduced from 1.0
        self._max_retries = 5
        self._base_delay = 2
        self._quota_window = 1.0  # 1 second window for quota tracking
        self._quota_limit = 250   # Gmail API quota limit per user per second
        self._quota_cost_get = 5  # Cost for message.get request
        self._quota_usage = []    # Track quota usage timestamps
    
    def _create_credentials(self, creds_dict: Dict) -> Credentials:
        """Create a Credentials object from session dictionary."""
        return Credentials(
            token=creds_dict['token'],
            refresh_token=creds_dict['refresh_token'],
            token_uri=creds_dict['token_uri'],
            client_id=creds_dict['client_id'],
            client_secret=creds_dict['client_secret'],
            scopes=creds_dict['scopes']
        )
    
    def _update_session_credentials(self):
        """Update session with current credential state."""
        if self._credentials:
            session['credentials'].update({
                'token': self._credentials.token,
                'refresh_token': self._credentials.refresh_token,
                'token_uri': self._credentials.token_uri,
                'client_id': self._credentials.client_id,
                'client_secret': self._credentials.client_secret,
                'scopes': self._credentials.scopes
            })
    
    async def _ensure_valid_credentials(self):
        """Ensure credentials are valid, refreshing if necessary."""
        try:
            if not self._credentials:
                if 'credentials' not in session:
                    raise GmailAPIError("No credentials found. Please authenticate first.")
                
                creds_dict = session['credentials']
                required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'scopes']
                missing_fields = [field for field in required_fields if field not in creds_dict]
                
                if missing_fields:
                    session.pop('credentials', None)
                    raise GmailAPIError(f"Authentication incomplete - missing: {', '.join(missing_fields)}")
                
                self._credentials = self._create_credentials(creds_dict)
            
            # Check if credentials need refresh
            if not self._credentials.valid:
                if self._credentials.expired and self._credentials.refresh_token:
                    self.logger.debug("Refreshing expired credentials")
                    self._credentials.refresh(Request())
                    self._update_session_credentials()
                    self.logger.debug("Credentials refreshed successfully")
                else:
                    raise GmailAPIError("Credentials invalid and cannot be refreshed")
                    
        except Exception as e:
            self.logger.error(f"Credential error: {e}")
            self._service = None
            self._credentials = None
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

    async def connect(self):
        """
        Establish a connection to Gmail API using OAuth credentials.
        
        Uses the credentials stored in the Flask session during OAuth flow.
        """
        try:
            # First ensure we have valid credentials
            await self._ensure_valid_credentials()
            
            # Only create service if we don't have one
            if not self._service:
                self.logger.info("Connecting to Gmail API")
                # Use cached discovery document
                self._service = build('gmail', 'v1', 
                                    credentials=self._credentials,
                                    cache=MemoryCache())
                self.logger.info("Gmail API connection established")
            
        except Exception as e:
            self._service = None
            self._credentials = None
            session.pop('credentials', None)
            raise GmailAPIError(f"Connection error: {e}")
    
    async def _handle_rate_limit(self, attempt: int) -> None:
        """Handle rate limit with exponential backoff."""
        if attempt >= self._max_retries:
            raise RateLimitError("Max retries exceeded for rate limit")
            
        delay = (self._base_delay ** attempt) + (random.random() * 0.5)
        self.logger.info(f"Rate limit hit. Backing off for {delay:.2f} seconds (attempt {attempt + 1}/{self._max_retries})")
        await asyncio.sleep(delay)

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
        """Track API quota usage within the rolling window."""
        current_time = time.time()
        # Remove timestamps outside the window
        self._quota_usage = [t for t in self._quota_usage if current_time - t < self._quota_window]
        if len(self._quota_usage) * cost >= self._quota_limit:
            await asyncio.sleep(self._quota_window)
            self._quota_usage.clear()
        self._quota_usage.append(current_time)

    async def fetch_emails(self, days_back: int = 1) -> List[Dict]:
        """
        Fetch emails from Gmail using the API with rate limiting and retries.
        
        Args:
            days_back: Number of days to fetch emails for (1 = today, 2 = today and yesterday, etc.)
            
        Returns:
            List of dictionaries containing email data
            
        Raises:
            GmailAPIError: If fetching emails fails
        """
        try:
            # Only connect if no service exists
            if not self._service:
                await self.connect()
            elif self._credentials and self._credentials.expired:
                await self._ensure_valid_credentials()
            
            # Calculate the time range using local timezone
            local_tz = datetime.now().astimezone().tzinfo
            local_midnight = (datetime.now(local_tz) - timedelta(days=days_back - 1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            utc_date = (local_midnight - timedelta(days=1)).astimezone(timezone.utc)
            query = f'after:{utc_date.strftime("%Y/%m/%d")}'
            
            self.logger.info(
                "Fetching emails\n"
                f"    Days Back: {days_back}\n"
                f"    Start Date: {local_midnight.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            )
            
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
            
            # Batch get full messages with rate limiting
            batch_results = []
            for i in range(0, len(messages), self._batch_size):
                batch = messages[i:i + self._batch_size]
                
                # Create a new batch request
                batch_request = self._service.new_batch_http_request()
                current_batch = []
                
                def callback(request_id, response, exception):
                    if exception is None:
                        batch_results.append(response)
                    else:
                        self.logger.error(f"Error in batch request: {exception}")
                        if "429" in str(exception) or "quota" in str(exception).lower():
                            current_batch.append(exception)
                
                # Track quota for the batch
                await self._track_quota(self._quota_cost_get * len(batch))
                
                for msg in batch:
                    batch_request.add(
                        self._service.users().messages().get(
                            userId='me',
                            id=msg['id'],
                            format='raw'
                        ),
                        callback=callback
                    )
                
                # Execute batch with retry
                retry_count = 0
                while retry_count < self._max_retries:
                    try:
                        current_batch.clear()
                        await self._execute_with_retry(batch_request.execute)
                        if not current_batch:  # No rate limit errors in batch
                            break
                        retry_count += 1
                        await self._handle_rate_limit(retry_count)
                    except Exception as e:
                        if retry_count == self._max_retries - 1:
                            raise
                        retry_count += 1
                        await self._handle_rate_limit(retry_count)
                
                # Only add delay if we're close to quota limits
                if len(self._quota_usage) * self._quota_cost_get > self._quota_limit * 0.8:
                    await asyncio.sleep(self._min_request_interval)
            
            # Process results
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
                            emails.append({
                                'id': msg['id'],
                                'raw_message': raw_msg,
                                'Message-ID': email_msg.get('Message-ID'),
                                'subject': email_msg.get('subject'),
                                'from': email_msg.get('from'),
                                'to': email_msg.get('to'),
                                'date': date_str,
                                'snippet': msg.get('snippet', '')
                            })
                except Exception as e:
                    self.logger.error(f"Error processing message {msg['id']}: {e}")
                    continue
            
            self.logger.info(f"Retrieved {len(emails)} emails from Gmail API")
            return emails
            
        except Exception as e:
            if "401" in str(e):
                self.logger.info("Token expired during fetch, attempting refresh...")
                await self._ensure_valid_credentials()
                # Retry the fetch once
                return await self.fetch_emails(days_back)
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