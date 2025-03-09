# Gmail Client Module

The Gmail Client module provides integration with Gmail's API for email operations including fetching, sending, and managing emails.

## Overview

This module implements client interfaces for Gmail, allowing the application to connect to Gmail accounts, retrieve emails, and perform other email operations. It offers both in-process and subprocess-based implementations to optimize memory usage and performance. The module handles OAuth authentication, API access, rate limiting, and error recovery.

## Directory Structure

```
gmail/
├── __init__.py              # Package exports
├── client.py                # Main in-process Gmail client
├── client_subprocess.py     # Subprocess-based Gmail client
├── core/                    # Core API functionality
│   ├── api.py               # Gmail API operations
│   ├── auth.py              # Authentication utilities
│   ├── email_utils.py       # Email-specific helpers
│   ├── exceptions.py        # Gmail-specific errors
│   └── quota.py             # Rate limiting and quotas
├── utils/                   # Utility functions
│   ├── date_utils.py        # Date handling utilities
│   ├── file_utils.py        # File operations utilities
│   └── subprocess_utils.py  # Subprocess management
├── worker/                  # Subprocess worker
│   ├── api_client.py        # Worker API client
│   ├── email_parser.py      # Email parsing in worker
│   ├── main.py              # Worker entry point
│   └── utils/               # Worker-specific utilities
└── README.md                # This documentation
```

## Components

### Gmail Client
The main client class that provides a high-level interface for Gmail operations. It handles authentication, connection management, and error handling, while providing methods for fetching and sending emails.

### Subprocess Client
A client implementation that runs Gmail API operations in a separate process to isolate memory usage. This approach prevents memory leaks and improves stability in long-running applications.

### Core Components
The building blocks for Gmail operations, including API access, authentication, quota management, and error handling. These components implement the low-level functionality used by the client classes.

### Worker Implementation
A separate process implementation for Gmail operations that can be launched by the subprocess client. It includes its own API client, parser, and utilities to function independently.

## Usage Examples

```python
# Using the standard in-process client
from app.email.clients.gmail.client import GmailClient

client = GmailClient()
await client.connect(user_email="user@gmail.com")
emails = await client.fetch_emails(days_back=3)

for email in emails:
    print(f"Email ID: {email['id']}")
    print(f"Raw content length: {len(email['raw_message'])}")

# Using the subprocess-based client for better memory isolation
from app.email.clients.gmail.client_subprocess import GmailClientSubprocess

subprocess_client = GmailClientSubprocess()
await subprocess_client.connect(user_email="user@gmail.com")
emails = await subprocess_client.fetch_emails(days_back=3)

# Sending an email
await client.send_email(
    to="recipient@example.com",
    subject="Hello from Beacon",
    body="This is a test email.",
    html_body="<p>This is a <b>test</b> email.</p>"
)
```

## Internal Design

The Gmail client module follows these design principles:
- Clean separation between API access and client interfaces
- Memory management via subprocess isolation
- Progressive retry and error recovery
- Quota and rate limit management
- Comprehensive error handling

## Dependencies

Internal:
- `app.utils.memory_profiling`: For memory management
- `app.utils.async_helpers`: For asynchronous operations
- `app.email.models.exceptions`: For error handling

External:
- `google-api-python-client`: For Gmail API access
- `google-auth`: For Google authentication
- `google-auth-oauthlib`: For OAuth flow
- `asyncio`: For asynchronous operations
- `base64`: For MIME encoding/decoding

## Additional Resources

- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Google Auth Library Documentation](https://googleapis.dev/python/google-auth/latest/index.html)
- [Email Processing Documentation]({doc}`email_processing`)
- [API Reference]({doc}`api`) 