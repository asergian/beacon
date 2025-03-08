# Email Storage Module

This module provides email caching functionality to improve performance and reduce load on email providers. It includes interfaces and implementations for storing, retrieving, and managing processed emails in a cache.

## Components

### Base Cache

The `base_cache.py` file defines the abstract base class `EmailCache` that establishes the interface for all email cache implementations.

#### Key Methods

- `get_recent(days, days_back, user_email, user_timezone)`: Retrieve recently cached emails
- `store_many(emails, user_email, ttl_days)`: Store multiple emails in the cache
- `delete_emails(user_email, email_ids)`: Delete specific emails from the cache (new)

### Redis Cache

The `redis_cache.py` file provides a Redis-based implementation of the `EmailCache` interface using Redis as the backend storage system.

#### Key Features

- **User-specific Storage**: Emails are stored per user
- **Automatic Expiration**: TTL-based caching with configurable duration
- **Selective Retrieval**: Fetch emails based on time range
- **Memory Efficiency**: JSON serialization for storage
- **Email Management**: Add, delete, and clear emails

#### Additional Methods

- `clear_cache(user_email)`: Clear all cached emails for a specific user
- `clear_all_cache(user_email)`: Clear all caches (admin function)
- `clear_old_entries(cache_duration_days, user_email)`: Cleanup old entries beyond cache duration
- `delete_emails(user_email, email_ids)`: Delete specific emails by ID (new)
- `get_cache_stats()`: Get statistics about the cache
- `log_cache_size()`: Log information about the current cache size

### Cache Utilities

The `cache_utils.py` file provides helper functions for working with cached emails:

- `get_user_timezone(timezone_str)`: Get a timezone object from a string
- `parse_date_string(date_str)`: Parse different date string formats
- `format_date_for_storage(date)`: Format dates for storage
- `validate_user_email(email)`: Validate email format

## Usage Examples

### Basic Usage

```python
from app.email.storage.redis_cache import RedisEmailCache

# Create a Redis cache with 7-day TTL
cache = RedisEmailCache(get_redis_client, ttl_days=7)

# Store emails in cache
await cache.store_many(emails, user_email="user@example.com")

# Retrieve recent emails (7 days of cache, looking back 2 days)
recent_emails = await cache.get_recent(7, 2, "user@example.com")
```

### Deleting Specific Emails

```python
# Delete specific emails that have been removed from the source
deleted_count, failed_count = await cache.delete_emails(
    "user@example.com", 
    ["email_id1", "email_id2"]
)
print(f"Deleted {deleted_count} emails, failed to delete {failed_count}")
```

### Cache Management

```python
# Clear all cached emails for a user
await cache.clear_cache("user@example.com")

# Clear old entries beyond cache duration
await cache.clear_old_entries(7, "user@example.com")

# Get cache statistics
stats = await cache.get_cache_stats()
print(f"Total users: {stats['total_users']}, Total emails: {stats['total_emails']}")
```

## Caching Strategy

1. **Storage**: Emails are stored as JSON with a key pattern of `email:{user_hash}:{email_id}`
2. **Retrieval**: Emails are retrieved based on date range and filtered by TTL
3. **Expiration**: Automatic TTL ensures emails beyond the cache duration are automatically removed
4. **Management**: Manual methods for clearing and managing the cache as needed

## Key Design Decisions

1. **Redis as Backend**: Scalable, in-memory storage with TTL support
2. **User Partitioning**: Each user's data is separately keyed
3. **JSON Serialization**: Efficient storage format for email data
4. **Selective Deletion**: Ability to remove specific emails (e.g., when they've been deleted from the source) 