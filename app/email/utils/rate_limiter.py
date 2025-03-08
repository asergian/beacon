"""Rate limiting utilities for API request management.

This module provides functionality for limiting the rate of API requests to external
services, helping avoid rate limit errors and ensuring responsible API usage. It 
implements a sliding window rate limiting algorithm for asynchronous operations.

TODO: This utility is currently unused. Consider integrating it with the Gmail API client 
or other external API calls to prevent rate limiting errors, or moving it to app/utils
if it could be useful for other parts of the application.
"""

import asyncio
from datetime import datetime, timedelta

class RateLimiter:
    """Rate limits API calls using a sliding window algorithm.
    
    This class provides asynchronous rate limiting functionality to prevent
    exceeding API rate limits when making requests to external services. It 
    tracks calls over a one-minute window and delays new calls when needed.
    
    Attributes:
        calls_per_minute: Maximum number of allowed calls per minute
        calls: List of timestamps for recent API calls
        _lock: Asyncio lock for thread-safe operations
    """
    
    def __init__(self, calls_per_minute: int = 60):
        """Initialize the RateLimiter with specified rate limit.
        
        Args:
            calls_per_minute: Maximum number of API calls allowed per minute (default: 60)
        """
        self.calls_per_minute = calls_per_minute
        self.calls = []
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Acquire permission to make an API call, waiting if necessary.
        
        This method uses a sliding window algorithm to track API calls over a
        one-minute period. If the rate limit has been reached, it will delay
        the current call until it's safe to proceed.
        
        The method is thread-safe and can be used concurrently from multiple
        asynchronous tasks.
        """
        async with self._lock:
            now = datetime.now()
            self.calls = [t for t in self.calls if now - t < timedelta(minutes=1)]
            
            if len(self.calls) >= self.calls_per_minute:
                wait_time = 60 - (now - self.calls[0]).total_seconds()
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            
            self.calls.append(now) 