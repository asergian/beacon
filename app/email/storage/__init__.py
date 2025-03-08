"""Email storage and caching module.

This module provides interfaces and implementations for caching processed emails
to improve performance and reduce load on email providers.

Available Classes:
- EmailCache: Abstract base class defining the email caching interface
- RedisEmailCache: Implementation using Redis as a backend

Usage:
    from app.email.storage.redis_cache import RedisEmailCache
    
    # Create a Redis cache with 7-day TTL
    cache = RedisEmailCache(get_redis_client, ttl_days=7)
    
    # Store emails in cache
    await cache.store_many(emails, user_email="user@example.com")
    
    # Retrieve recent emails
    recent_emails = await cache.get_recent(7, 2, "user@example.com")
    
    # Delete specific emails from cache
    deleted, failed = await cache.delete_emails("user@example.com", ["email_id1", "email_id2"])
    
    # Clear all cached emails for a user
    await cache.clear_cache("user@example.com")
"""

from .base_cache import EmailCache, get_email_cache
from .redis_cache import RedisEmailCache

__all__ = [
    'EmailCache',
    'RedisEmailCache',
    'get_email_cache'
] 