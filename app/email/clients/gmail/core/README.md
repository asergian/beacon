# Gmail Client Core

This directory contains the core components of the Gmail client, designed to provide modular functionality for interacting with the Gmail API.

## Components

### API Service (`api.py`)

The `GmailAPIService` class provides a comprehensive interface for interacting with the Gmail API. Key features:

- Handles API connections and service management
- Implements batch processing with rate limiting
- Provides memory optimization for large email fetches
- Handles service lifecycle (connection, fetch, close)

### Authentication (`auth.py`)

Authentication utilities for the Gmail API:

- OAuth credential management
- Token validation and refresh
- Session credential handling
- User verification

### Quota Management (`quota.py`)

Manages API quota and rate limiting:

- Tracks API usage to prevent quota overruns
- Provides exponential backoff for rate limits
- Dynamically adjusts batch sizes and concurrency
- Implements retry mechanisms for API operations

### Email Utilities (`email_utils.py`)

Utilities for processing email data:

- Cached date parsing for performance
- Email data normalization
- Utility functions for common email operations

### Exceptions (`exceptions.py`)

Centralized exception definitions:

- `GmailAPIError`: Base exception for all Gmail API errors
- `RateLimitError`: For handling rate limiting issues
- `AuthenticationError`: For authentication and credential problems

## Usage

The components in this directory are primarily used by the main `GmailClient` class, but can also be used directly for more specialized Gmail API operations:

```python
from app.email.clients.gmail.core import GmailAPIService, ensure_valid_credentials

# Get credentials
credentials = await ensure_valid_credentials("user@example.com")

# Create service
service = GmailAPIService()
await service.connect("user@example.com")

# Use service
emails = await service.fetch_emails(days_back=3)
```

## Design Philosophy

The core components follow these design principles:

1. **Single responsibility**: Each module handles one aspect of Gmail API interaction
2. **Loose coupling**: Components can be used independently
3. **Comprehensive error handling**: All errors are caught and converted to domain-specific exceptions
4. **Performance optimization**: Includes caching, memory management, and batch processing
5. **Resource management**: Proper cleanup of resources when operations complete 