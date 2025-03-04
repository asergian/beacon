from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
from redis.asyncio import Redis
from app.models import User
import hashlib
from zoneinfo import ZoneInfo

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
        # Hash the email to prevent key injection and ensure consistent format
        email_hash = hashlib.sha256(user_email.lower().encode()).hexdigest()[:12]
        return f"{self._base_prefix}{email_hash}:"

    def _validate_user_email(self, user_email: str) -> None:
        """Validate user email format and presence"""
        if not user_email:
            raise ValueError("user_email cannot be empty")
        if not isinstance(user_email, str):
            raise ValueError("user_email must be a string")
        if '@' not in user_email:
            raise ValueError("Invalid email format")
        # Normalize email to lowercase
        return user_email.lower()

    async def _ensure_redis_connection(self, user_email: str) -> Redis:
        """Ensure Redis connection is active and working"""
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

    async def get_recent(self, cache_duration_days: int, days_back: int, user_email: str, user_timezone: str = 'US/Pacific') -> List[ProcessedEmail]:
        """Get recent emails from cache for a specific user"""
        self._validate_user_email(user_email)
        try:
            redis = await self._ensure_redis_connection(user_email)
            
            # Use the user's timezone for date calculations
            try:
                # Create timezone object from string
                user_tz = ZoneInfo(user_timezone)
                self.logger.info(f"Using user timezone for cache: {user_timezone}")
            except (ImportError, Exception) as e:
                self.logger.warning(f"Could not use user timezone ({user_timezone}) for cache, falling back to US/Pacific: {e}")
                try:
                    user_tz = ZoneInfo('US/Pacific')
                except Exception:
                    user_tz = timezone.utc
            
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
            keys = []
            try:
                cursor = 0
                while True:
                    cursor, temp_keys = await redis.scan(cursor, match=pattern)
                    keys.extend(temp_keys)
                    if cursor == 0:
                        break
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
                                await redis.delete(key)
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
        self._validate_user_email(user_email)
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
                        if email_dict['date'].tzinfo is None:
                            email_dict['date'] = email_dict['date'].replace(tzinfo=timezone.utc)
                        else:
                            email_dict['date'] = email_dict['date'].astimezone(timezone.utc)
                        email_dict['date'] = email_dict['date'].isoformat()
                    
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
            
            self.logger.info(f"Cache storage complete - Stored: {stored_count}, Failed: {failed_count}")
                    
        except Exception as e:
            self.logger.error(f"Error in store_many: {e}")
            raise

    async def clear_cache(self, user_email: str) -> None:
        """Flush all cached emails for a specific user"""
        self._validate_user_email(user_email)
        try:
            redis = await self._ensure_redis_connection(user_email)
            
            # Only clear keys for the specific user
            pattern = f"{self._get_key_prefix(user_email)}*"
            deleted_count = 0
            failed_count = 0
            
            try:
                cursor = 0
                while True:
                    cursor, temp_keys = await redis.scan(cursor, match=pattern)
                    for key in temp_keys:
                        try:
                            await redis.delete(key)
                            deleted_count += 1
                        except Exception as e:
                            self.logger.error(f"Failed to delete key {key}: {e}")
                            failed_count += 1
                    if cursor == 0:
                        break
            except Exception as e:
                self.logger.error(f"Failed to scan Redis keys during clear: {e}")
                raise
                
            self.logger.info(f"Cache cleared - Deleted: {deleted_count}, Failed: {failed_count}")
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
            raise

    async def clear_all_cache(self, user_email: str) -> None:
        """Clear all caches (admin only)
        
        Args:
            user_email: Email of the admin user attempting the operation
            
        Raises:
            ValueError: If user_email is not provided or user is not an admin
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
            deleted_count = 0
            failed_count = 0
            
            try:
                cursor = 0
                while True:
                    cursor, temp_keys = await redis.scan(cursor, match=pattern)
                    for key in temp_keys:
                        try:
                            await redis.delete(key)
                            deleted_count += 1
                        except Exception as e:
                            self.logger.error(f"Failed to delete key {key}: {e}")
                            failed_count += 1
                    if cursor == 0:
                        break
            except Exception as e:
                self.logger.error(f"Failed to scan Redis keys during clear: {e}")
                raise
                
            self.logger.info(f"All caches cleared by admin {user_email} - Deleted: {deleted_count}, Failed: {failed_count}")
        except Exception as e:
            self.logger.error(f"Failed to clear all caches: {e}")
            raise

    async def clear_old_entries(self, cache_duration_days: int, user_email: str, user_timezone: str = 'US/Pacific') -> None:
        """Proactively clear old cache entries"""
        try:
            redis = await self._ensure_redis_connection(user_email)
            
            # Use the user's timezone for date calculations
            try:
                # Create timezone object from string
                user_tz = ZoneInfo(user_timezone)
                self.logger.info(f"Using user timezone for cache cleanup: {user_timezone}")
            except (ImportError, Exception) as e:
                self.logger.warning(f"Could not use user timezone ({user_timezone}) for cache cleanup, falling back to US/Pacific: {e}")
                try:
                    user_tz = ZoneInfo('US/Pacific')
                except Exception:
                    user_tz = timezone.utc
            
            now = datetime.now(user_tz)
            cache_cutoff = (now - timedelta(days=cache_duration_days)).astimezone(timezone.utc)
            
            pattern = f"{self._get_key_prefix(user_email)}*"
            deleted_count = 0
            failed_count = 0
            invalid_count = 0
            
            cursor = 0
            while True:
                cursor, temp_keys = await redis.scan(cursor, match=pattern)
                for key in temp_keys:
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
                                await redis.delete(key)
                                deleted_count += 1
                                
                        except ValueError:
                            await redis.delete(key)
                            invalid_count += 1
                            
                    except Exception as e:
                        self.logger.error(f"Error processing cache entry {key}: {e}")
                        failed_count += 1
                
                if cursor == 0:
                    break
                    
            self.logger.info(
                f"Cache cleanup complete - Expired: {deleted_count}, "
                f"Invalid: {invalid_count}, Failed: {failed_count}"
            )
            
        except Exception as e:
            self.logger.error(f"Error clearing old cache entries: {e}")
            raise

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the Redis cache."""
        info = await self.redis.info()
        keys = await self.redis.keys('email:*')
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

    async def log_cache_size(self) -> None:
        """Log the size of the Redis cache."""
        try:
            redis = await self._ensure_redis_connection('admin@example.com')  # Use a dummy email for connection
            keys = await redis.keys(f"{self._base_prefix}*")
            total_size = 0
            for key in keys:
                size = await redis.memory_usage(key)
                total_size += size
            self.logger.info(f"Total Redis cache size: {total_size / 1024:.2f} KB")
        except Exception as e:
            self.logger.error(f"Error logging cache size: {e}")