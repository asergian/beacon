# Gmail Core Module

The Gmail Core module provides the fundamental building blocks for interacting with the Gmail API.

## Overview

This module serves as the foundation for Gmail API interactions, providing essential components for authentication, API service initialization, quota management, and error handling. It abstracts the complexities of the Gmail API into a clean, reusable interface that ensures efficient and reliable email operations.

## Directory Structure

```
core/
├── __init__.py       # Package exports
├── api.py            # Gmail API service initialization
├── auth.py           # Authentication utilities
├── email_utils.py    # Email processing utilities
├── exceptions.py     # Custom exception classes
├── quota.py          # API quota management
└── README.md         # This documentation
```

## Components

### API Service
Core implementation for initializing and configuring the Gmail API service, including request retries, timeouts, and optimized connection pooling.

### Authentication
Handles OAuth2 authentication flow and token management for Gmail API access, supporting both user and service account authentication methods.

### Email Utilities
Provides utility functions for common email operations such as encoding/decoding, MIME handling, and RFC compliance.

### Exception Handling
Custom exception classes specifically designed for Gmail API error scenarios, providing detailed error information and recovery suggestions.

### Quota Management
Implements rate limiting and quota tracking to prevent quota exhaustion and ensure compliance with Gmail API usage limits.

## Usage Examples

```python
# Initializing the Gmail API service
from app.email.clients.gmail.core.api import create_gmail_service
from app.email.clients.gmail.core.auth import get_credentials

# Get OAuth credentials
credentials = get_credentials(
    token_file="token.json",
    credentials_file="credentials.json",
    scopes=["https://www.googleapis.com/auth/gmail.readonly"]
)

# Create the Gmail service
gmail_service = create_gmail_service(credentials)

# Use the service to fetch profile information
profile = gmail_service.users().getProfile(userId="me").execute()
print(f"Email: {profile['emailAddress']}")
```

```python
# Managing quotas
from app.email.clients.gmail.core.quota import QuotaManager

# Create a quota manager
quota_manager = QuotaManager(
    max_requests_per_day=1000000,
    max_requests_per_100seconds=250
)

# Check if we can make a request
if quota_manager.can_make_request():
    # Make API request
    response = gmail_service.users().messages().list(userId="me").execute()
    # Record the request
    quota_manager.record_request()
else:
    wait_time = quota_manager.get_wait_time()
    print(f"Rate limit reached. Wait {wait_time} seconds.")
```

```python
# Handling exceptions
from app.email.clients.gmail.core.exceptions import GmailAPIError, GmailQuotaExceededError

try:
    response = gmail_service.users().messages().get(userId="me", id="12345").execute()
except GmailQuotaExceededError as e:
    print(f"Quota exceeded: {e.quota_limit}. Retry after {e.retry_after} seconds.")
    # Implement backoff strategy
except GmailAPIError as e:
    print(f"API error: {e.error_code} - {e.message}")
    # Handle specific error codes
```

## Internal Design

The Gmail Core module follows these design principles:
- Clean separation of concerns between authentication, API access, and error handling
- Robust error handling with detailed contextual information
- Efficient API response handling to minimize memory usage
- Memory optimization for large API responses
- Proper rate limiting to ensure quota compliance

## Dependencies

Internal:
- None (core module with no internal dependencies)

External:
- `google-api-python-client`: For Gmail API access
- `google-auth`: For Google authentication
- `google-auth-oauthlib`: For OAuth flow
- `google-auth-httplib2`: For HTTP client
- `asyncio`: For asynchronous operations

## Additional Resources

- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Google Auth Library](https://developers.google.com/identity/protocols/oauth2)
- [API Reference](../../../../../docs/sphinx/build/html/api.html) 