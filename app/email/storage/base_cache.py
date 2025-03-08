"""Email caching module.

This module provides interfaces and implementations for caching processed emails
to improve performance and reduce the load on email providers.

The module includes:
    - An abstract base class defining the email caching interface
    - Factory function to create cache instances based on configuration

Typical usage:
    cache = get_email_cache(config)
    recent_emails = await cache.get_recent(7, user_email)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, TypeVar, Tuple, Optional

from ..models.processed_email import ProcessedEmail

# Create a type variable for the EmailCache class
T = TypeVar('T', bound='EmailCache')

class EmailCache(ABC):
    """Abstract base class for email caching.
    
    This class defines the interface for email caching implementations.
    Implementations should provide methods for retrieving, storing, and managing emails.
    """
    
    @abstractmethod
    async def get_recent(self, days: int, days_back: int, user_email: str, user_timezone: str = 'US/Pacific') -> List[ProcessedEmail]:
        """Retrieve recent emails from the cache.
        
        Args:
            days: Number of days for cache duration.
            days_back: Number of days to look back for emails.
            user_email: The user's email address.
            user_timezone: The user's timezone. Defaults to 'US/Pacific'.
            
        Returns:
            List of ProcessedEmail objects.
        """
        pass

    @abstractmethod
    async def store_many(self, emails: List[ProcessedEmail], user_email: str, ttl_days: Optional[int] = None) -> None:
        """Store multiple emails in the cache.
        
        Args:
            emails: List of ProcessedEmail objects to store.
            user_email: The user's email address.
            ttl_days: Optional override for the TTL in days. Defaults to None.
        """
        pass
        
    @abstractmethod
    async def delete_emails(self, user_email: str, email_ids: List[str]) -> Tuple[int, int]:
        """Delete specific emails from the cache by their IDs.
        
        Args:
            user_email: The user's email address.
            email_ids: List of email IDs to delete.
            
        Returns:
            Tuple of (deleted_count, failed_count).
        """
        pass

# Factory function to get the appropriate cache implementation
def get_email_cache(config: Dict[str, Any]) -> 'EmailCache':
    """Get an email cache implementation based on configuration.
    
    Args:
        config: Configuration dictionary with cache settings.
        
    Returns:
        An implementation of EmailCache.
    """
    cache_type = config.get('cache_type', 'redis')
    
    if cache_type == 'redis':
        # Import here to avoid circular imports
        from .redis_cache import RedisEmailCache
        get_redis_client = config.get('get_redis_client')
        ttl_days = config.get('cache_ttl_days', 7)
        return RedisEmailCache(get_redis_client, ttl_days)
    else:
        raise ValueError(f"Unsupported cache type: {cache_type}")

__all__ = ['EmailCache', 'get_email_cache']