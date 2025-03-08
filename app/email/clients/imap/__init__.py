"""IMAP client package.

This package provides a client implementation for interacting with
IMAP email servers.
"""

from .client import EmailConnection

__all__ = ["EmailConnection"] 