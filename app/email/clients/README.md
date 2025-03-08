# Email Clients Module

The Email Clients module provides interfaces to connect to and interact with various email service providers.

## Overview

This module implements client connections to different email service providers, such as Gmail and standard IMAP servers. It handles authentication, connection management, email fetching, and sending operations. The clients abstract away the complexities of different email protocols and provider-specific APIs.

## Directory Structure

```
clients/
├── __init__.py           # Client factory functions
├── base.py               # Base client interfaces
├── gmail/                # Gmail API integration
│   ├── client.py         # Main Gmail client
│   ├── client_subprocess.py # Subprocess-based client
│   ├── core/             # Core Gmail functionality
│   ├── utils/            # Gmail utilities
│   └── worker/           # Subprocess worker implementation
├── imap/                 # IMAP protocol integration
│   └── client.py         # IMAP client implementation
└── README.md             # This documentation
```

## Components

### Base Client
Defines the common interface for all email client implementations, ensuring consistent behavior regardless of the underlying email provider.

### Gmail Client
Implements email operations using the Gmail API, including OAuth authentication, fetching, and sending capabilities. Provides both in-process and subprocess-based implementations for improved memory management.

### IMAP Client
Implements email operations using the standard IMAP protocol for compatibility with a wide range of email providers. Handles connection management, authentication, and email operations.

## Usage Examples

```python
# Using the Gmail client
from app.email.clients.gmail.client import GmailClient

client = GmailClient()
await client.connect(user_email="user@gmail.com")
emails = await client.fetch_emails(days_back=3)

# Using the IMAP client
from app.email.clients.imap.client import EmailConnection

imap_client = EmailConnection(
    server="imap.example.com",
    email="user@example.com",
    password="password",
    port=993,
    use_ssl=True
)
emails = await imap_client.fetch_emails(days=3)

# Using the client factory
from app.email.clients import create_client

client = create_client("gmail", credentials=credentials)
# or
client = create_client("imap", server="imap.example.com", email="user@example.com", password="password")
```

## Internal Design

The clients module follows these design principles:
- Provider-agnostic interfaces with consistent behavior
- Memory management for resource-intensive operations
- Proper connection pooling and reuse
- Robust error handling and retry logic
- Rate limiting and quota management

## Dependencies

Internal:
- `app.utils.memory_profiling`: For memory management
- `app.utils.async_helpers`: For asynchronous operations

External:
- `google-api-python-client`: For Gmail API access
- `google-auth`: For Google authentication
- `google-auth-oauthlib`: For OAuth flow
- `imapclient`: For IMAP protocol support
- `email`: For email parsing and construction

## Additional Resources

- [Email Processing Documentation](../../../docs/sphinx/source/email_processing.html)
- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [IMAP Protocol Documentation](https://datatracker.ietf.org/doc/html/rfc3501)
- [API Reference](../../../docs/sphinx/source/api.html) 