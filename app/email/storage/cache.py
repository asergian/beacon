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
    
    def __init__(self, redis_client, ttl_days: int = 7):
        self.redis = redis_client
        self.ttl = timedelta(days=ttl_days)
        self.key_prefix = "email:"

    async def _ensure_redis_connection(self):
        """Ensure Redis connection is active and working"""
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

    async def get_recent(self, cache_duration_days: int) -> List[ProcessedEmail]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=cache_duration_days)
        
        try:
            await self._ensure_redis_connection()
            
            keys = await self.redis.keys(f"{self.key_prefix}*")
            logging.info(f"Found {len(keys)} keys in Redis")
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
                        
                        if parsed_date >= cutoff:
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
            
            logging.info(f"Number of emails to store: {len(emails)}")
            for email in emails:
                try:
                    key = f"{self.key_prefix}{email.id}"
                    email_dict = email.dict()
                    if email_dict['date'].tzinfo is None:
                        email_dict['date'] = email_dict['date'].replace(tzinfo=timezone.utc)
                    email_dict['date'] = email_dict['date'].isoformat()

                    ttl_seconds = int(self.ttl.total_seconds())
                    logging.info(f"Storing email {email.id} with TTL: {ttl_seconds} seconds")

                    await self.redis.set(
                        key,
                        json.dumps(email_dict),
                        ex=ttl_seconds
                    )
                    
                    exists = await self.redis.exists(key)
                    logging.info(f"Email {email.id} stored successfully. Key exists: {exists}")
                except Exception as e:
                    logging.error(f"Error storing email {email.id} in Redis: {e}")
                    continue
        except Exception as e:
            logging.error(f"Error in store_many: {e}")

    async def clear_cache(self) -> None:
        """Flush the Redis cache"""
        try:
            await self._ensure_redis_connection()
            
            await self.redis.flushdb()
            logging.info("Redis cache cleared successfully.")
        except Exception as e:
            logging.error(f"Error clearing Redis cache: {e}") 