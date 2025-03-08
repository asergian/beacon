# Email Storage Module

The Email Storage module provides caching and persistence mechanisms for email data and processing results.

## Overview

This module handles the storage and retrieval of processed emails and their analysis results. It implements various caching strategies to optimize performance and reduce redundant processing. The primary implementation uses Redis for fast, distributed caching with flexible expiration policies.

## Directory Structure

```
storage/
├── __init__.py           # Package exports
├── base_cache.py         # Abstract cache interface
├── cache_utils.py        # Cache utility functions
├── redis_cache.py        # Redis implementation
└── README.md             # This documentation
```

## Components

### Email Cache Interface
Defines the common interface for all cache implementations, ensuring consistent behavior across different storage backends.

### Redis Email Cache
Implements the cache interface using Redis as the storage backend. Provides fast, distributed caching with TTL-based expiration and serialization/deserialization of complex objects.

### Cache Utilities
Helper functions for cache operations like serialization, compression, and key generation. These utilities help manage the storage and retrieval of complex objects like processed emails.

## Usage Examples

```python
# Using the Redis cache implementation
from app.email.storage.redis_cache import RedisEmailCache
from app.email.models.processed_email import ProcessedEmail

# Create a cache instance
cache = RedisEmailCache()

# Store a processed email
email = ProcessedEmail(
    id="email_123",
    subject="Meeting tomorrow",
    # ... other fields
)
await cache.store_email(email, user_id="user_456", ttl_days=7)

# Retrieve cached emails
emails = await cache.get_emails_for_user(
    user_id="user_456", 
    days_back=3,
    max_count=100
)

# Check if an email exists in cache
exists = await cache.has_email("email_123", user_id="user_456")

# Delete an email from cache
await cache.delete_email("email_123", user_id="user_456")

# Clear user's cache
await cache.clear_user_cache("user_456")
```

## Internal Design

The storage module follows these design principles:
- Clean abstraction with interface-based design
- Efficient serialization and deserialization
- Proper expiration and TTL management
- Namespace isolation between users
- Compression for large objects

## Dependencies

Internal:
- `app.services.redis_service`: For Redis client access
- `app.utils.logging_setup`: For logging storage operations

External:
- `redis`: For Redis connection
- `msgpack`: For efficient serialization
- `zlib`: For compression
- `json`: For JSON serialization fallback

## Additional Resources

- [Redis Documentation](https://redis.io/docs/manual/)
- [Python Redis Client Documentation](https://redis-py.readthedocs.io/)
- [Email Processing Documentation](../../../docs/email_processing.md)
- [API Reference](../../../docs/sphinx/build/html/api.html) 