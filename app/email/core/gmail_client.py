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
from google.auth.transport.requests import Request
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
        self._credentials = None
    
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
                self._service = build('gmail', 'v1', credentials=self._credentials)
                self.logger.info("Gmail API connection established")
            
        except Exception as e:
            self._service = None
            self._credentials = None
            session.pop('credentials', None)
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
        try:
            # Ensure connection and valid credentials
            if not self._service:
                await self.connect()
            else:
                # Verify credentials are still valid
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
            
            # Get list of message IDs
            results = self._service.users().messages().list(
                userId='me',
                q=query,
                maxResults=100  # Limit to reasonable batch size
            ).execute()
            
            messages = results.get('messages', [])
            if not messages:
                return []
                
            # Batch get full messages
            batch_results = []
            for i in range(0, len(messages), 50):  # Process in batches of 50
                batch = messages[i:i + 50]
                batch_request = self._service.new_batch_http_request()
                
                def callback(request_id, response, exception):
                    if exception is None:
                        batch_results.append(response)
                    else:
                        self.logger.error(f"Error in batch request: {exception}")
                
                for msg in batch:
                    batch_request.add(
                        self._service.users().messages().get(
                            userId='me',
                            id=msg['id'],
                            format='raw'  # Get raw message for full content
                        ),
                        callback=callback
                    )
                
                batch_request.execute()
            
            # Process results
            emails = []
            for msg in batch_results:
                try:
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
                                    email_date = email_date.replace(tzinfo=timezone.utc)
                                except ValueError:
                                    self.logger.debug(f"Skipping email {msg['id']}: invalid date format '{date_str}'")
                                    continue
                            
                            local_email_date = email_date.astimezone(local_tz)
                            
                            # Only include emails after local_midnight
                            if local_email_date >= local_midnight:
                                emails.append({
                                    'id': msg['id'],
                                    'raw_message': raw_msg,  # Store raw message for body parsing
                                    'Message-ID': email_msg.get('Message-ID'),
                                    'subject': email_msg.get('subject'),
                                    'from': email_msg.get('from'),
                                    'to': email_msg.get('to'),
                                    'date': date_str,
                                    'snippet': msg.get('snippet', '')
                                })
                        except ValueError as e:
                            self.logger.debug(f"Skipping email {msg['id']}: {e}")
                            continue
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