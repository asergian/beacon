# IMAP Client Module

The IMAP Client module provides a standard interface for accessing emails via the IMAP protocol.

## Overview

This module implements a client for the Internet Message Access Protocol (IMAP), allowing the application to connect to and interact with any IMAP-compliant email server. It provides capabilities for retrieving, searching, and managing emails while handling connection management, authentication, and error recovery.

## Directory Structure

```
imap/
├── __init__.py       # Package exports
├── client.py         # Main IMAP client implementation
├── auth.py           # Authentication utilities
├── email_parser.py   # Email parsing functionality
├── exceptions.py     # Custom exception handling
├── utils/            # IMAP-specific utilities
│   ├── __init__.py   # Utility exports
│   ├── search.py     # Search query builders
│   ├── folder.py     # Folder management utilities
│   └── connection.py # Connection management helpers
└── README.md         # This documentation
```

## Components

### IMAP Client
The core client implementation that handles connecting to IMAP servers, authenticating, and providing methods for email operations such as fetching, searching, and folder management.

### Authentication
Provides utilities for authenticating with IMAP servers using various methods including password-based authentication, OAuth2, and application-specific passwords.

### Email Parser
Implements parsing functionality for IMAP email messages, handling RFC822 format, MIME parts, attachments, and encoding issues.

### Exceptions
Custom exception classes for IMAP-specific errors, providing detailed error information and recovery suggestions.

### Utilities
Helper functions for building IMAP search queries, managing folders, and handling connection lifecycle.

## Usage Examples

```python
# Basic IMAP client usage
from app.email.clients.imap.client import IMAPClient

# Initialize client
client = IMAPClient()

# Connect to server
client.connect(
    host="imap.example.com",
    port=993,
    use_ssl=True
)

# Authenticate
client.authenticate(
    username="user@example.com",
    password="password"
)

# Select folder
client.select_folder("INBOX")

# Fetch recent emails
emails = client.fetch_emails(
    criteria="UNSEEN",
    limit=10,
    fetch_body=True
)

# Process emails
for email in emails:
    print(f"Subject: {email.subject}")
    print(f"From: {email.sender}")
    print(f"Body: {email.body[:100]}...")

# Close connection
client.disconnect()
```

```python
# Using OAuth2 authentication
from app.email.clients.imap.auth import OAuth2Authenticator

# Create authenticator
authenticator = OAuth2Authenticator(
    client_id="your_client_id",
    client_secret="your_client_secret",
    token_file="token.json"
)

# Get authentication string
auth_string = authenticator.get_auth_string(
    username="user@example.com"
)

# Connect client with OAuth
client = IMAPClient()
client.connect(host="imap.gmail.com", port=993)
client.authenticate_oauth2(
    username="user@example.com",
    auth_string=auth_string
)
```

## Internal Design

The IMAP client module follows these design principles:
- RFC-compliant IMAP protocol implementation
- Connection pooling and reuse for efficiency
- Robust error handling with automatic reconnection
- Memory-efficient handling of large emails and attachments
- Asynchronous operations support
- Comprehensive logging of IMAP operations

## Dependencies

Internal:
- `app.email.models`: For email data models
- `app.utils.logging`: For logging operations

External:
- `imaplib`: Python's standard IMAP library
- `email`: Python's standard email package
- `ssl`: For secure connections
- `asyncio`: For asynchronous operations

## Additional Resources

- [IMAP Protocol RFC3501](https://tools.ietf.org/html/rfc3501)
- [Email Format RFC822](https://tools.ietf.org/html/rfc822)
- [MIME Format RFC2045](https://tools.ietf.org/html/rfc2045)
- [API Reference]({doc}`api`) 