# Gmail Worker Module

The Gmail Worker module implements a separate process for Gmail API operations to isolate memory usage and improve stability.

## Overview

This module provides a subprocess-based implementation for Gmail API operations. It's designed to run in a separate Python process to isolate memory usage, prevent leaks, and maintain stable performance in long-running applications. The worker receives commands from the main process, executes Gmail API operations, and returns results through interprocess communication.

## Directory Structure

```
worker/
├── __init__.py           # Package exports
├── api_client.py         # Worker API client
├── email_parser.py       # Email parsing functionality
├── main.py               # Worker entry point script
├── utils/                # Worker-specific utilities
│   ├── __init__.py       # Utility exports
│   ├── date_utils.py     # Date handling utilities
│   ├── file_utils.py     # File operations utilities
│   ├── logging_utils.py  # Logging configuration
│   ├── memory_management.py # Memory optimization
│   ├── process_utils.py  # Process management
│   └── processing_utils.py # Data processing helpers
└── README.md             # This documentation
```

## Components

### Worker API Client
Implements a dedicated Gmail API client that runs entirely within the worker process. It provides email fetching and other Gmail operations isolated from the main application.

### Email Parser
Implements email parsing functionality specific to the worker environment, optimized for memory usage in a separate process.

### Worker Main
The entry point script that launches the worker process, parses command-line arguments, and coordinates operations between the main process and Gmail API.

### Worker Utilities
Collection of helper functions specifically for the worker process, including memory management, logging, and process coordination.

## Usage Examples

```python
# Using the worker directly (typically not used directly, but through client_subprocess.py)
import subprocess
import json
import sys

# Prepare arguments for the worker process
worker_script = "app/email/clients/gmail/worker/main.py"
cmd = [
    sys.executable,
    worker_script,
    "--credentials", "@/path/to/credentials.json",
    "--user_email", "user@gmail.com",
    "--action", "fetch_emails",
    "--days_back", "3"
]

# Launch worker process
process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Get output
stdout, stderr = process.communicate()
result = json.loads(stdout.decode())

# Process emails
for email in result["emails"]:
    print(f"Email ID: {email['id']}")
```

## Internal Design

The Gmail worker module follows these design principles:
- Complete isolation from the main process
- Memory-efficient implementation of Gmail operations
- Command-line based interface for interprocess communication
- Standardized JSON-based data exchange
- Comprehensive error reporting back to the main process

## Dependencies

Internal:
- None (designed to run independently)

External:
- `google-api-python-client`: For Gmail API access
- `google-auth`: For Google authentication
- `google-auth-oauthlib`: For OAuth flow
- `email`: Python's standard email package
- `argparse`: For command-line argument parsing
- `json`: For data serialization

## Additional Resources

- [Multiprocessing in Python](https://docs.python.org/3/library/multiprocessing.html)
- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Memory Management Documentation](../../../../../docs/memory_management.md)
- [API Reference](../../../../../docs/sphinx/build/html/api.html) 