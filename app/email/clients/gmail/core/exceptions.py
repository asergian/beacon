"""Exception classes for Gmail client module.

This module defines exception classes used throughout the Gmail client
to handle various error conditions.
"""


class GmailAPIError(Exception):
    """Exception raised for Gmail API-related errors."""
    pass


class RateLimitError(GmailAPIError):
    """Exception raised when hitting Gmail API rate limits."""
    pass


class AuthenticationError(GmailAPIError):
    """Exception raised when authentication with Gmail API fails."""
    pass 