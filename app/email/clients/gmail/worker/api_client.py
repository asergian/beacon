"""Gmail API client module for worker process.

This module provides a Gmail API client for the worker process, handling
interaction with the Gmail API including authentication, message fetching,
and email sending.
"""

import base64
import json
import logging
import time
import base64
import random
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Any, Dict, List, Optional

# Import Google API libraries
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.discovery_cache.base import Cache
import httplib2

# Import utility functions from local worker utils package
from .utils import (
    log_memory_usage, 
    get_logger, 
    filter_emails_by_date,
    track_message_processing
)
from .email_parser import process_message

# Import quota manager 
from app.email.clients.gmail.core.quota import QuotaManager

# Ensure httplib2 caching is disabled to prevent memory leaks
httplib2.RETRIES = 1

# Create a global quota manager instance
quota_manager = QuotaManager()


def load_credentials(credentials_json: str) -> Dict[str, Any]:
    """Load credentials from JSON string or file.
    
    Parses OAuth credentials from either a JSON string or a file path prefixed
    with '@'. Used for initializing the Gmail API client.
    
    Args:
        credentials_json: str: OAuth credentials JSON string or file path 
            (prefixed with '@', e.g., '@/path/to/creds.json')
        
    Returns:
        Dict[str, Any]: Dictionary containing credential data with keys like
            'token', 'refresh_token', 'client_id', 'client_secret', etc.
        
    Raises:
        ValueError: If credentials cannot be loaded or parsed as valid JSON
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
    for the API discovery document. Uses a class-level dictionary to store
    cache entries, ensuring they persist for the duration of the process
    but do not consume memory between process executions.
    
    Attributes:
        _CACHE: dict: Class-level dictionary to store cached content by URL
    """
    _CACHE = {}  # Process-local cache

    def get(self, url: str) -> Optional[bytes]:
        """Get cached content for a URL.
        
        Retrieves content from the in-memory cache if it exists.
        
        Args:
            url: str: The URL to retrieve from cache
            
        Returns:
            Optional[bytes]: Cached content as bytes if found, None otherwise
        """
        return self._CACHE.get(url)

    def set(self, url: str, content: bytes) -> None:
        """Set cached content for a URL.
        
        Stores content in the in-memory cache for later retrieval.
        
        Args:
            url: str: The URL to use as cache key
            content: bytes: The content to cache
            
        Returns:
            None
        """
        self._CACHE[url] = content


async def create_gmail_service(creds_data: Dict[str, Any], logger: Optional[logging.Logger] = None) -> Any:
    """Create a Gmail API service client.
    
    Initializes and returns a Gmail API service object using the provided
    OAuth credentials. Handles token refresh and API client construction.
    
    Args:
        creds_data: Dict[str, Any]: OAuth credentials dictionary containing
            token, refresh_token, client_id, client_secret, and other required fields
        logger: Optional[logging.Logger]: Logger instance for output messages
            and debugging. If None, a default logger will be obtained.
        
    Returns:
        Any: Gmail API service object from googleapiclient.discovery
        
    Raises:
        ValueError: If credentials are invalid or service creation fails
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
    interface for fetching and sending emails. It handles authentication,
    API initialization, and provides methods for common Gmail operations with
    proper memory management and error handling.
    
    Attributes:
        logger: Optional[logging.Logger]: Logger for output messages
        credentials_json: str: OAuth credentials JSON string or file path
        service: Any: Gmail API service object from googleapiclient.discovery
        user_email: Optional[str]: Email address of the authenticated user
        credentials_data: Optional[Dict[str, Any]]: Parsed credentials dictionary
    """
    
    def __init__(self, credentials_json: str, logger: Optional[logging.Logger] = None):
        """Initialize the Gmail service with credentials.
        
        Sets up the initial state of the Gmail service object. Note that this
        does not actually create the API client - that happens in initialize().
        
        Args:
            credentials_json: str: OAuth credentials JSON string or file path 
                (prefixed with '@' for file paths)
            logger: Optional[logging.Logger]: Logger for output. If None, a default
                logger will be obtained using get_logger().
        """
        self.logger = logger or get_logger()
        self.credentials_json = credentials_json
        self.service = None
        self.user_email = None
        self.credentials_data = None
        
    async def initialize(self) -> None:
        """Initialize the service.
        
        This method loads credentials and creates the service object.
        It must be called before using any other methods of this class.
        If the service is already initialized, this method returns early.
        
        Returns:
            None
            
        Raises:
            ValueError: If credentials cannot be loaded or service creation fails
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
        
        Retrieves a single email message from Gmail by its ID, processes
        it into a structured format, and tracks memory usage.
        
        Args:
            msg_id: str: Message ID to fetch from Gmail
            
        Returns:
            Dict[str, Any]: Processed message data with standardized fields
                including headers, body content, and metadata
            
        Raises:
            ValueError: If the service is not initialized
            Exception: If message fetch fails due to API errors
        """
        if self.service is None:
            await self.initialize()
            
        try:
            # Use the quota manager to execute with retry
            async def fetch_operation():
                """Execute the actual API call to fetch a Gmail message.
                
                This nested function encapsulates the API call for use with
                the quota manager's retry mechanism.
                
                Returns:
                    Dict[str, Any]: Raw Gmail API message response
                """
                message = self.service.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="full"
                ).execute()
                return message
                
            # Track quota and execute with retry
            await quota_manager.track_quota(quota_manager._quota_cost_get)
            message = await quota_manager.execute_with_retry(fetch_operation)
            
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
        
        Creates a callback function to process responses from batch requests.
        The callback populates the responses dictionary with results or logs
        errors for failed requests.
        
        Args:
            responses: Dict[str, Any]: Dictionary to store responses, keyed by 
                request_id (usually the message ID)
            
        Returns:
            function: Callback function that takes (request_id, response, exception)
                parameters and updates the responses dictionary
        """
        def callback(request_id, response, exception):
            """Process a single response in a batch request.
            
            Args:
                request_id: str: ID of the request (usually message ID)
                response: Any: Response data if successful
                exception: Exception: Exception if request failed
            """
            if exception:
                self.logger.error(f"Error fetching message {request_id}: {exception}")
            else:
                responses[request_id] = response
            
        return callback
            
    async def get_messages_batch(self, message_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch multiple messages by ID.
        
        Retrieves multiple email messages in batches for efficiency. This method
        uses the Gmail API batch request functionality to reduce the number of
        HTTP requests and improve performance.
        
        Args:
            message_ids: List[str]: List of message IDs to fetch
            
        Returns:
            List[Dict[str, Any]]: List of processed messages, each containing
                standardized fields like headers, body content, and metadata
            
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
                
                # Track quota and execute with retry
                await quota_manager.track_quota(quota_manager._quota_cost_get * len(batch_ids))
                await quota_manager.execute_with_retry(batch.execute)
                
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
            
            # # Add a small delay between batches to avoid rate limits
            # if i + BATCH_SIZE < len(message_ids):
            #     await asyncio.sleep(0.25)  # Small delay between batches
        
        return messages
            
    async def list_message_ids(self, query: str, max_results: Optional[int] = None) -> List[str]:
        """List message IDs matching a query.
        
        Queries the Gmail API to find messages matching the specified search query
        and returns their IDs. This method handles pagination automatically if
        there are more results than can be returned in a single request.
        
        Args:
            query: str: Gmail search query in the same format as the Gmail search box
            max_results: Optional[int]: Maximum number of results to return.
                If None, returns all matching messages.
            
        Returns:
            List[str]: List of message IDs matching the query
            
        Raises:
            ValueError: If the service is not initialized
            Exception: If the listing operation fails due to API errors
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
        
        This is the main method for retrieving emails. It combines list_message_ids
        and get_messages_batch to efficiently fetch and process emails in batches,
        with optional filtering by date and folder location.
        
        Args:
            query: str: Gmail search query in the same format as the Gmail search box
            include_spam_trash: bool: Whether to include emails from spam and trash folders.
                Defaults to False.
            cutoff_time: Optional[datetime]: Cutoff time for filtering emails.
                Only emails after this time will be included. Defaults to None (no filtering).
            max_results: int: Maximum number of results to return. Defaults to 100.
            
        Returns:
            List[Dict[str, Any]]: List of processed email dictionaries with standardized
                fields including headers, body content, and metadata
            
        Raises:
            ValueError: If the service is not initialized
            Exception: If fetching or processing fails
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
        
        # Track fetch time for rate limiting
        start_time = time.time()
        
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
        
        total_time = time.time() - start_time
        rate = len(all_emails) / max(0.1, total_time)
        self.logger.info(f"Fetched and processed {len(all_emails)} emails in {total_time:.2f}s ({rate:.1f}/s)")
            
        return all_emails
            
    async def send_email(self, to: str, subject: str, content: str,
                       cc: Optional[List[str]] = None, bcc: Optional[List[str]] = None,
                       html_content: Optional[str] = None, max_retries: int = 3) -> Dict[str, Any]:
        """Send an email.
        
        Composes and sends an email with both plain text and optional HTML content.
        Handles retries with exponential backoff in case of transient failures.
        
        Args:
            to: str: Recipient email address(es), can be comma-separated
            subject: str: Email subject line
            content: str: Plain text email content
            cc: Optional[List[str]]: List of CC recipient email addresses
            bcc: Optional[List[str]]: List of BCC recipient email addresses
            html_content: Optional[str]: HTML version of the email content
            max_retries: int: Maximum number of retry attempts in case of failure.
                Defaults to 3.
            
        Returns:
            Dict[str, Any]: Dictionary with send result containing:
                - success: bool: Whether the send operation succeeded
                - message_id: str: ID of the sent message (if successful)
                - thread_id: str: ID of the thread (if successful)
                - user_email: str: Sender email address (if successful)
                - error: str: Error message (if failed)
            
        Raises:
            ValueError: If the service is not initialized
        """
        if self.service is None:
            await self.initialize()
            
        self.logger.info(f"Sending email to {to}")
        
        retries = 0
        last_error = None
        
        while retries < max_retries:
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
                
                self.logger.info(f"Email sent successfully, message ID: {result.get('id')}")
                
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