# Email Pipeline Helper Modules

This directory contains modular helper functions that support the email processing pipeline. These modules separate concerns and make the core orchestrator code cleaner and more maintainable.

## Module Overview

### `__init__.py`

Exposes all helper functions for easy importing. Use this to import helpers from other modules:

```python
from app.email.pipeline.helpers import (
    setup_user_context,  # From context.py
    fetch_cached_emails, # From fetching.py
    process_in_batches,  # From processing.py
    generate_final_stats  # From stats.py
)
```

### `context.py`

Handles user context setup and validation.

**Key Functions:**
- `setup_user_context`: Sets up the user context for email analysis, including:
  - Validating user session
  - Retrieving user ID and email
  - Setting up user timezone
  - Checking AI feature enablement
  - Retrieving cache duration settings

### `fetching.py`

Manages email retrieval from both cache and Gmail.

**Key Functions:**
- `send_cache_status`: Sends a status update about checking the cache
- `fetch_cached_emails`: Retrieves cached emails matching criteria
- `fetch_emails_from_gmail`: Connects to Gmail and fetches emails
- `filter_cached_emails`: Filters cached emails to keep only those still in Gmail

### `processing.py`

Contains functions for processing and analyzing emails.

**Key Functions:**
- `process_without_ai`: Processes emails without AI features
- `process_in_batches`: Processes emails in batches with AI features
- `process_batch_results`: Processes batch results and yields updates
- `process_all_at_once`: Processes all emails at once (no batching)
- `apply_filters`: Applies priority and category filters to emails

### `stats.py`

Provides statistics generation and activity logging.

**Key Functions:**
- `generate_final_stats`: Generates and yields final pipeline statistics
- `log_activity`: Logs email analysis activity for a user

## Dependency Flow

```
orchestrator.py
    ↓
    ├── context.py
    │      ↓
    ├── fetching.py
    │      ↓
    ├── processing.py
    │      ↓
    └── stats.py
```

## Usage Example

```python
from app.email.pipeline.helpers import (
    setup_user_context,
    fetch_cached_emails,
    fetch_emails_from_gmail,
    filter_cached_emails,
    process_in_batches,
    apply_filters,
    log_activity
)

# Set up user context
user_id, user_email, timezone_obj, ai_enabled, cache_duration = setup_user_context(command, logger)

# Fetch cached emails
cached_emails, cached_ids = await fetch_cached_emails(
    command, user_email, timezone_obj, stats, cache, logger
)

# Process emails with AI in batches
async for result in process_in_batches(
    parsed_emails, command, user_id, user_email, ai_enabled,
    cache_duration, stats, processor, cache, logger
):
    # Handle result
    pass

# Apply filters to emails
filtered_emails = apply_filters(emails, command, logger)

# Log activity
log_activity(user_id, filtered_emails, stats, command, logger)
```

## Design Principles

1. **Separation of Concerns**: Each module handles a specific aspect of the pipeline
2. **Consistent Interface**: Functions follow consistent parameter patterns
3. **Error Handling**: All functions include appropriate error handling
4. **Logging**: Comprehensive logging for debugging and monitoring
5. **Type Annotations**: Full type hints for better IDE support and code validation

## Extension Points

To extend or modify pipeline functionality:

1. **Add New Helper Functions**: Add new functions to existing modules
2. **Create New Helper Modules**: For entirely new categories of functionality
3. **Update `__init__.py`**: Export new functions for easy importing 