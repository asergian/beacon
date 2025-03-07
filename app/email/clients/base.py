"""Base interface for email clients.

This module defines the abstract base class that all email clients must implement.
Email clients provide a consistent interface for connecting to email services,
fetching emails, and managing connections.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime


class BaseEmailClient(ABC):
    """Abstract base class defining the interface for all email clients.
    
    All email client implementations (Gmail, IMAP, etc.) must implement this interface
    to ensure consistent behavior across the application.
    """
    
    @abstractmethod
    async def connect(self, user_email: Optional[str] = None) -> None:
        """Connect to the email service.
        
        Args:
            user_email: Optional email address for the connection.
                        Used for services that require an email address.
        
        Raises:
            ConnectionError: If unable to connect to the email service.
        """
        pass
    
    @abstractmethod
    async def fetch_emails(self, days_back: int = 1, user_email: Optional[str] = None) -> List[Dict]:
        """Fetch emails from the email service.
        
        Args:
            days_back: Number of days to fetch emails for, where 1 means today.
            user_email: Optional email address to fetch emails for.
        
        Returns:
            A list of dictionaries containing email data.
            
        Raises:
            ConnectionError: If not connected to the email service.
            FetchError: If unable to fetch emails.
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the connection to the email service.
        
        This method should be called when the client is no longer needed
        to release resources and ensure a clean shutdown.
        
        Raises:
            ConnectionError: If unable to close the connection cleanly.
        """
        pass 