"""Gmail API client for fetching and managing emails.

This module provides a Gmail API client that implements the BaseEmailClient interface
using Google's Gmail API for better integration and performance.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from flask import session

from ..base import BaseEmailClient
from .core import ensure_valid_credentials, GmailAPIService, GmailAPIError


class GmailClient(BaseEmailClient):
    """
    A client for interacting with Gmail using the Gmail API.
    
    This class provides the same interface as EmailConnection but uses
    the Gmail API instead of IMAP for better integration with Google's services.
    """
    
    def __init__(self):
        """Initialize the Gmail API client."""
        self.logger = logging.getLogger(__name__)
        self._api_service = GmailAPIService()
        self._user_email = None  # Track the authenticated user's email
    
    async def connect(self, user_email: Optional[str] = None):
        """Establish a connection to Gmail API using OAuth credentials.
        
        Args:
            user_email: Email address to connect with
            
        Raises:
            ValueError: If user_email is not provided
            GmailAPIError: If connection fails
        """
        if not user_email:
            # Added to match the interface
            user_email = self._user_email
            
        if not user_email:
            raise ValueError("user_email is required to fetch emails")
            
        try:
            await self._api_service.connect(user_email)
            self._user_email = user_email
            
        except Exception as e:
            self._user_email = None
            session.pop('credentials', None)
            raise GmailAPIError(f"Connection error: {e}")
    
    async def fetch_emails(self, days_back: int = 1, user_email: str = None) -> List[Dict]:
        """
        Fetch emails from Gmail using the API with rate limiting and retries.
        
        Args:
            days_back: Number of days to fetch emails for (1 = today, 2 = today and yesterday, etc.)
            user_email: Email of the user to fetch emails for
            
        Returns:
            List of dictionaries containing email data
            
        Raises:
            ValueError: If user_email is not provided
            GmailAPIError: If email fetching fails
        """
        if not user_email:
            user_email = self._user_email
            
        if not user_email:
            raise ValueError("user_email is required to fetch emails")
            
        try:
            return await self._api_service.fetch_emails(days_back, user_email)
                
        except Exception as e:
            if "401" in str(e):
                self.logger.info("Token expired during fetch, attempting refresh...")
                await ensure_valid_credentials(user_email)
                # Retry the fetch once
                return await self.fetch_emails(days_back, user_email)
            raise GmailAPIError(f"Failed to fetch emails: {e}")

    async def close(self):
        """Close the Gmail API connection."""
        try:
            await self._api_service.close()
            self.logger.debug("Gmail API connection closed")
        except Exception as e:
            self.logger.debug(f"Error closing Gmail API connection: {e}")
            
    def __del__(self):
        """Ensure resources are cleaned up."""
        if hasattr(self, '_api_service'):
            try:
                self._api_service._service.close()
            except:
                pass

    async def disconnect(self):
        """Cleanup method to close any open connections."""
        await self.close()
        self.logger.info("Gmail client disconnected")
        return True 