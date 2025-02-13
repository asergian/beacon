from abc import ABC, abstractmethod
from typing import List, Optional
import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
from redis.asyncio import Redis
from app.utils.async_utils import async_manager

from ..models.processed_email import ProcessedEmail

class EmailCache(ABC):
    """Abstract base class for email caching"""
    
    @abstractmethod
    async def get_recent(self, days: int) -> List[ProcessedEmail]:
        pass

    @abstractmethod
    async def store_many(self, emails: List[ProcessedEmail]) -> None:
        pass

class RedisEmailCache(EmailCache):
    """Redis implementation of email cache"""
    
    def __init__(self, get_redis_client, ttl_days: int = 7):
        """Initialize Redis cache with a function to get the Redis client
        
        Args:
            get_redis_client: Function that returns a Redis client instance
            ttl_days: Number of days to keep emails in cache
        """
        if not callable(get_redis_client):
            raise ValueError("get_redis_client must be a callable")
        self.get_redis_client = get_redis_client
        self.ttl = timedelta(days=ttl_days)
        self._base_prefix = "email:"
        self.logger = logging.getLogger(__name__)
        
    def _get_key_prefix(self, user_email: str) -> str:
        """Get the cache key prefix for a specific user"""
        if not user_email:
            raise ValueError("user_email cannot be empty")
        return f"{self._base_prefix}{user_email.lower()}:"

    async def set_user(self, user_email: str) -> None:
        """Validate user email format - no longer stores the email"""
        if not user_email:
            raise ValueError("user_email cannot be empty")
        # Just validate the email format but don't store it
        user_email.lower()

    async def _ensure_redis_connection(self, user_email: str) -> Redis:
        """Ensure Redis connection is active and working"""
        if not user_email:
            raise ValueError("user_email must be provided for cache operations")
        try:
            redis = self.get_redis_client()
            if not redis:
                raise ValueError("Failed to get Redis client")
            # Test the connection with a simple ping
            await async_manager.run_in_loop(redis.ping)
            return redis
        except Exception as e:
            self.logger.error(f"Redis connection check failed: {e}")
            raise

    async def get_recent(self, cache_duration_days: int, days_back: int, user_email: str) -> List[ProcessedEmail]:
        """Get recent emails from cache for a specific user"""
        try:
            redis = await self._ensure_redis_connection(user_email)
            
            # Calculate the cutoff times in UTC
            now = datetime.now()  # Local time
            local_tz = now.astimezone().tzinfo  # Get the local timezone
            
            cache_cutoff = (now - timedelta(days=cache_duration_days)).astimezone(timezone.utc)
            
            # Make it timezone-aware in local time first
            start_date = now.replace(tzinfo=local_tz)
            
            # Calculate start date using days_back-1 to match Gmail logic
            # where days_back=1 means today, days_back=2 means today and yesterday
            start_date = (start_date - timedelta(days=days_back - 1))
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Then convert to UTC
            start_date = start_date.astimezone(timezone.utc)
            
            self.logger.debug(
                f"Cache parameters - Start: {start_date.isoformat()}, "
                f"Cutoff: {cache_cutoff.isoformat()}, Days back: {days_back}"
            )
            
            # Get all keys for the specific user
            pattern = f"{self._get_key_prefix(user_email)}*"
            keys = []
            try:
                async for key in redis.scan_iter(match=pattern):
                    key_parts = key.split(':')
                    if len(key_parts) != 3 or key_parts[1] != user_email:
                        self.logger.warning(f"Invalid cache key format: {key}")
                        continue
                    keys.append(key)
            except Exception as e:
                self.logger.error(f"Failed to scan Redis keys: {e}")
                return []
            
            self.logger.info(f"Found {len(keys)} cached entries for user {user_email}")
            emails = []
            skipped = 0
            deleted = 0
            
            # Fetch and deserialize emails
            for key in keys:
                try:
                    # Skip keys that don't match the expected format or user
                    key_parts = key.split(':')
                    if len(key_parts) != 3 or key_parts[1] != user_email:
                        continue
                        
                    email_data = await redis.get(key)
                    email_data = await redis.get(key)
                    if not email_data:
                        continue
                        
                    email_dict = json.loads(email_data)
                    date_str = email_dict.get('date')
                    
                    if not date_str:
                        skipped += 1
                        continue
                        
                    try:
                        # Handle various date formats
                        if 'Z' in date_str:
                            parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        elif '+' in date_str or '-' in date_str[-6:]:
                            parsed_date = datetime.fromisoformat(date_str)
                        else:
                            parsed_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                        
                        # Ensure date is in UTC
                        if parsed_date.tzinfo is None:
                            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                        else:
                            parsed_date = parsed_date.astimezone(timezone.utc)
                        
                        email_dict['date'] = parsed_date
                        
                        # First check if email is within cache duration
                        if parsed_date >= cache_cutoff:
                            # Only include if within requested date range
                            if start_date <= parsed_date:
                                try:
                                    if not email_dict.get('id'):
                                        skipped += 1
                                        continue
                                        
                                    processed_email = ProcessedEmail(**email_dict)
                                    
                                    if not processed_email.id:
                                        skipped += 1
                                        continue
                                        
                                    emails.append(processed_email)
                                except Exception as e:
                                    self.logger.error(f"Failed to create ProcessedEmail for {key}: {e}")
                                    skipped += 1
                        else:
                            # Delete emails older than cache cutoff
                            try:
                                await async_manager.run_in_loop(redis.delete, key)
                                deleted += 1
                            except Exception as e:
                                self.logger.error(f"Failed to delete expired key {key}: {e}")
                    except ValueError as e:
                        self.logger.warning(f"Invalid date format in cache entry {key}: {e}")
                        skipped += 1
                except Exception as e:
                    self.logger.error(f"Error processing cache entry {key}: {e}")
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
        """Store multiple emails in cache for a specific user"""
        if not emails:
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
                        if email_dict['date'].tzinfo is None:
                            email_dict['date'] = email_dict['date'].replace(tzinfo=timezone.utc)
                        else:
                            email_dict['date'] = email_dict['date'].astimezone(timezone.utc)
                        email_dict['date'] = email_dict['date'].isoformat()
                    
                    # Store with TTL using Redis SETEX command
                    await async_manager.run_in_loop(
                        redis.setex,
                        key,
                        ttl_seconds,
                        json.dumps(email_dict)
                    )
                    
                    exists = await async_manager.run_in_loop(redis.exists, key)
                    if exists:
                        stored_count += 1
                    else:
                        failed_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Failed to store email {email.id}: {e}")
                    failed_count += 1
            
            self.logger.info(f"Cache storage complete - Stored: {stored_count}, Failed: {failed_count}")
                    
        except Exception as e:
            self.logger.error(f"Error in store_many: {e}")
            raise

    async def clear_cache(self, user_email: str) -> None:
        """Flush the cache for a specific user"""
        if not user_email:
            return
            
        try:
            redis = await self._ensure_redis_connection(user_email)
            
            # Only clear keys for the specific user
            pattern = f"{self._get_key_prefix(user_email)}*"
            deleted_count = 0
            failed_count = 0
            
            try:
                async for key in redis.scan_iter(match=pattern):
                    try:
                        await async_manager.run_in_loop(redis.delete, key)
                        deleted_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to delete key {key}: {e}")
                        failed_count += 1
            except Exception as e:
                self.logger.error(f"Failed to scan Redis keys during clear: {e}")
                raise
                
            self.logger.info(f"Cache cleared - Deleted: {deleted_count}, Failed: {failed_count}")
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
            raise

    async def clear_all_cache(self) -> None:
        """Flush the cache for all users"""
        try:
            redis = await self._ensure_redis_connection(None)
            
            pattern = f"{self._base_prefix}*"  # Match all user keys
            deleted_count = 0
            failed_count = 0
            
            try:
                async for key in redis.scan_iter(match=pattern):
                    try:
                        await async_manager.run_in_loop(redis.delete, key)
                        deleted_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to delete key {key}: {e}")
                        failed_count += 1
            except Exception as e:
                self.logger.error(f"Failed to scan Redis keys during clear: {e}")
                raise
                
            self.logger.info(f"All caches cleared - Deleted: {deleted_count}, Failed: {failed_count}")
        except Exception as e:
            self.logger.error(f"Error clearing all caches: {e}")
            raise

    async def clear_old_entries(self, cache_duration_days: int, user_email: str) -> None:
        """Proactively clear old cache entries for a specific user"""
        try:
            redis = await self._ensure_redis_connection(user_email)
            
            now = datetime.now()
            local_tz = now.astimezone().tzinfo
            cache_cutoff = (now - timedelta(days=cache_duration_days)).astimezone(timezone.utc)
            
            pattern = f"{self._get_key_prefix(user_email)}*"
            deleted_count = 0
            failed_count = 0
            invalid_count = 0
            
            async for key in redis.scan_iter(match=pattern):
                try:
                    email_data = await async_manager.run_in_loop(redis.get, key)
                    if not email_data:
                        continue
                        
                    email_dict = json.loads(email_data)
                    date_str = email_dict.get('date')
                    
                    if not date_str:
                        await async_manager.run_in_loop(redis.delete, key)
                        invalid_count += 1
                        continue
                        
                    try:
                        if 'Z' in date_str:
                            parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        elif '+' in date_str or '-' in date_str[-6:]:
                            parsed_date = datetime.fromisoformat(date_str)
                        else:
                            parsed_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                        
                        if parsed_date.tzinfo is None:
                            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                        else:
                            parsed_date = parsed_date.astimezone(timezone.utc)
                            
                        if parsed_date < cache_cutoff:
                            await async_manager.run_in_loop(redis.delete, key)
                            deleted_count += 1
                            
                    except ValueError:
                        await async_manager.run_in_loop(redis.delete, key)
                        invalid_count += 1
                        
                except Exception as e:
                    self.logger.error(f"Error processing cache entry {key}: {e}")
                    failed_count += 1
                    
            self.logger.info(
                f"Cache cleanup complete - Expired: {deleted_count}, "
                f"Invalid: {invalid_count}, Failed: {failed_count}"
            )
            
        except Exception as e:
            self.logger.error(f"Error clearing old cache entries: {e}")
            raise