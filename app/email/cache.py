from abc import ABC, abstractmethod
from typing import List, Optional
import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging

from ..email_processor import AnalyzedEmail

class EmailCache(ABC):
    """Abstract base class for email caching"""
    
    @abstractmethod
    async def get_recent(self, days: int) -> List[AnalyzedEmail]:
        pass

    @abstractmethod
    async def store_many(self, emails: List[AnalyzedEmail]) -> None:
        pass

class RedisEmailCache(EmailCache):
    """Redis implementation of email cache"""
    
    def __init__(self, redis_client, ttl_days: int = 7):
        self.redis = redis_client
        self.ttl = timedelta(days=ttl_days)
        self.key_prefix = "email:"

    async def get_recent(self, days: int) -> List[AnalyzedEmail]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Get all email keys
        try:
            keys = await self.redis.keys(f"{self.key_prefix}*")
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
                        email_dict['date'] = parsed_date
                        
                        # Compare dates only if parsing succeeded
                        if parsed_date >= cutoff:
                            emails.append(AnalyzedEmail(**email_dict))
                    except (ValueError, KeyError) as e:
                        # Log error but continue processing other emails
                        logging.warning(f"Error processing cached email {key}: {e}")
                        continue
            
            return sorted(emails, key=lambda x: x.date, reverse=True)
        except Exception as e:
            logging.error(f"Error fetching emails from Redis: {e}")
            return []

    async def store_many(self, emails: List[AnalyzedEmail]) -> None:
        # Store each email with message_id as key
        print("Number of emails to store: ", len(emails))
        for email in emails:
            try:
                key = f"{self.key_prefix}{email.id}"
                print("Storing email with key: ", email.id)
                # Convert to dict and ensure datetime is JSON serializable
                email_dict = email.dict()
                # Ensure date is timezone-aware before converting to ISO format
                if email_dict['date'].tzinfo is None:
                    email_dict['date'] = email_dict['date'].replace(tzinfo=timezone.utc)
                email_dict['date'] = email_dict['date'].isoformat()

                await self.redis.set(
                    key,
                    json.dumps(email_dict),
                    ex=int(self.ttl.total_seconds())
                )
                print("Email stored successfully")
            except Exception as e:
                logging.error(f"Error storing email {email.id} in Redis: {e}")
                continue 