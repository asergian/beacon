"""Gmail API client for worker process.

This module provides functions for creating and interacting with the Gmail API
in a memory-efficient way via the GmailService class.
"""

import json
import logging
import os
import time
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Any, Dict, List, Optional

# Import Google API libraries
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.discovery_cache.base import Cache
import httplib2

# Import utility functions
from utils import (
    log_memory_usage, 
    get_logger, 
    filter_emails_by_date,
    track_message_processing
)
from email_parser import process_message

# Ensure httplib2 caching is disabled to prevent memory leaks
httplib2.RETRIES = 1


def load_credentials(credentials_json: str) -> Dict[str, Any]:
    """Load credentials from JSON string or file.
    
    Args:
        credentials_json: OAuth credentials JSON string or file path (prefixed with '@')
        
    Returns:
        Dictionary containing credential data
        
    Raises:
        ValueError: If credentials cannot be loaded
    """
    logger = get_logger()
    try:
        if credentials_json.startswith('@'):
            # It's a file path
            file_path = credentials_json[1:]
            with open(file_path, 'r') as f:
                return json.load(f)
        else:
            # It's a JSON string
            return json.loads(credentials_json)
    except Exception as e:
        logger.error(f"Failed to load credentials: {e}")
        raise ValueError(f"Failed to load credentials: {e}")


class MemoryCache(Cache):
    """In-memory cache for Gmail API discovery document.
    
    This cache is process-local and helps avoid repeated network requests
    for the API discovery document.
    """
    _CACHE = {}  # Process-local cache

    def get(self, url: str) -> Optional[bytes]:
        """Get cached content for a URL.
        
        Args:
            url: The URL to retrieve from cache
            
        Returns:
            Cached content or None if not in cache
        """
        return self._CACHE.get(url)

    def set(self, url: str, content: bytes) -> None:
        """Set cached content for a URL.
        
        Args:
            url: The URL to cache
            content: The content to cache
        """
        self._CACHE[url] = content


async def create_gmail_service(creds_data: Dict[str, Any], logger: Optional[logging.Logger] = None) -> Any:
    """Create a Gmail API service client.
    
    Args:
        creds_data: OAuth credentials dictionary
        logger: Optional logger for output
        
    Returns:
        Gmail API service object
        
    Raises:
        ValueError: If credentials are invalid
    """
    if logger is None:
        logger = get_logger()
        
    start_time = time.time()
    
    # Get user email for logging
    user_email = creds_data.get('user_email')
    if user_email:
        logger.info(f"Creating service for user: {user_email}")
    
    # Create credentials object - token should already be refreshed by parent process
    try:
        logger.debug(f"Creating credentials with token: {creds_data.get('token', '')[:10]}...")
        
        credentials = Credentials(
            token=creds_data.get('token'),
            refresh_token=creds_data.get('refresh_token'),
            token_uri=creds_data.get('token_uri'),
            client_id=creds_data.get('client_id'),
            client_secret=creds_data.get('client_secret'),
            scopes=creds_data.get('scopes')
        )
        
        # Log credential status but don't rely on it for actual validity
        # The Google Auth library will handle refreshing if needed
        if hasattr(credentials, 'expired'):
            logger.debug(f"Credentials reported as expired: {credentials.expired}")
            
        if hasattr(credentials, 'valid'):
            logger.debug(f"Credentials reported as valid: {credentials.valid}")
        
        # Build the service - Google Auth will automatically refresh the token if needed
        service = build(
            'gmail', 'v1', 
            credentials=credentials,
            cache_discovery=True,
            cache=MemoryCache(),
            static_discovery=True  # Use static discovery for reliability
        )
        
        logger.info(f"Gmail API service created in {time.time() - start_time:.2f}s")
            
        return service
    except Exception as e:
        logger.error(f"Failed to create Gmail service: {e}")
        raise ValueError(f"Failed to create Gmail service: {e}")


class GmailService:
    """Gmail API service wrapper for the worker process.
    
    This class encapsulates Gmail API interactions and provides a consistent
    interface for fetching and sending emails.
    """
    
    def __init__(self, credentials_json: str, logger: Optional[logging.Logger] = None):
        """Initialize the Gmail service with credentials.
        
        Args:
            credentials_json: OAuth credentials JSON string or path
            logger: Optional logger for output
        """
        self.logger = logger or get_logger()
        self.credentials_json = credentials_json
        self.service = None
        self.user_email = None
        self.credentials_data = None
        
    async def initialize(self) -> None:
        """Initialize the service.
        
        This method loads credentials and creates the service object.
        It must be called before using any other methods.
        """
        if self.service is not None:
            return
            
        # Load credentials
        self.credentials_data = load_credentials(self.credentials_json)
        self.user_email = self.credentials_data.get('user_email')
        
        # Create service
        self.service = await create_gmail_service(self.credentials_data, self.logger)
        
    async def get_message(self, msg_id: str) -> Dict[str, Any]:
        """Fetch a single message by ID.
        
        Args:
            msg_id: Message ID to fetch
            
        Returns:
            Processed message data
            
        Raises:
            ValueError: If the service is not initialized
            Exception: If message fetch fails
        """
        if self.service is None:
            await self.initialize()
            
        try:
            # Fetch the message
            message = self.service.users().messages().get(
                userId="me",
                id=msg_id,
                format="full"
            ).execute()
            
            # Process the message
            processed_message = process_message(message)
            
            # Track memory usage
            track_message_processing(message, self.logger)
                
            return processed_message
        except Exception as e:
            self.logger.error(f"Error fetching message {msg_id}: {e}")
            raise
            
    def create_batch_callback(self, responses: Dict[str, Any]) -> Any:
        """Create a callback function for batch requests.
        
        Args:
            responses: Dictionary to store responses
            
        Returns:
            Callback function
        """
        def callback(request_id, response, exception):
            if exception:
                self.logger.error(f"Error fetching message {request_id}: {exception}")
            else:
                responses[request_id] = response
            
        return callback
            
    async def get_messages_batch(self, message_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch multiple messages by ID.
        
        Args:
            message_ids: List of message IDs to fetch
            
        Returns:
            List of processed messages
            
        Raises:
            ValueError: If the service is not initialized
        """
        if self.service is None:
            await self.initialize()
            
        if not message_ids:
            return []
            
        self.logger.info(f"Fetching batch of {len(message_ids)} messages")
        
        # Gmail API supports batch requests which are much more efficient
        # However, we need to limit batch size to avoid hitting API limits
        BATCH_SIZE = 25  # Gmail recommendation for batch size
        messages = []
        
        # Process in smaller batches for better efficiency
        for i in range(0, len(message_ids), BATCH_SIZE):
            batch_ids = message_ids[i:i+BATCH_SIZE]
            self.logger.debug(f"Processing sub-batch {i//BATCH_SIZE + 1}: {len(batch_ids)} messages")
            
            try:
                # Create a batch request
                batch = self.service.new_batch_http_request()
                
                # Dictionary to store responses by ID
                responses = {}
                
                # Create callback for batch responses
                callback = self.create_batch_callback(responses)
                        
                # Add each message request to the batch
                for msg_id in batch_ids:
                    batch.add(
                        self.service.users().messages().get(
                            userId="me",
                            id=msg_id,
                            format="full"
                        ),
                        request_id=msg_id,
                        callback=callback
                    )
                    
                # Execute the batch request
                batch.execute()
                
                # Process successful responses
                for msg_id, response in responses.items():
                    try:
                        processed_message = process_message(response)
                        messages.append(processed_message)
                        
                        # Track memory usage
                        track_message_processing(response, self.logger)
                    except Exception as e:
                        self.logger.error(f"Error processing message {msg_id}: {e}")
            except Exception as e:
                self.logger.error(f"Error processing batch: {e}")
        
        return messages
            
    async def list_message_ids(self, query: str, max_results: Optional[int] = None) -> List[str]:
        """List message IDs matching a query.
        
        Args:
            query: Gmail search query
            max_results: Maximum number of results to return
            
        Returns:
            List of message IDs
            
        Raises:
            ValueError: If the service is not initialized
        """
        if self.service is None:
            await self.initialize()
            
        self.logger.info(f"Listing messages with query: {query}")
            
        all_messages = []
        page_token = None
        batch_size = 100  # Gmail API max is 100
        
        try:
            while True:
                # Log memory usage before each batch
                log_memory_usage(self.logger, "Before listing messages batch")
                
                # Fetch batch of message IDs
                request = self.service.users().messages().list(
                    userId="me",
                    q=query,
                    maxResults=min(batch_size, 100),
                    pageToken=page_token
                )
                response = request.execute()
                
                # Extract messages
                messages = response.get('messages', [])
                all_messages.extend(messages)
                
                # Progress logging
                self.logger.info(f"Listed {len(all_messages)} message IDs...")
                
                # Check if we need to continue
                if not response.get('nextPageToken') or (max_results and len(all_messages) >= max_results):
                    break
                    
                page_token = response.get('nextPageToken')
                
                # If we have enough messages, stop
                if max_results and len(all_messages) >= max_results:
                    break
                
            # Trim to max_results if needed
            if max_results and len(all_messages) > max_results:
                all_messages = all_messages[:max_results]
                
            # Extract just the IDs
            return [msg['id'] for msg in all_messages]
        except Exception as e:
            self.logger.error(f"Error listing messages: {e}")
            raise
            
    async def fetch_emails(self, query: str, include_spam_trash: bool = False, 
                         cutoff_time: Optional[datetime] = None,
                         max_results: int = 100) -> List[Dict[str, Any]]:
        """Fetch and process emails matching the query.
        
        Args:
            query: Gmail search query
            include_spam_trash: Whether to include spam and trash folders
            cutoff_time: Cutoff time for filtering emails
            max_results: Maximum number of results to return
            
        Returns:
            List of processed emails
            
        Raises:
            ValueError: If the service is not initialized
        """
        if self.service is None:
            await self.initialize()
            
        self.logger.info(f"Fetching emails for {self.user_email} with query: {query}")
        
        if cutoff_time:
            self.logger.info(f"Using cutoff time: {cutoff_time}")
        
        # Modify query to include/exclude spam and trash
        if not include_spam_trash:
            query = f"{query} -in:spam -in:trash"
            
        # List message IDs
        message_ids = await self.list_message_ids(query, max_results)
        
        if not message_ids:
            self.logger.info("No messages found matching criteria")
            return []
            
        self.logger.info(f"Found {len(message_ids)} messages, fetching details...")
        
        # Process in batches to manage memory
        batch_size = 25  # Smaller batches for better memory management
        all_emails = []
        
        for i in range(0, len(message_ids), batch_size):
            batch = message_ids[i:i+batch_size]
            
            # Process batch
            batch_start = time.time()
            emails = await self.get_messages_batch(batch)
            
            # Apply cutoff time filter if specified
            if cutoff_time:
                emails = filter_emails_by_date(emails, cutoff_time)
                
            all_emails.extend(emails)
            
            # Log batch progress
            batch_time = time.time() - batch_start
            self.logger.info(f"Processed batch {i//batch_size + 1}/{(len(message_ids) + batch_size - 1)//batch_size}: "
                          f"{len(emails)} emails in {batch_time:.2f}s")
        
        self.logger.info(f"Fetched and processed {len(all_emails)} emails")
            
        return all_emails
            
    async def send_email(self, to: str, subject: str, content: str,
                       cc: Optional[List[str]] = None, bcc: Optional[List[str]] = None,
                       html_content: Optional[str] = None, max_retries: int = 3) -> Dict[str, Any]:
        """Send an email.
        
        Args:
            to: Recipient email address(es)
            subject: Email subject
            content: Plain text content
            cc: CC recipients
            bcc: BCC recipients
            html_content: HTML content
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dictionary with send result
            
        Raises:
            ValueError: If the service is not initialized
            Exception: If sending fails after retries
        """
        if self.service is None:
            await self.initialize()
            
        self.logger.info(f"Sending email to {to}")
        
        retries = 0
        last_error = None
        
        while retries <= max_retries:
            try:
                if retries > 0:
                    delay = 2 ** retries  # Exponential backoff
                    self.logger.info(f"Retry {retries}/{max_retries} after {delay}s delay")
                    time.sleep(delay)
                    
                # Create a multipart message
                message = MIMEMultipart('alternative')
                message['Subject'] = subject
                message['To'] = to
                
                # Add CC and BCC if provided
                if cc:
                    message['Cc'] = ','.join(cc) if isinstance(cc, list) else cc
                if bcc:
                    message['Bcc'] = ','.join(bcc) if isinstance(bcc, list) else bcc
                
                # Make sure From is set based on Gmail API docs
                message['From'] = 'me'
                    
                # Add text part
                text_part = MIMEText(content, 'plain')
                message.attach(text_part)
                
                # Add HTML part if provided
                if html_content:
                    html_part = MIMEText(html_content, 'html')
                    message.attach(html_part)
                    
                # Convert message to RFC 2822 format base64 encoded string
                raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
                
                # Send message
                result = self.service.users().messages().send(
                    userId='me',
                    body={'raw': raw_message}
                ).execute()
                
                # Label the message as SENT if it's not already
                message_id = result.get('id')
                # Ensure the message has the SENT label
                self.service.users().messages().modify(
                    userId='me',
                    id=message_id,
                    body={'addLabelIds': ['SENT']}
                ).execute()
                
                self.logger.info(f"Email sent successfully, message ID: {message_id}")
                
                return {
                    "success": True,
                    "message_id": result.get("id", ""),
                    "thread_id": result.get("threadId", ""),
                    "user_email": self.user_email
                }
            except Exception as e:
                last_error = e
                self.logger.warning(f"Attempt {retries + 1}/{max_retries + 1} failed: {e}")
                retries += 1
        
        # If we get here, all retries failed
        error_msg = f"Failed to send email after {max_retries + 1} attempts: {last_error}"
        self.logger.error(error_msg)
        
        return {
            "success": False,
            "error": error_msg
        } 