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
from typing import List, Dict, Any, TypeVar

from ..models.processed_email import ProcessedEmail

# Create a type variable for the EmailCache class
T = TypeVar('T', bound='EmailCache')

class EmailCache(ABC):
    """Abstract base class for email caching.
    
    This class defines the interface for email caching implementations.
    Implementations should provide methods for retrieving and storing emails.
    """
    
    @abstractmethod
    async def get_recent(self, days: int) -> List[ProcessedEmail]:
        """Retrieve recent emails from the cache.
        
        Args:
            days: Number of days to look back for emails.
            
        Returns:
            List of ProcessedEmail objects.
        """
        pass

    @abstractmethod
    async def store_many(self, emails: List[ProcessedEmail]) -> None:
        """Store multiple emails in the cache.
        
        Args:
            emails: List of ProcessedEmail objects to store.
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