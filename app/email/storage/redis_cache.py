"""Redis implementation of the EmailCache interface.

This module provides a Redis-based implementation of the EmailCache interface,
offering email caching with automatic expiration and user-specific storage.

Typical usage:
    redis_cache = RedisEmailCache(redis_client_factory, ttl_days=7)
    await redis_cache.store_many(emails, user_email="user@example.com")
    recent_emails = await redis_cache.get_recent(7, 2, "user@example.com")
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone
import json
import logging
from redis.asyncio import Redis
from app.models.user import User
import hashlib

from ..models.processed_email import ProcessedEmail
from .base_cache import EmailCache
from .cache_utils import (
    get_user_timezone,
    parse_date_string,
    format_date_for_storage,
    validate_user_email
)

class RedisEmailCache(EmailCache):
    """Redis implementation of email cache.
    
    This class provides an implementation of the EmailCache interface using Redis
    as the backend storage. It handles caching of processed emails, with
    automatic expiration and user-specific storage.
    """
    
    def __init__(self, get_redis_client, ttl_days: int = 7):
        """Initialize Redis cache with a function to get the Redis client.
        
        Args:
            get_redis_client: Function that returns a Redis client instance.
            ttl_days: Number of days to keep emails in cache. Defaults to 7.
            
        Raises:
            ValueError: If get_redis_client is not callable.
        """
        if not callable(get_redis_client):
            raise ValueError("get_redis_client must be a callable")
        self.get_redis_client = get_redis_client
        self.ttl = timedelta(days=ttl_days)
        self._base_prefix = "email:"
        self.logger = logging.getLogger(__name__)
        
    def _get_key_prefix(self, user_email: str) -> str:
        """Get the cache key prefix for a specific user.
        
        Args:
            user_email: The user's email address.
            
        Returns:
            String prefix for Redis keys for this user.
            
        Raises:
            ValueError: If user_email is empty.
        """
        if not user_email:
            raise ValueError("user_email cannot be empty")
        # Hash the email to prevent key injection and ensure consistent format
        email_hash = hashlib.sha256(user_email.lower().encode()).hexdigest()[:12]
        return f"{self._base_prefix}{email_hash}:"

    async def _ensure_redis_connection(self, user_email: str) -> Redis:
        """Ensure Redis connection is active and working.
        
        Args:
            user_email: The user's email address (used for validation).
            
        Returns:
            Active Redis client instance.
            
        Raises:
            ValueError: If user_email is empty or Redis connection fails.
        """
        if not user_email:
            raise ValueError("user_email must be provided for cache operations")
        try:
            redis = self.get_redis_client()
            if not redis:
                raise ValueError("Failed to get Redis client")
            # Test the connection with a simple ping
            await redis.ping()
            return redis
        except Exception as e:
            self.logger.error(f"Redis connection check failed: {e}")
            raise

    async def _scan_keys(self, redis: Redis, pattern: str) -> List[str]:
        """Scan Redis for keys matching a pattern.
        
        Args:
            redis: Redis client instance.
            pattern: Key pattern to match.
            
        Returns:
            List of matching keys.
            
        Raises:
            Exception: If scanning fails.
        """
        keys = []
        try:
            cursor = 0
            while True:
                cursor, temp_keys = await redis.scan(cursor, match=pattern)
                keys.extend(temp_keys)
                if cursor == 0:
                    break
            return keys
        except Exception as e:
            self.logger.error(f"Failed to scan Redis keys: {e}")
            raise

    async def _process_cache_entry(self, redis: Redis, key: str, cache_cutoff: datetime = None) -> Tuple[Optional[ProcessedEmail], bool]:
        """Process a single cache entry from Redis.
        
        Args:
            redis: Redis client instance.
            key: Redis key to process.
            cache_cutoff: Optional datetime cutoff for expired entries.
            
        Returns:
            Tuple of (ProcessedEmail object or None, bool indicating if entry was deleted).
        """
        try:
            email_data = await redis.get(key)
            if not email_data:
                return None, False
                
            email_dict = json.loads(email_data)
            date_str = email_dict.get('date')
            
            if not date_str:
                return None, False
                
            parsed_date = parse_date_string(date_str)
            if not parsed_date:
                # Invalid date format, might need to delete the entry
                if cache_cutoff:
                    await redis.delete(key)
                    return None, True
                return None, False
            
            email_dict['date'] = parsed_date
            
            # Check if email is expired if we have a cutoff
            if cache_cutoff and parsed_date < cache_cutoff:
                await redis.delete(key)
                return None, True
                
            # Validate email has an ID
            if not email_dict.get('id'):
                return None, False
                
            try:
                processed_email = ProcessedEmail(**email_dict)
                if not processed_email.id:
                    return None, False
                return processed_email, False
            except Exception as e:
                self.logger.error(f"Failed to create ProcessedEmail for {key}: {e}")
                return None, False
                
        except Exception as e:
            self.logger.error(f"Error processing cache entry {key}: {e}")
            return None, False

    async def _delete_keys(self, redis: Redis, keys: List[str]) -> Tuple[int, int]:
        """Delete multiple keys from Redis.
        
        Args:
            redis: Redis client instance.
            keys: List of keys to delete.
            
        Returns:
            Tuple of (deleted_count, failed_count).
        """
        deleted_count = 0
        failed_count = 0
        
        for key in keys:
            try:
                await redis.delete(key)
                deleted_count += 1
            except Exception as e:
                self.logger.error(f"Failed to delete key {key}: {e}")
                failed_count += 1
                
        return deleted_count, failed_count

    async def get_recent(self, cache_duration_days: int, days_back: int, user_email: str, user_timezone: str = 'US/Pacific') -> List[ProcessedEmail]:
        """Get recent emails from cache for a specific user.
        
        Args:
            cache_duration_days: Number of days to keep emails in cache.
            days_back: Number of days to look back for emails.
            user_email: The user's email address.
            user_timezone: The user's timezone. Defaults to 'US/Pacific'.
            
        Returns:
            List of ProcessedEmail objects sorted by date in descending order.
        """
        validate_user_email(user_email)
        try:
            redis = await self._ensure_redis_connection(user_email)
            
            # Get user timezone
            user_tz = get_user_timezone(user_timezone)
            
            # Calculate the cutoff times using user's timezone
            now = datetime.now(user_tz)
            
            cache_cutoff = (now - timedelta(days=cache_duration_days))
            
            # Calculate start date using days_back-1 to match Gmail logic
            # where days_back=1 means today, days_back=2 means today and yesterday
            adjusted_days = max(0, days_back - 1)
            start_date = (now - timedelta(days=adjusted_days)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            
            # Convert to UTC for consistent comparison with stored dates
            cache_cutoff = cache_cutoff.astimezone(timezone.utc)
            start_date = start_date.astimezone(timezone.utc)
            
            self.logger.debug(
                f"Cache parameters - Start: {start_date.isoformat()}, "
                f"Cutoff: {cache_cutoff.isoformat()}, Days back: {days_back}, User timezone: {user_timezone}"
            )
            
            # Get all keys for the specific user
            pattern = f"{self._get_key_prefix(user_email)}*"
            keys = await self._scan_keys(redis, pattern)
            
            self.logger.info(f"Found {len(keys)} cached entries for user {user_email}")
            emails = []
            skipped = 0
            deleted = 0
            
            # Fetch and deserialize emails
            for key in keys:
                email, was_deleted = await self._process_cache_entry(redis, key, cache_cutoff)
                if was_deleted:
                    deleted += 1
                elif email is None:
                    skipped += 1
                else:
                    # Check if within requested date range
                    if start_date <= email.date:
                        emails.append(email)
                    else:
                        skipped += 1
            
            # Sort emails by date in descending order
            emails.sort(key=lambda x: x.date, reverse=True)
            
            self.logger.info(
                f"Cache retrieval complete - Retrieved: {len(emails)}, "
                f"Skipped: {skipped}, Deleted expired: {deleted}"
            )
            return emails
            
        except Exception as e:
            self.logger.error(f"Error fetching emails from Redis: {e}")
            return []

    async def store_many(self, emails: List[ProcessedEmail], user_email: str, ttl_days: Optional[int] = None) -> None:
        """Store multiple emails in cache for a specific user.
        
        Args:
            emails: List of ProcessedEmail objects to store.
            user_email: The user's email address.
            ttl_days: Optional override for the TTL in days. Defaults to None.
            
        Raises:
            Exception: If Redis operations fail.
        """
        validate_user_email(user_email)
        if not emails:
            return
            
        # Skip storing if cache duration is 0
        if ttl_days == 0:
            self.logger.info("Cache duration is 0, skipping email storage")
            return
            
        try:
            redis = await self._ensure_redis_connection(user_email)
            
            self.logger.info(f"Storing {len(emails)} emails in cache for user {user_email}")
            stored_count = 0
            failed_count = 0
            
            # Use provided TTL or fall back to instance default
            ttl_seconds = int(timedelta(days=(ttl_days or self.ttl.days)).total_seconds())
            
            for email in emails:
                try:
                    email_id = email.id
                    if not email_id:
                        failed_count += 1
                        continue
                        
                    key = f"{self._get_key_prefix(user_email)}{email_id}"
                    email_dict = email.dict()
                    
                    # Ensure date is properly formatted in UTC
                    if isinstance(email_dict['date'], datetime):
                        email_dict['date'] = format_date_for_storage(email_dict['date'])
                    
                    # Store with TTL using Redis SETEX command
                    await redis.setex(key, ttl_seconds, json.dumps(email_dict))
                    
                    exists = await redis.exists(key)
                    if exists:
                        stored_count += 1
                    else:
                        failed_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Failed to store email {email.id}: {e}")
                    failed_count += 1
            
            self.logger.info(f"Cache storage complete - Stored: {stored_count}, Failed: {failed_count}\n")
                    
        except Exception as e:
            self.logger.error(f"Error in store_many: {e}")
            raise

    async def clear_cache(self, user_email: str) -> None:
        """Flush all cached emails for a specific user.
        
        Args:
            user_email: The user's email address.
            
        Raises:
            ValueError: If user_email is invalid.
            Exception: If Redis operations fail.
        """
        validate_user_email(user_email)
        try:
            redis = await self._ensure_redis_connection(user_email)
            
            # Only clear keys for the specific user
            pattern = f"{self._get_key_prefix(user_email)}*"
            keys = await self._scan_keys(redis, pattern)
            
            deleted_count, failed_count = await self._delete_keys(redis, keys)
                
            self.logger.info(f"Cache cleared - Deleted: {deleted_count}, Failed: {failed_count}\n")
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
            raise

    async def clear_all_cache(self, user_email: str) -> None:
        """Clear all caches (admin only).
        
        Args:
            user_email: Email of the admin user attempting the operation.
            
        Raises:
            ValueError: If user_email is not provided or user is not an admin.
            Exception: If Redis operations fail.
        """
        if not user_email:
            raise ValueError("user_email must be provided for cache operations")
            
        # Get user from database to check role
        user = User.query.filter_by(email=user_email).first()
        if not user or not user.has_role('admin'):
            raise ValueError("Only admin users can clear all caches")
            
        try:
            redis = await self._ensure_redis_connection(user_email)
            pattern = f"{self._base_prefix}*"  # Match all user keys
            keys = await self._scan_keys(redis, pattern)
            
            deleted_count, failed_count = await self._delete_keys(redis, keys)
                
            self.logger.info(f"All caches cleared by admin {user_email} - Deleted: {deleted_count}, Failed: {failed_count}\n")
        except Exception as e:
            self.logger.error(f"Failed to clear all caches: {e}")
            raise

    async def clear_old_entries(self, cache_duration_days: int, user_email: str, user_timezone: str = 'US/Pacific') -> None:
        """Proactively clear old cache entries.
        
        Args:
            cache_duration_days: Number of days to keep emails in cache.
            user_email: The user's email address.
            user_timezone: The user's timezone. Defaults to 'US/Pacific'.
            
        Raises:
            Exception: If Redis operations fail.
        """
        try:
            redis = await self._ensure_redis_connection(user_email)
            
            # Get user timezone
            user_tz = get_user_timezone(user_timezone)
            
            now = datetime.now(user_tz)
            cache_cutoff = (now - timedelta(days=cache_duration_days)).astimezone(timezone.utc)
            
            pattern = f"{self._get_key_prefix(user_email)}*"
            keys = await self._scan_keys(redis, pattern)
            
            deleted_count = 0
            failed_count = 0
            invalid_count = 0
            
            for key in keys:
                try:
                    email_data = await redis.get(key)
                    if not email_data:
                        continue
                        
                    email_dict = json.loads(email_data)
                    date_str = email_dict.get('date')
                    
                    if not date_str:
                        await redis.delete(key)
                        invalid_count += 1
                        continue
                        
                    parsed_date = parse_date_string(date_str)
                    if not parsed_date:
                        await redis.delete(key)
                        invalid_count += 1
                        continue
                                
                    if parsed_date < cache_cutoff:
                        await redis.delete(key)
                        deleted_count += 1
                        
                except Exception as e:
                    self.logger.error(f"Error processing cache entry {key}: {e}")
                    failed_count += 1
                    
            self.logger.info(
                f"Cache cleanup complete - Expired: {deleted_count}, "
                f"Invalid: {invalid_count}, Failed: {failed_count}\n"
            )
            
        except Exception as e:
            self.logger.error(f"Error clearing old cache entries: {e}")
            raise

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the Redis cache.
        
        Returns:
            Dictionary with cache statistics.
            
        Raises:
            Exception: If Redis operations fail.
        """
        try:
            # Use a dummy email for connection
            redis = await self._ensure_redis_connection('admin@example.com')
            info = await redis.info()
            keys = await redis.keys('email:*')
            users = set()
            email_count = 0
            
            # Count emails per user
            for key in keys:
                if key.startswith(b'email:'):
                    user = key.split(b':')[1].decode('utf-8')
                    users.add(user)
                    email_count += 1
            
            return {
                'total_emails_cached': email_count,
                'unique_users': len(users),
                'memory_used_mb': info['used_memory'] / 1024 / 1024,
                'peak_memory_mb': info['used_memory_peak'] / 1024 / 1024,
                'memory_fragmentation_ratio': info.get('mem_fragmentation_ratio', 0),
                'connected_clients': info['connected_clients']
            }
        except Exception as e:
            self.logger.error(f"Error getting cache stats: {e}")
            raise

    async def log_cache_size(self) -> None:
        """Log the size of the Redis cache to the application logs.
        
        Raises:
            Exception: If Redis operations fail.
        """
        try:
            # Use a dummy email for connection
            redis = await self._ensure_redis_connection('admin@example.com')
            keys = await redis.keys(f"{self._base_prefix}*")
            total_size = 0
            for key in keys:
                size = await redis.memory_usage(key)
                total_size += size
            self.logger.info(f"Total Redis cache size: {total_size / 1024:.2f} KB")
        except Exception as e:
            self.logger.error(f"Error logging cache size: {e}")

    async def delete_emails(self, user_email: str, email_ids: List[str]) -> Tuple[int, int]:
        """Delete specific emails from the cache by their IDs.
        
        Args:
            user_email: The user's email address
            email_ids: List of email IDs to delete
            
        Returns:
            Tuple of (deleted_count, failed_count)
            
        Raises:
            ValueError: If user_email is invalid
            Exception: If Redis operations fail
        """
        validate_user_email(user_email)
        if not email_ids:
            return 0, 0
            
        try:
            redis = await self._ensure_redis_connection(user_email)
            
            # Create keys for the emails to delete
            keys_to_delete = [f"{self._get_key_prefix(user_email)}{email_id}" for email_id in email_ids]
            
            # Delete keys directly
            deleted_count, failed_count = await self._delete_keys(redis, keys_to_delete)
            
            self.logger.info(f"Deleted {deleted_count} emails from cache, Failed: {failed_count}")
            return deleted_count, failed_count
            
        except Exception as e:
            self.logger.error(f"Error deleting emails from cache: {e}")
            raise 