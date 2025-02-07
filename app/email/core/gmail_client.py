"""Gmail API client for fetching and managing emails.

This module provides a Gmail API client that implements the same interface as
the IMAP client but uses Google's Gmail API for better integration and performance.
"""

import logging
from typing import Dict, List
from datetime import datetime, timedelta, timezone
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
    
    # Token refresh threshold (5 minutes before expiry)
    TOKEN_REFRESH_THRESHOLD = 300
    
    def __init__(self):
        """Initialize the Gmail API client."""
        self.logger = logging.getLogger(__name__)
        self._service = None
        self._credentials = None
        self._token_expiry = None
    
    def _should_refresh_token(self) -> bool:
        """Check if token should be refreshed based on expiry time."""
        if not self._token_expiry:
            return True
        return (self._token_expiry - datetime.now(timezone.utc)).total_seconds() < self.TOKEN_REFRESH_THRESHOLD
    
    async def _refresh_token_if_needed(self):
        """Refresh the access token if it's close to expiring."""
        try:
            if self._should_refresh_token() and self._credentials:
                self.logger.debug("Proactively refreshing token")
                self._credentials.refresh()
                self._token_expiry = datetime.now(timezone.utc) + timedelta(seconds=3600)  # 1 hour
                
                # Update session with new token
                session['credentials'].update({
                    'token': self._credentials.token,
                    'refresh_token': self._credentials.refresh_token
                })
                self.logger.info("OAuth token refreshed")
        except Exception as e:
            self.logger.error(f"Token refresh failed: {e}")
            # Force reconnection on next operation
            self._service = None
            self._credentials = None
            self._token_expiry = None
    
    async def connect(self):
        """
        Establish a connection to Gmail API using OAuth credentials.
        
        Uses the credentials stored in the Flask session during OAuth flow.
        """
        if self._service and not self._should_refresh_token():
            await self._refresh_token_if_needed()
            return
            
        try:
            self.logger.info("Connecting to Gmail API")
            
            # Get credentials from session
            if 'credentials' not in session:
                raise GmailAPIError("No credentials found. Please authenticate first.")
            
            creds_dict = session['credentials']
            
            # Verify all required fields are present
            required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'scopes']
            missing_fields = [field for field in required_fields if field not in creds_dict]
            
            if missing_fields:
                session.pop('credentials', None)
                raise GmailAPIError(f"Authentication incomplete - missing: {', '.join(missing_fields)}")
            
            self._credentials = Credentials(
                token=creds_dict['token'],
                refresh_token=creds_dict['refresh_token'],
                token_uri=creds_dict['token_uri'],
                client_id=creds_dict['client_id'],
                client_secret=creds_dict['client_secret'],
                scopes=creds_dict['scopes']
            )
            
            # Set initial token expiry (1 hour from now)
            self._token_expiry = datetime.now(timezone.utc) + timedelta(seconds=3600)
            
            # Build the Gmail API service
            self._service = build('gmail', 'v1', credentials=self._credentials)
            
            self.logger.info("Gmail API connection established")
            
        except Exception as e:
            # Clear invalid session credentials
            session.pop('credentials', None)
            self._service = None
            self._credentials = None
            self._token_expiry = None
            raise GmailAPIError(f"Connection error: {e}")
    
    async def fetch_emails(self, days_back: int = 1) -> List[Dict]:
        """
        Fetch emails from Gmail using the API.
        
        Args:
            days_back: Number of days to fetch emails for (1 = today, 2 = today and yesterday, etc.)
            
        Returns:
            List of dictionaries containing email data
            
        Raises:
            GmailAPIError: If fetching emails fails
        """
        if not self._service:
            await self.connect()
        
        await self._refresh_token_if_needed()
            
        try:
            # Calculate the time range using local timezone
            local_tz = datetime.now().astimezone().tzinfo
            
            # Set after_date to midnight of days_back - 1 days ago in local time
            local_midnight = (datetime.now(local_tz) - timedelta(days=days_back - 1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            
            # Subtract a day to include local midnight for the query
            utc_date = (local_midnight - timedelta(days=1)).astimezone(timezone.utc)
            query = f'after:{utc_date.strftime("%Y/%m/%d")}'
            
            self.logger.info(
                "Fetching emails\n"
                f"    Days Back: {days_back}\n"
                f"    Start Date: {local_midnight.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            )
            
            # Get list of messages
            results = self._service.users().messages().list(
                userId='me',
                q=query
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            # Fetch full message data for each email and filter by local date
            for message in messages:
                try:
                    msg = self._service.users().messages().get(
                        userId='me',
                        id=message['id'],
                        format='raw'
                    ).execute()
                    
                    # Decode the raw message
                    raw_msg = base64.urlsafe_b64decode(msg['raw'])
                    email_msg = message_from_bytes(raw_msg)
                    
                    # Parse the email date and convert to local timezone
                    date_str = email_msg.get('date')
                    if date_str:
                        try:
                            # Remove the "(UTC)" part if it exists
                            date_str = date_str.split(' (')[0].strip()
                            
                            # Try parsing with timezone offset format
                            try:
                                email_date = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
                            except ValueError:
                                # Try parsing GMT format
                                try:
                                    email_date = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S GMT")
                                    # Convert GMT to UTC
                                    email_date = email_date.replace(tzinfo=timezone.utc)
                                except ValueError:
                                    self.logger.debug(f"Skipping email {message['id']}: invalid date format '{date_str}'")
                                    continue
                            
                            local_email_date = email_date.astimezone(local_tz)
                            
                            # Only include emails after local_midnight
                            if local_email_date >= local_midnight:
                                emails.append({
                                    'id': message['id'],
                                    'raw_message': raw_msg,
                                    'Message-ID': email_msg.get('Message-ID'),
                                    'subject': email_msg.get('subject'),
                                    'from': email_msg.get('from'),
                                    'to': email_msg.get('to'),
                                    'date': date_str
                                })
                        except ValueError as e:
                            self.logger.debug(f"Skipping email {message['id']}: {e}")
                            continue
                except Exception as e:
                    # Log individual message fetch errors but continue processing
                    self.logger.error(f"Error fetching message {message['id']}: {e}")
                    continue
            
            self.logger.info(f"Retrieved {len(emails)} emails from Gmail API")
            return emails
            
        except Exception as e:
            # Check if token needs refresh
            if "401" in str(e):
                self.logger.info("Token expired during fetch, refreshing...")
                await self._refresh_token_if_needed()
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