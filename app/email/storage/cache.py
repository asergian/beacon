from abc import ABC, abstractmethod
from typing import List, Optional
import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging

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
    
    def __init__(self, redis_client, ttl_days: int = 7, user_email: str = None):
        self.redis = redis_client
        self.ttl = timedelta(days=ttl_days)
        self.user_email = user_email
        self._base_prefix = "email:"
        
    @property
    def key_prefix(self) -> str:
        """Get the cache key prefix for the current user"""
        if not self.user_email:
            raise ValueError("user_email must be set to access cache")
        return f"{self._base_prefix}{self.user_email}:"

    async def set_user(self, user_email: str) -> None:
        """Set the current user for the cache"""
        self.user_email = user_email
        
    async def _ensure_redis_connection(self):
        """Ensure Redis connection is active and working"""
        if not self.user_email:
            raise ValueError("user_email must be set before accessing cache")
        try:
            if not self.redis.connection:
                await self.redis.initialize()
            # Test the connection with a ping
            await self.redis.ping()
        except Exception as e:
            logging.warning(f"Redis connection check failed: {e}")
            # Attempt to reconnect
            try:
                await self.redis.initialize()
            except Exception as e:
                logging.error(f"Redis reconnection failed: {e}")
                raise

    async def get_recent(self, cache_duration_days: int, days_back: int) -> List[ProcessedEmail]:
        # Calculate the cutoff time using local timezone
        local_tz = datetime.now().astimezone().tzinfo  # Get local timezone info
        cutoff = (datetime.now(local_tz) - timedelta(days=cache_duration_days)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate the start date based on days_back
        start_date = (datetime.now(local_tz) - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)

        try:
            await self._ensure_redis_connection()
            
            # Ensure we are fetching keys specific to the current user
            if not self.user_email:
                raise ValueError("user_email must be set to fetch user-specific emails")
                
            keys = await self.redis.keys(f"{self.key_prefix}*")
            logging.info(f"Found {len(keys)} keys in Redis for user {self.user_email}")
            emails = []
            
            # Fetch and deserialize emails
            for key in keys:
                email_data = await self.redis.get(key)
                if email_data:
                    try:
                        email_dict = json.loads(email_data)
                        # Parse the date string and ensure it's UTC
                        date_str = email_dict['date']
                        parsed_date = datetime.fromisoformat(date_str)
                        if parsed_date.tzinfo is None:
                            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                        
                        # Filter emails based on both cutoff and start_date
                        if parsed_date >= start_date and parsed_date >= cutoff:
                            emails.append(ProcessedEmail(**email_dict))
                        else:
                            logging.info(f"Email {key} filtered out due to date")
                    except (ValueError, KeyError) as e:
                        logging.warning(f"Error processing cached email {key}: {e}")
                        continue
            
            logging.info(f"Returning {len(emails)} emails after date filtering")
            return sorted(emails, key=lambda x: x.date, reverse=True)
        except Exception as e:
            logging.error(f"Error fetching emails from Redis: {e}")
            return []

    async def store_many(self, emails: List[ProcessedEmail]) -> None:
        try:
            await self._ensure_redis_connection()
            
            # Ensure we are storing emails specific to the current user
            if not self.user_email:
                raise ValueError("user_email must be set to store user-specific emails")
            
            logging.info(f"Number of emails to store for user {self.user_email}: {len(emails)}")
            for email in emails:
                try:
                    key = f"{self.key_prefix}{email.id}"
                    email_dict = email.dict()
                    if email_dict['date'].tzinfo is None:
                        email_dict['date'] = email_dict['date'].replace(tzinfo=timezone.utc)
                    email_dict['date'] = email_dict['date'].isoformat()

                    ttl_seconds = int(self.ttl.total_seconds())
                    logging.info(f"Storing email {email.id} for user {self.user_email} with TTL: {ttl_seconds} seconds")

                    await self.redis.set(
                        key,
                        json.dumps(email_dict),
                        ex=ttl_seconds
                    )
                    
                    exists = await self.redis.exists(key)
                    logging.info(f"Email {email.id} stored successfully for user {self.user_email}. Key exists: {exists}")
                except Exception as e:
                    logging.error(f"Error storing email {email.id} for user {self.user_email} in Redis: {e}")
                    continue
        except Exception as e:
            logging.error(f"Error in store_many for user {self.user_email}: {e}")

    async def clear_cache(self) -> None:
        """Flush the Redis cache"""
        try:
            await self._ensure_redis_connection()
            
            await self.redis.flushdb()
            logging.info("Redis cache cleared successfully.")
        except Exception as e:
            logging.error(f"Error clearing Redis cache: {e}") 