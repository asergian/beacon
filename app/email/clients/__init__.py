"""Email client module.

This module provides various email client implementations for different
email service providers, all implementing a consistent interface.
"""

from typing import Dict, Any, Optional, Union

# Import specific clients based on need
from .gmail.client import GmailClient
from .gmail.client_subprocess import GmailClientSubprocess
from .imap.client import EmailConnection

__all__ = ["GmailClient", "GmailClientSubprocess", "EmailConnection"]


def create_gmail_client(credentials: Optional[Dict[str, Any]] = None) -> GmailClient:
    """Create a configured Gmail client.

    Args:
        credentials: Optional OAuth credentials dictionary.
            If not provided, credentials will be loaded from session.

    Returns:
        A configured GmailClient instance.
    """
    client = GmailClient()
    return client


def create_imap_client(
    server: str,
    email: str,
    password: str,
    port: int = 993,
    use_ssl: bool = True
) -> EmailConnection:
    """Create a configured IMAP client.

    Args:
        server: IMAP server hostname
        email: User's email address
        password: User's email password
        port: IMAP server port (default 993)
        use_ssl: Whether to use SSL connection (default True)

    Returns:
        A configured EmailConnection instance.
    """
    return EmailConnection(
        server=server,
        email=email,
        password=password,
        port=port,
        use_ssl=use_ssl
    )


def create_client(client_type: str, **kwargs) -> Union[GmailClient, EmailConnection]:
    """Create an email client of the specified type.

    Args:
        client_type: Type of client to create ("gmail" or "imap")
        **kwargs: Configuration parameters passed to the specific client factory

    Returns:
        An email client instance

    Raises:
        ValueError: If client_type is not supported
    """
    if client_type.lower() == "gmail":
        return create_gmail_client(**kwargs)
    elif client_type.lower() == "imap":
        return create_imap_client(**kwargs)
    else:
        raise ValueError(f"Unsupported client type: {client_type}. Use 'gmail' or 'imap'.") 