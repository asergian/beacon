"""Quota and rate limit management for Gmail API.

This module provides functionality for managing API quota and rate limits
when interacting with the Gmail API to prevent quota overruns and handle
rate limiting gracefully.
"""

import logging
import time
import random
import asyncio
from typing import List, Tuple, Any, Callable

from .exceptions import RateLimitError

logger = logging.getLogger(__name__)


class QuotaManager:
    """Manages quota usage and rate limiting for Gmail API."""
    
    def __init__(self):
        """Initialize the quota manager with default settings."""
        self._request_count = 0
        self._last_request_time = 0
        self._min_request_interval = 0.1
        self._max_retries = 3
        self._base_delay = 1
        self._quota_window = 1.0
        self._quota_limit = 250  # Gmail's default quota
        self._quota_cost_get = 5
        self._quota_usage: List[Tuple[float, int]] = []
        self._last_quota_reset = time.time()
        self._batch_size = 25
        self._concurrent_batch_limit = 5
    
    async def handle_rate_limit(self, attempt: int) -> None:
        """Handle rate limit with exponential backoff.
        
        Args:
            attempt: The current attempt number (0-indexed)
            
        Raises:
            RateLimitError: If max retries are exceeded
        """
        if attempt >= self._max_retries:
            raise RateLimitError("Max retries exceeded for rate limit")
            
        delay = (self._base_delay * (2 ** attempt)) + (random.random() * 0.5)
        logger.warning(f"Rate limit hit. Backing off for {delay:.2f} seconds (attempt {attempt + 1}/{self._max_retries})")
        await asyncio.sleep(delay)
        
        # Adjust batch size and concurrency after rate limit
        if attempt > 0:
            self._batch_size = max(5, self._batch_size - 2)
            self._concurrent_batch_limit = max(2, self._concurrent_batch_limit - 1)
            logger.info(f"Adjusted batch size to {self._batch_size} and concurrency to {self._concurrent_batch_limit}")
    
    async def execute_with_retry(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute an operation with retry logic for rate limits.
        
        Args:
            operation: The function to execute
            *args: Arguments to pass to the operation
            **kwargs: Keyword arguments to pass to the operation
            
        Returns:
            The result of the operation
            
        Raises:
            RateLimitError: If max retries are exceeded
        """
        for attempt in range(self._max_retries):
            try:
                # Ensure minimum time between requests
                now = time.time()
                time_since_last = now - self._last_request_time
                if time_since_last < self._min_request_interval:
                    await asyncio.sleep(self._min_request_interval - time_since_last)
                
                self._last_request_time = time.time()
                self._request_count += 1
                
                return operation(*args, **kwargs)
                
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    await self.handle_rate_limit(attempt)
                    continue
                raise
                
        raise RateLimitError("Max retries exceeded")
    
    async def track_quota(self, cost: int):
        """Track API quota usage with automatic reset.
        
        Args:
            cost: The quota cost of the operation
        """
        current_time = time.time()
        
        # Reset quota if window has passed
        if current_time - self._last_quota_reset >= self._quota_window:
            self._quota_usage.clear()
            self._last_quota_reset = current_time
        
        # Remove old timestamps
        self._quota_usage = [t for t in self._quota_usage 
                           if current_time - t[0] < self._quota_window]
        
        # Calculate current usage
        current_usage = sum(cost for _, cost in self._quota_usage)
        
        # If we would exceed quota, wait for reset
        if current_usage + cost >= self._quota_limit:
            wait_time = self._quota_window - (current_time - self._last_quota_reset)
            if wait_time > 0:
                logger.info(f"Quota limit reached, waiting {wait_time:.2f}s for reset")
                await asyncio.sleep(wait_time)
                self._quota_usage.clear()
                self._last_quota_reset = time.time()
        
        # Add new usage
        self._quota_usage.append((current_time, cost))
    
    async def execute_batch_with_quota(self, batch_request, batch_size: int):
        """Execute a batch request with quota tracking and rate limiting.
        
        Args:
            batch_request: The batch request to execute
            batch_size: The size of the batch for quota calculation
            
        Returns:
            The result of the batch request
            
        Raises:
            RateLimitError: If rate limits are hit
        """
        try:
            # Track quota before execution
            await self.track_quota(self._quota_cost_get * batch_size)
            
            # Add jitter to request timing to avoid thundering herd
            jitter = random.uniform(0, 0.1)
            current_time = time.time()
            time_since_last = current_time - self._last_request_time
            if time_since_last < self._min_request_interval:
                await asyncio.sleep(self._min_request_interval - time_since_last + jitter)
            
            # Execute with retry
            result = await self.execute_with_retry(batch_request.execute)
            self._last_request_time = time.time()
            return result

        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                # If we hit rate limit, adjust parameters dynamically
                self._min_request_interval = min(self._min_request_interval * 1.2, 0.5)
                raise RateLimitError(str(e))
            raise
    
    @property
    def batch_size(self) -> int:
        """Get the current batch size."""
        return self._batch_size
    
    @property
    def concurrent_batch_limit(self) -> int:
        """Get the current concurrent batch limit."""
        return self._concurrent_batch_limit
    
    @property
    def quota_cost_get(self) -> int:
        """Get the quota cost for a GET operation."""
        return self._quota_cost_get 