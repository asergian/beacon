"""Core components for Gmail client.

This package contains the core components for the Gmail client,
including authentication, API service, quota management, etc.
"""

# Re-export all public components
from .exceptions import GmailAPIError, RateLimitError, AuthenticationError
from .auth import create_credentials, update_session_credentials, ensure_valid_credentials
from .quota import QuotaManager
from .api import GmailAPIService, MemoryCache
from .email_utils import parse_date, create_email_data

__all__ = [
    # Exceptions
    'GmailAPIError',
    'RateLimitError',
    'AuthenticationError',
    
    # Authentication
    'create_credentials',
    'update_session_credentials',
    'ensure_valid_credentials',
    
    # Quota
    'QuotaManager',
    
    # API
    'GmailAPIService',
    'MemoryCache',
    
    # Email utils
    'parse_date',
    'create_email_data',
] 