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
    
    def __init__(self, get_redis_client, ttl_days: int = 7, user_email: str = None):
        """Initialize Redis cache with a function to get the Redis client
        
        Args:
            get_redis_client: Function that returns a Redis client instance
            ttl_days: Number of days to keep emails in cache
            user_email: Optional user email to initialize the cache for
        """
        if not callable(get_redis_client):
            raise ValueError("get_redis_client must be a callable")
        self.get_redis_client = get_redis_client
        self.ttl = timedelta(days=ttl_days)
        self.user_email = user_email.lower() if user_email else None
        self._base_prefix = "email:"
        self.logger = logging.getLogger(__name__)
        
    @property
    def key_prefix(self) -> str:
        """Get the cache key prefix for the current user"""
        if not self.user_email:
            raise ValueError("user_email must be set to access cache")
        return f"{self._base_prefix}{self.user_email}:"

    async def set_user(self, user_email: str) -> None:
        """Set the current user for the cache"""
        if not user_email:
            raise ValueError("user_email cannot be empty")
        new_email = user_email.lower()
        # Clear any existing cache for different user
        if self.user_email and self.user_email != new_email:
            try:
                await async_manager.run_in_loop(self.clear_cache)
            except Exception as e:
                self.logger.error(f"Failed to clear cache when switching users: {e}")
        self.user_email = new_email
        
    async def _ensure_redis_connection(self) -> Redis:
        """Ensure Redis connection is active and working"""
        if not self.user_email:
            raise ValueError("user_email must be set before accessing cache")
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

    async def get_recent(self, cache_duration_days: int, days_back: int) -> List[ProcessedEmail]:
        """Get recent emails from cache"""
        try:
            redis = await self._ensure_redis_connection()
            
            # Calculate the cutoff times in UTC
            now = datetime.now()  # Local time
            local_tz = now.astimezone().tzinfo  # Get the local timezone
            self.logger.info(f"Local timezone: {local_tz}")
            
            cache_cutoff = (now - timedelta(days=cache_duration_days)).astimezone(timezone.utc)
            
            # For days_back=0, use today's start (local midnight)
            if days_back == 0:
                # Make it timezone-aware in local time first
                start_date = now.replace(tzinfo=local_tz)
                
                # Get local midnight
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # Then convert to UTC
                start_date = start_date.astimezone(timezone.utc)
            else:
                # Make it timezone-aware in local time first
                start_date = now.replace(tzinfo=local_tz)
                
                # For other days_back, get midnight of that day in local time
                start_date = (start_date - timedelta(days=days_back))
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # Then convert to UTC
                start_date = start_date.astimezone(timezone.utc)
            
            self.logger.info(f"Date filtering parameters: now={now} (local), local_midnight={start_date.astimezone(local_tz)}, start_date_utc={start_date}, cache_cutoff={cache_cutoff}, days_back={days_back}")
            
            # Get all keys for the current user
            pattern = f"{self.key_prefix}*"
            keys = []
            try:
                # Use scan_iter directly with await since we're in an async context
                async for key in redis.scan_iter(match=pattern):
                    keys.append(key)
                    # Log the key pattern we're finding
                    self.logger.info(f"Found Redis key: {key}")
            except Exception as e:
                self.logger.error(f"Failed to scan Redis keys: {e}")
                return []
            
            self.logger.info(f"Found {len(keys)} keys in Redis for user {self.user_email}")
            emails = []
            
            # Fetch and deserialize emails
            for key in keys:
                try:
                    # Extract ID from key for logging
                    key_id = key.split(':')[-1]
                    self.logger.info(f"Processing Redis key: {key}, extracted ID: {key_id}")
                    
                    # Use await directly since we're in an async context
                    email_data = await redis.get(key)
                    if not email_data:
                        continue
                        
                    email_dict = json.loads(email_data)
                    # Log the ID from the stored data
                    self.logger.info(f"Loaded email data with ID: {email_dict.get('id')}")
                    
                    date_str = email_dict.get('date')
                    
                    if not date_str:
                        self.logger.warning(f"No date found for email {key}")
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
                        
                        self.logger.info(f"Processing email {key}: date={parsed_date}, cache_cutoff={cache_cutoff}, start_date={start_date}")
                        
                        # First check if email is within the requested date range
                        if start_date <= parsed_date:
                            try:
                                processed_email = ProcessedEmail(**email_dict)
                                # Ensure the ID is properly set
                                if not processed_email.id:
                                    self.logger.warning(f"Email missing ID in cache: {key}")
                                    continue
                                emails.append(processed_email)
                                self.logger.info(f"Added email {key} to results (within date range, ID: {processed_email.id})")
                            except Exception as e:
                                self.logger.error(f"Failed to create ProcessedEmail for {key}: {e}")
                                continue
                        # Only delete if older than cache cutoff
                        elif parsed_date < cache_cutoff:
                            try:
                                await async_manager.run_in_loop(redis.delete, key)
                                self.logger.info(f"Deleted old email {key} (before cache cutoff {cache_cutoff})")
                            except Exception as e:
                                self.logger.warning(f"Failed to delete old email {key}: {e}")
                        else:
                            self.logger.info(f"Keeping email {key} in cache (between start_date and cache_cutoff)")
                    except ValueError as e:
                        self.logger.warning(f"Date parsing error for {key}: {e}, date_str={date_str}")
                        continue
                except Exception as e:
                    self.logger.error(f"Error processing email {key}: {e}")
                    continue
            
            # Sort emails by date in descending order
            emails.sort(key=lambda x: x.date, reverse=True)
            self.logger.info(f"Returning {len(emails)} emails after date filtering with IDs: {[e.id for e in emails]}")
            return emails
            
        except Exception as e:
            self.logger.error(f"Error fetching emails from Redis: {e}")
            return []

    async def store_many(self, emails: List[ProcessedEmail]) -> None:
        """Store multiple emails in cache"""
        if not emails:
            return
            
        try:
            redis = await self._ensure_redis_connection()
            
            self.logger.info(f"Storing {len(emails)} emails for user {self.user_email}")
            stored_count = 0
            
            for email in emails:
                try:
                    # Log the ID we're about to store
                    self.logger.info(f"Storing email with ID: {email.id}")
                    key = f"{self.key_prefix}{email.id}"
                    email_dict = email.dict()
                    
                    # Ensure date is properly formatted in UTC
                    if isinstance(email_dict['date'], datetime):
                        if email_dict['date'].tzinfo is None:
                            email_dict['date'] = email_dict['date'].replace(tzinfo=timezone.utc)
                        else:
                            email_dict['date'] = email_dict['date'].astimezone(timezone.utc)
                        email_dict['date'] = email_dict['date'].isoformat()
                    
                    # Log the full key and ID being stored
                    self.logger.info(f"Using Redis key: {key} for email ID: {email.id}")
                    
                    ttl_seconds = int(self.ttl.total_seconds())
                    
                    # Store with TTL
                    await async_manager.run_in_loop(
                        redis.set,
                        key,
                        json.dumps(email_dict),
                        ex=ttl_seconds
                    )
                    
                    exists = await async_manager.run_in_loop(redis.exists, key)
                    if exists:
                        stored_count += 1
                        self.logger.info(f"Successfully stored email with ID: {email.id}")
                    else:
                        self.logger.warning(f"Failed to verify storage of email {email.id}")
                    
                except Exception as e:
                    self.logger.error(f"Error storing email {email.id}: {e}")
                    continue
            
            self.logger.info(f"Successfully stored {stored_count} out of {len(emails)} emails")
                    
        except Exception as e:
            self.logger.error(f"Error in store_many: {e}")
            raise

    async def clear_cache(self) -> None:
        """Flush the cache"""
        if not self.user_email:
            return
            
        try:
            redis = await self._ensure_redis_connection()
            
            # Only clear keys for the current user
            pattern = f"{self.key_prefix}*"
            deleted_count = 0
            try:
                async for key in redis.scan_iter(match=pattern):
                    try:
                        await async_manager.run_in_loop(redis.delete, key)
                        deleted_count += 1
                    except Exception as e:
                        self.logger.warning(f"Failed to delete key {key}: {e}")
            except Exception as e:
                self.logger.error(f"Failed to scan Redis keys during clear: {e}")
                raise
                
            self.logger.info(f"Redis cache cleared successfully. Deleted {deleted_count} keys.")
        except Exception as e:
            self.logger.error(f"Error clearing Redis cache: {e}")
            raise