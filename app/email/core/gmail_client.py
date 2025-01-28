"""Gmail API client for fetching and managing emails.

This module provides a Gmail API client that implements the same interface as
the IMAP client but uses Google's Gmail API for better integration and performance.
"""

import logging
from typing import Dict, List
from datetime import datetime, timedelta
import base64
from email import message_from_bytes
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from flask import session

class GmailAPIError(Exception):
    """Exception raised for Gmail API-related errors."""
    pass

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
    
    async def connect(self):
        """
        Establish a connection to Gmail API using OAuth credentials.
        
        Uses the credentials stored in the Flask session during OAuth flow.
        """
        try:
            self.logger.info("Connecting to Gmail API")
            
            # Get credentials from session
            if 'credentials' not in session:
                raise GmailAPIError("No credentials found. Please authenticate first.")
            
            creds_dict = session['credentials']
            credentials = Credentials(
                token=creds_dict['token'],
                refresh_token=creds_dict['refresh_token'],
                token_uri=creds_dict['token_uri'],
                client_id=creds_dict['client_id'],
                client_secret=creds_dict['client_secret'],
                scopes=creds_dict['scopes']
            )
            
            # Build the Gmail API service
            self._service = build('gmail', 'v1', credentials=credentials)
            self.logger.info("Successfully connected to Gmail API")
            
        except Exception as e:
            self.logger.error(f"Gmail API connection failed: {e}")
            raise GmailAPIError(f"Connection error: {e}")
    
    async def fetch_emails(self, days: int = 1) -> List[Dict]:
        """
        Fetch emails from Gmail using the API.
        
        Args:
            days: Number of days to fetch emails for (default 1)
            
        Returns:
            List of dictionaries containing email data
            
        Raises:
            GmailAPIError: If fetching emails fails
        """
        if not self._service:
            await self.connect()
            
        try:
            self.logger.info(f"Fetching emails for the past {days} days")
            
            # Calculate the time range
            after_date = datetime.now() - timedelta(days=days)
            query = f'after:{after_date.strftime("%Y/%m/%d")}'
            
            # Get list of messages
            results = self._service.users().messages().list(
                userId='me',
                q=query
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            # Fetch full message data for each email
            for message in messages:
                msg = self._service.users().messages().get(
                    userId='me',
                    id=message['id'],
                    format='raw'
                ).execute()
                
                # Decode the raw message
                raw_msg = base64.urlsafe_b64decode(msg['raw'])
                email_msg = message_from_bytes(raw_msg)
                
                emails.append({
                    'id': message['id'],
                    'raw_message': raw_msg,
                    'Message-ID': email_msg.get('Message-ID'),
                    'subject': email_msg.get('subject'),
                    'from': email_msg.get('from'),
                    'to': email_msg.get('to'),
                    'date': email_msg.get('date')
                })
            
            self.logger.info(f"Fetched {len(emails)} emails")
            return emails
            
        except Exception as e:
            self.logger.error(f"Email fetch error: {e}")
            raise GmailAPIError(f"Failed to fetch emails: {e}")
    
    async def close(self):
        """Close the Gmail API connection."""
        try:
            if self._service:
                self._service.close()
                self._service = None
                self.logger.info("Gmail API connection closed")
        except Exception as e:
            self.logger.warning(f"Error closing Gmail API connection: {e}")
            
    def __del__(self):
        """Ensure resources are cleaned up."""
        if self._service:
            self._service.close() 