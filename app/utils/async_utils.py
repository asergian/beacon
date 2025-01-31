"""Utilities for handling async operations in Flask context."""

import asyncio
import contextvars
import functools
from typing import Any, Callable, TypeVar, Optional
from flask import current_app

T = TypeVar('T')

class AsyncContextManager:
    """Manages async context and event loops for Flask applications."""
    
    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
    def get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create an event loop for the current context."""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop
        
    def run_async(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to run async functions in Flask routes."""
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            loop = self.get_loop()
            
            # Copy context vars from parent to child
            ctx = contextvars.copy_context()
            
            async def _wrapped():
                # Restore context
                for var in ctx:
                    var.set(ctx[var])
                return await func(*args, **kwargs)
            
            try:
                return loop.run_until_complete(_wrapped())
            except RuntimeError as e:
                if "Event loop is closed" in str(e):
                    # Create new loop if current one is closed
                    self._loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self._loop)
                    return self._loop.run_until_complete(_wrapped())
                raise
                
    def ensure_loop(self) -> asyncio.AbstractEventLoop:
        """Ensure we have a valid event loop, creating one if necessary."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
            return loop
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
            
    async def run_in_loop(self, coro: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run a coroutine in the current event loop, handling loop closure."""
        try:
            return await coro(*args, **kwargs)
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                loop = self.ensure_loop()
                return await coro(*args, **kwargs)
            raise

# Global instance
async_manager = AsyncContextManager() 