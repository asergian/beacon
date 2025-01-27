"""
Module for managing IMAP email connections and fetching emails.

This module provides a robust, configurable IMAP email client for fetching 
and interacting with email servers. It supports secure connections, 
error handling, and logging.

Typical usage:
    client = IMAPEmailClient(server='imap.example.com', email='user@example.com', password='secret')
    emails = await client.fetch_emails(days=1)
"""

import asyncio
import logging
from typing import Dict, List
from imapclient import IMAPClient
from datetime import datetime, timedelta

class IMAPConnectionError(Exception):
    """Exception raised for IMAP connection-related errors."""
    pass

class EmailConnection:
    """
    A client for connecting to and fetching emails from an IMAP server.

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
        
        # Configure logging
        self.logger = logging.getLogger(__name__)

    async def connect(self):
        """
        Establish a connection to the IMAP server.

        Raises:
            IMAPConnectionError: If connection or login fails
        """
        try:
            self.logger.info(f"Connecting to IMAP server: {self.server}")
     
            # Use asyncio to run blocking operations
            self._client = await asyncio.to_thread(
                IMAPClient, 
                self.server, 
                port=self.port, 
                ssl=self.use_ssl
            )

            await asyncio.to_thread(self._client.login, self.email, self.password)
            await asyncio.to_thread(self._client.select_folder, 'INBOX')
            self.logger.info("Successfully connected to IMAP server")
        except Exception as e:
            self.logger.error(f"IMAP connection failed: {e}")
            raise IMAPConnectionError(f"Connection error: {e}")

    async def fetch_emails(self, days: int = 1) -> List[Dict]:
        """
        Fetch emails from specified number of days.

        Args:
            days: Number of days to fetch emails for (default 1)

        Returns:
            A list of raw email dictionaries

        Raises:
            IMAPConnectionError: If fetching emails fails
        """
        if not self._client:
            await self.connect()

        start_date = datetime.now() - timedelta(days=days)
        start_date_str = start_date.strftime("%d-%b-%Y")

        try:
            self.logger.info(f"Fetching emails since {start_date_str}")
            
            # Run the blocking search operation in a thread
            email_ids = await asyncio.to_thread(
                lambda: self._client.search(['SINCE', start_date_str])
            )
            
            emails = []
            if email_ids:  # Add check for empty list
                for msg_id in email_ids:
                    # Run the blocking fetch operation in a thread
                    raw_email = await asyncio.to_thread(
                        lambda: self._client.fetch([msg_id], ['BODY[]'])
                    )
                    emails.append({
                        'id': msg_id,
                        'raw_message': raw_email[msg_id][b'BODY[]']
                    })
            
            self.logger.info(f"Fetched {len(emails)} emails")
            return emails
        except Exception as e:
            self.logger.error(f"Email fetch error: {e}")
            raise IMAPConnectionError(f"Failed to fetch emails: {e}")

    async def close(self):
        """Close the IMAP connection safely."""
        try:
            if self._client:
                await asyncio.to_thread(self._client.logout)
                self._client = None
                self.logger.info("IMAP connection closed")
        except Exception as e:
            self.logger.warning(f"Error closing IMAP connection: {e}")