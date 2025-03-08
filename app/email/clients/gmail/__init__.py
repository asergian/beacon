"""Gmail client package.

This package provides different client implementations for interacting with
the Gmail API, including direct and subprocess-based clients.
"""

from .client import GmailClient
from .client_subprocess import GmailClientSubprocess 

__all__ = ["GmailClient", "GmailClientSubprocess"] 