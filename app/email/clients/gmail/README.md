# Gmail Client

This module provides a Gmail API client for fetching and managing emails, implementing the BaseEmailClient interface using Google's Gmail API for better integration and performance.

## Module Structure

The Gmail client has been refactored into a modular architecture to improve maintainability, testability, and separation of concerns:

```
gmail/
├── core/                 # Core components and functionality
│   ├── __init__.py       # Exports all public components
│   ├── api.py            # Gmail API service operations
│   ├── auth.py           # Authentication utilities
│   ├── email_utils.py    # Email processing utilities
│   ├── exceptions.py     # Exception definitions
│   └── quota.py          # Rate limit and quota management
├── utils/                # Utilities for the Gmail client
│   ├── __init__.py       # Exports utility functions
│   ├── date_utils.py     # Date handling utilities
│   ├── file_utils.py     # File operations utilities
│   └── subprocess_utils.py # Subprocess handling utilities
├── worker/               # Gmail worker for subprocess implementation
│   ├── __init__.py
│   ├── api_client.py     # Worker API client implementation
│   ├── email_parser.py   # Email parsing functionality
│   ├── main.py           # Main worker entry point
│   └── README.md         # Worker documentation
├── __init__.py           # Package initialization
├── client.py             # Main Gmail client
├── client_subprocess.py  # Subprocess-based client implementation
└── README.md             # This documentation
```

## Components

### Main Components

- **client.py**: The main Gmail client implementing the BaseEmailClient interface.
- **client_subprocess.py**: A memory-isolated implementation that delegates API operations to a subprocess.

### Core Components

- **core/api.py**: Provides the `GmailAPIService` class for all Gmail API operations.
- **core/auth.py**: Handles authentication with the Gmail API, including credentials management.
- **core/quota.py**: Manages API rate limits and quotas to prevent overruns.
- **core/email_utils.py**: Utilities for processing email data.
- **core/exceptions.py**: Defines exceptions used throughout the module.

### Utilities

- **utils/subprocess_utils.py**: Utilities for subprocess operations.
- **utils/file_utils.py**: Utilities for file operations.
- **utils/date_utils.py**: Utilities for date calculations.

### Worker

The worker directory contains a subprocess implementation that handles Gmail API operations in a separate process for memory isolation.

## Usage

### Basic Usage

```python
from app.email.clients.gmail.client import GmailClient

# Create a client
gmail_client = GmailClient()

# Connect to Gmail API
await gmail_client.connect('user@example.com')

# Fetch emails
emails = await gmail_client.fetch_emails(days_back=3)

# Process emails
for email in emails:
    print(f"Subject: {email['subject']}")

# Close the connection
await gmail_client.close()
```

### Subprocess Implementation

For memory-intensive operations, you can use the subprocess implementation:

```python
from app.email.clients.gmail.client_subprocess import GmailClientSubprocess

# Create a subprocess client
gmail_client = GmailClientSubprocess()

# Connect and use same as the regular client
await gmail_client.connect('user@example.com')
emails = await gmail_client.fetch_emails(days_back=3)
await gmail_client.close()
```

## Architecture

The Gmail client follows a modular design pattern:

1. The main `client.py` presents a simplified facade over the core components.
2. Core functionality is split into separate modules by concern.
3. The `GmailAPIService` in core/api.py handles direct interactions with the Gmail API.
4. Authentication and quota management are handled in dedicated modules.
5. The subprocess implementation uses a worker subprocess for memory isolation.

This architecture allows for better separation of concerns, easier testing, and improved maintainability. 