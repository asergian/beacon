# Gmail Worker Package

This package provides a modular implementation of the Gmail worker process for memory-isolated email operations. It's designed to handle Gmail API interactions in a separate process, preventing memory leaks and resource exhaustion from impacting the main application.

## Overview

The Gmail worker solves several challenges in working with email data:

- **Memory Management**: Email processing can be memory-intensive, especially with large attachments
- **Resource Isolation**: Running in a separate process prevents memory leaks from affecting the main application
- **Efficient Batch Processing**: Optimized for handling large numbers of emails in memory-efficient batches
- **Robust Error Handling**: Graceful error recovery and comprehensive logging
- **Clean API**: Simple command-line interface for flexible integration

## Structure

The package is organized into the following modules and subpackages:

### Core Modules
- `__init__.py`: Package initialization and module documentation
- `main.py`: Command-line interface and main execution logic
- `email_parser.py`: Email content parsing and decoding functionality
- `api_client.py`: Gmail API client with batching and memory optimization

### Utility Modules
- `utils/`: Utility functions package
  - `date_utils.py`: Date/time handling and timezone conversions
  - `file_utils.py`: File operation utilities
  - `logging_utils.py`: Logging configuration utilities
  - `memory_management.py`: Memory tracking and optimization
  - `processing_utils.py`: Email filtering and processing utilities
  - See `utils/README.md` for detailed information

## Installation

The Gmail worker is part of the main application and doesn't require separate installation. However, it has the following dependencies:

- Python 3.7+
- google-api-python-client
- google-auth
- google-auth-oauthlib
- google-auth-httplib2

These dependencies are included in the main application's requirements.txt file.

## Usage

The worker is typically invoked by the parent client module, but can also be run directly as a command-line tool. The worker responds with JSON output containing the processed data or error information.

### Fetching Emails

```bash
python -m app.email.clients.gmail.worker.main \
  --action fetch_emails \
  --credentials @/path/to/creds.json \
  --user_email user@gmail.com \
  --query "after:2023/01/01 from:important@example.com" \
  --days_back 7 \
  --max_results 100 \
  --user_timezone "America/New_York"
```

#### Fetch Parameters:

- `--credentials`: OAuth credentials JSON string or file path (prefixed with @)
- `--user_email`: Email address of the authenticated user
- `--query`: Gmail search query (same format as Gmail search box)
- `--days_back`: Number of days back to fetch emails (default: 1)
- `--include_spam_trash`: Include emails from spam and trash folders (flag)
- `--max_results`: Maximum number of results to return (default: 100)
- `--user_timezone`: User's timezone for date filtering (default: US/Pacific)

### Sending Emails

```bash
python -m app.email.clients.gmail.worker.main \
  --action send_email \
  --credentials @/path/to/creds.json \
  --user_email user@gmail.com \
  --to recipient@example.com \
  --subject "Important Message" \
  --content @/path/to/content.txt \
  --html_content @/path/to/content.html \
  --cc cc@example.com \
  --bcc bcc@example.com
```

#### Send Parameters:

- `--credentials`: OAuth credentials JSON string or file path (prefixed with @)
- `--user_email`: Email address of the authenticated user
- `--to`: Recipient email address(es), comma-separated for multiple recipients
- `--subject`: Email subject line
- `--content`: Plain text content or file path (prefixed with @)
- `--html_content`: HTML content or file path (prefixed with @) (optional)
- `--cc`: CC recipient(s), comma-separated (optional)
- `--bcc`: BCC recipient(s), comma-separated (optional)

## Memory Management Techniques

The Gmail worker implements several strategies for efficient memory usage:

1. **Process Isolation**: Running in a separate process prevents memory leaks from affecting the main application
2. **Aggressive Garbage Collection**: Custom garbage collection settings for better memory reclamation
3. **Batch Processing**: Processing emails in small batches to limit peak memory usage
4. **Resource Cleanup**: Explicit cleanup of connections and resources after use
5. **Timeout Protection**: SIGALRM-based timeouts to prevent hanging processes
6. **Memory Monitoring**: Tracking and logging of memory usage throughout execution

## Error Handling

The worker has comprehensive error handling to ensure reliability:

- All errors are caught and converted to structured JSON responses
- Detailed logging provides context for debugging
- Retries with exponential backoff for transient API errors
- Graceful degradation when possible

## Troubleshooting

Common issues and solutions:

- **Timeout Errors**: Increase the timeout value in `setup_signal_handlers()` or process emails in smaller batches
- **Memory Issues**: Reduce batch sizes in `get_messages_batch()` and `fetch_emails()`
- **Authentication Errors**: Ensure OAuth credentials are valid and have appropriate scopes
- **Parse Errors**: For problematic emails, use debug logging to identify issues

## Design Principles

1. **Memory Efficiency**: The worker is designed to minimize memory usage through careful resource management and isolation.
2. **Modularity**: Each component has a single responsibility and clear interfaces for better maintainability.
3. **Error Handling**: Comprehensive error handling with detailed logging for better diagnostics.
4. **Performance**: Batch processing and concurrent operations for optimal performance.
5. **Isolation**: Running in a separate process to isolate memory usage and prevent leaks.

## Coding Standards

This package follows Google coding standards:
- Clear docstrings with Args/Returns/Raises sections
- Type hints for all parameters and return values
- Consistent naming conventions
- Comprehensive error handling
- Modular design with single responsibility principle 