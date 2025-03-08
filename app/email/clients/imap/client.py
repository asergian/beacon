"""
Module for managing IMAP email connections and fetching emails.

This module provides a robust, configurable IMAP email client that implements
the BaseEmailClient interface for consistent integration with the application.

Typical usage:
    client = EmailConnection(server='imap.example.com', email='user@example.com', password='secret')
    await client.connect()
    emails = await client.fetch_emails(days_back=1)
    await client.close()
"""

import asyncio
import logging
from typing import Dict, List, Optional
from imapclient import IMAPClient
from datetime import datetime, timedelta, timezone

from ..base import BaseEmailClient


class IMAPConnectionError(Exception):
    """Exception raised for IMAP connection-related errors."""
    pass


class EmailConnection(BaseEmailClient):
    """
    A client for connecting to and fetching emails from an IMAP server.
    
    This client implements the BaseEmailClient interface to provide
    a consistent interface for email operations across the application.

    Attributes:
        server (str): IMAP server hostname
        email (str): User's email address
        password (str): User's email password
        port (int): IMAP server port
        use_ssl (bool): Whether to use SSL connection
    """

    def __init__(
        self, 
        server: str, 
        email: str, 
        password: str, 
        port: int = 993, 
        use_ssl: bool = True
    ):
        """
        Initialize the IMAP email client.

        Args:
            server: IMAP server hostname
            email: User's email address
            password: User's email password
            port: IMAP server port (default 993)
            use_ssl: Whether to use SSL connection (default True)
            
        Raises:
            ValueError: If any required parameters are missing or invalid
        """
        if not all([server, email, password]):
            raise ValueError("Server, email, and password must be provided")
            
        self.server = server
        self.email = email
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self._client = None
        self.logger = logging.getLogger(__name__)
        
    async def connect(self, user_email: Optional[str] = None) -> None:
        """
        Connect to the IMAP server.
        
        Args:
            user_email: Optional override for the email address.
                        If provided, it will override the email set in constructor.
        
        Raises:
            IMAPConnectionError: If unable to connect to the IMAP server.
        """
        try:
            # Use user_email if provided, otherwise use the one from constructor
            email_to_use = user_email if user_email else self.email
            
            self.logger.info(f"Connecting to IMAP server {self.server} for {email_to_use}")
            
            # Create a new client in a thread to avoid blocking the event loop
            self._client = await asyncio.to_thread(
                IMAPClient, 
                self.server, 
                port=self.port, 
                use_uid=True, 
                ssl=self.use_ssl
            )
            
            # Login in a thread
            await asyncio.to_thread(self._client.login, self.email, self.password)
            
            # Select inbox in a thread
            await asyncio.to_thread(self._client.select_folder, 'INBOX')
            
            self.logger.info("IMAP connection established")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to IMAP server: {str(e)}")
            if self._client:
                try:
                    await asyncio.to_thread(self._client.logout)
                except:
                    pass
                self._client = None
            raise IMAPConnectionError(f"Failed to connect to IMAP server: {str(e)}")

    async def fetch_emails(self, days_back: int = 1, user_email: Optional[str] = None) -> List[Dict]:
        """
        Fetch emails from the IMAP server.
        
        Args:
            days_back: Number of days to fetch emails for, where 1 means today.
            user_email: Optional override for the email address.
        
        Returns:
            A list of dictionaries containing email data with 'id' and 'raw_message' keys.
            
        Raises:
            IMAPConnectionError: If not connected or unable to fetch emails.
        """
        try:
            if not self._client:
                await self.connect(user_email)
                
            # Calculate date for search
            date_limit = datetime.now() - timedelta(days=days_back)  # Removed timezone.utc to match original
            date_str = date_limit.strftime('%d-%b-%Y')
            
            # Search for all messages since date_limit
            search_criteria = ['SINCE', date_str]
            self.logger.info(f"Searching for emails since {date_str}")
            
            # Use asyncio.to_thread for blocking operations, with lambda to match original style
            message_ids = await asyncio.to_thread(
                lambda: self._client.search(search_criteria)
            )
            self.logger.info(f"Found {len(message_ids)} messages")
            
            if not message_ids:
                return []
            
            # Fetch message data
            emails = []
            # Process in batches of 50 to avoid memory issues
            batch_size = 50
            
            for i in range(0, len(message_ids), batch_size):
                batch_ids = message_ids[i:i+batch_size]
                
                # Fetch messages in a thread, using BODY[] to match the original
                response = await asyncio.to_thread(
                    lambda: self._client.fetch(batch_ids, ['BODY[]', 'FLAGS', 'INTERNALDATE'])
                )
                
                # Process each message
                for msg_id, data in response.items():
                    # Extract email data
                    raw_email = data[b'BODY[]']  # Changed from RFC822 to BODY[] to match original
                    
                    # Create a dict with the same structure as the original
                    email_dict = {
                        'id': msg_id,  # Not converting to string to match original
                        'raw_message': raw_email  # Using 'raw_message' key to match original
                    }
                    
                    # Optionally add additional fields that weren't in the original
                    # but might be useful for enhanced functionality
                    email_dict['flags'] = data[b'FLAGS']
                    email_dict['date'] = data[b'INTERNALDATE']
                    
                    emails.append(email_dict)
                
                self.logger.info(f"Processed {len(emails)}/{len(message_ids)} emails")
            
            return emails
            
        except Exception as e:
            self.logger.error(f"Error fetching emails: {e}")
            raise IMAPConnectionError(f"Failed to fetch emails: {e}")

    async def close(self) -> None:
        """
        Close the connection to the IMAP server.
        
        Releases any resources used by the client.
        
        Raises:
            IMAPConnectionError: If unable to close the connection cleanly.
        """
        try:
            if self._client:
                await asyncio.to_thread(self._client.logout)
                self._client = None
                self.logger.info("IMAP connection closed")
        except Exception as e:
            self.logger.error(f"Error closing IMAP connection: {e}")
            self._client = None
            # We don't raise here to ensure cleanup happens even with errors